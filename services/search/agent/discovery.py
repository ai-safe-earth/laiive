"""The city sweep: search → extract → dedup → dry-run candidates.

Writes nothing. Each candidate carries its source URL and a dedup verdict so
the reviewer sees exactly what an approve would add; the writer's own probe
still guards the actual write.
"""

from datetime import datetime
from itertools import zip_longest

from laiive_shared import EventDraft, missing_required
from laiive_shared.neo4j_writer import parse_start_at
from laiive_shared.normalize import norm
from loguru import logger
from pydantic import BaseModel

from agent import extraction, graph, tavily
from config import settings

# One phrasing reaches one kind of site, and the language of the phrasing picks
# the language of the sites. Measured on Torino, ten results per query, counting
# Italian domains:
#
#   "live music concerts Torino August 2026"        3/9
#   "live music concerts Turin August 2026"         2/9
#   "concerti Torino agosto 2026"                   7/9
#   "agenda culturale Torino musica dal vivo"       6/9
#   "cosa fare a Torino spettacoli musicali eventi" 5/9
#
# The English queries return eventbrite.com, songkick, bandsintown, operabase
# and an English tourism site. The Italian ones return torinotoday.it,
# guidatorino.com, torinogiovani.it and eventi.comune.torino.it — the city
# council's own listing, which no English query surfaced at all.
#
# Note it is the keywords, not the toponym: Torino vs Turin moved 3/9 to 2/9,
# English vs Italian moved 3/9 to 7/9. So there is no English template here.
# The international aggregators are reachable in Italian anyway (ticketone.it
# and eventbrite.it appear in every Italian query above), so an English one
# would buy only the layer written for visitors.
#
# This couples the list to the swept provinces being Italian. Adding a province
# elsewhere means writing its own phrasings, which is the honest cost of
# reaching a scene instead of a search engine's idea of one.
#
# Recall is the goal here, not precision. A wrong candidate costs a human one
# glance at a dry-run report, and anything that survives to a card carries the
# "!" mark saying nobody at the door confirmed it.
QUERY_TEMPLATES = [
    # Cultural agendas and what's-on listings.
    "{city} agenda culturale musica dal vivo {month_year}",
    # Clubs and the live circuit.
    "{city} concerti live club locali serate musica dal vivo",
    # The independent circuit, which is where the small gigs actually are.
    "{city} circolo arci centro culturale live band concerti",
    # Venue programming and ticketing.
    "concerti {city} {month_year} biglietti programmazione stagione",
    # How a person actually asks, which reaches the municipal and city-guide
    # listings the other four phrasings miss.
    "cosa fare a {city} {month_year} spettacoli musicali eventi",
]


# strftime("%B") answers in the process locale, which is C on both this box and
# the container -- so it was putting "August 2026" inside otherwise-Italian
# queries, the exact mistake the templates above exist to avoid. Spelled out
# rather than fixed with setlocale, which is process-global and not thread-safe.
_ITALIAN_MONTHS = (
    "gennaio",
    "febbraio",
    "marzo",
    "aprile",
    "maggio",
    "giugno",
    "luglio",
    "agosto",
    "settembre",
    "ottobre",
    "novembre",
    "dicembre",
)


def italian_month_year(when: datetime) -> str:
    return f"{_ITALIAN_MONTHS[when.month - 1]} {when.year}"


class Candidate(BaseModel):
    draft: EventDraft
    source_url: str
    missing: list[str] = []
    dedup_status: str = "new"  # new | exists | similar
    matched_uid: str | None = None
    matched_name: str | None = None
    similarity: float | None = None


class SweepResult(BaseModel):
    city: str
    candidates: list[Candidate] = []
    stats: dict = {}


def sweep_city(city: str, max_pages: int | None = None) -> SweepResult:
    """Dry-run discovery for one city. Never writes to the graph."""
    max_pages = max_pages or settings.sweep_max_pages
    month_year = italian_month_year(datetime.now())

    # One credit per call regardless of how many rows come back, so this counts
    # calls, not results. Recorded on the report because a monthly allowance
    # nobody can see is one nobody notices spending.
    tavily_calls = 0
    per_template: list[list[tavily.SearchHit]] = []
    seen_urls: set[str] = set()
    for template in QUERY_TEMPLATES:
        query = template.format(city=city, month_year=month_year)
        tavily_calls += 1
        kept = []
        for hit in tavily.search(
            query,
            settings.sweep_results_per_query,
            country=settings.sweep_country,
        ):
            if hit.url in seen_urls:
                continue
            seen_urls.add(hit.url)
            kept.append(hit)
        per_template.append(kept)

    # Round-robin rather than concatenation. max_pages truncates below, and
    # appending template after template spends the whole budget on the first
    # one's results — the later, narrower phrasings are what reach the circuit,
    # so they must not be the ones that fall off the end.
    pages = [hit for row in zip_longest(*per_template) for hit in row if hit]
    # Bounds the LLM extraction below, never the Tavily spend above: the calls
    # have already been made and paid for by the time this runs.
    pages = pages[:max_pages]

    drafts: list[tuple[EventDraft, str]] = []
    pages_with_events = 0
    for hit in pages:
        text = hit.raw_content or hit.content
        if not text.strip():
            continue
        found = extraction.extract_events_from_page(text, url=hit.url, city=city)
        if found:
            pages_with_events += 1
        drafts.extend((draft, hit.url) for draft in found)

    candidates: list[Candidate] = []
    skipped_past = 0
    seen_keys: set[tuple[str, str, str]] = set()
    for draft, url in drafts:
        if not draft.city:
            draft.city = city  # the page was found searching this city

        start_at = parse_start_at(draft.start_at or "")
        if start_at is not None and start_at < datetime.now():
            skipped_past += 1
            continue

        # Intra-sweep dedup: two pages listing the same gig collapse to one.
        key = (
            norm(draft.name or (draft.artists[0] if draft.artists else "")),
            (start_at.date().isoformat() if start_at else ""),
            norm(draft.venue or ""),
        )
        if key in seen_keys:
            continue
        seen_keys.add(key)

        candidate = Candidate(
            draft=draft, source_url=url, missing=missing_required(draft, "admin_search")
        )
        try:
            if exact := graph.probe_duplicate(draft):
                candidate.dedup_status = "exists"
                candidate.matched_uid = exact.uid
                candidate.matched_name = exact.name
            elif near := graph.similar_event(draft):
                candidate.dedup_status = "similar"
                candidate.matched_uid = near.uid
                candidate.matched_name = near.name
                candidate.similarity = near.score
        except Exception as e:
            # Dedup is advisory in a dry run; a probe failure must not eat the sweep.
            logger.warning(f"Dedup probe failed for {key}: {e}")
        candidates.append(candidate)

    return SweepResult(
        city=city,
        candidates=candidates,
        stats={
            "queries": len(QUERY_TEMPLATES),
            "tavily_credits": tavily_calls,
            "pages_searched": len(pages),
            "pages_with_events": pages_with_events,
            "drafts_extracted": len(drafts),
            "skipped_past": skipped_past,
            "candidates": len(candidates),
            "new": sum(1 for c in candidates if c.dedup_status == "new"),
            "exists": sum(1 for c in candidates if c.dedup_status == "exists"),
            "similar": sum(1 for c in candidates if c.dedup_status == "similar"),
            "complete": sum(1 for c in candidates if not c.missing),
        },
    )
