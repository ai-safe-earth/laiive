"""The city sweep: search → extract → dedup → dry-run candidates.

Writes nothing. Each candidate carries its source URL and a dedup verdict so
the reviewer sees exactly what an approve would add; the writer's own probe
still guards the actual write.
"""

from datetime import datetime
from itertools import zip_longest

from laiive_shared import EventDraft, missing_required
from laiive_shared.neo4j_writer import parse_start_at
from laiive_shared.normalize import norm, source_domain
from loguru import logger
from pydantic import BaseModel

from agent import extraction, graph, learning, tavily
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


# Phrasings on probation. One is tried per sweep, in the slot the standing set
# gives up, so the vocabulary keeps growing instead of ossifying around
# whatever was written into this file first. A trial that earns its keep is
# promoted in search_queries and starts appearing on its own; one that does not
# is retired and stops costing credits.
#
# Seeded with the words a person in the scene would use — genre, register, and
# the region rather than the town — because those are exactly the ones a
# generic "concerti" query does not reach. Add to it freely: a new phrasing
# costs nothing until the trial slot reaches it.
TRIAL_TEMPLATES = [
    "{city} musica indipendente concerti emergenti",
    "{city} festival musicale rassegna {month_year}",
    "{city} locali musicali dal vivo jazz blues",
    "{city} concerti rock indie punk {month_year}",
    "{city} jazz club rassegna concerti {month_year}",
    "{city} Piemonte Lombardia eventi musicali {month_year}",
    "{city} cartellone concerti stagione musicale",
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


def plan_queries() -> list[str]:
    """The templates this sweep will spend its credits on.

    Most slots go to the phrasings that have earned them and one is reserved
    for a trial, which is the whole reason the vocabulary can improve. Before
    anything has been learned the file's list is the answer, so a fresh
    database sweeps exactly as it did before this existed.
    """
    slots = settings.sweep_query_slots
    standing = learning.standing_templates(QUERY_TEMPLATES, slots - 1)
    trial = learning.select_trial(TRIAL_TEMPLATES)
    return [*standing, trial] if trial else standing[:slots]


def sweep_city(city: str, max_pages: int | None = None) -> SweepResult:
    """Dry-run discovery for one city. Never writes to the graph."""
    max_pages = max_pages or settings.sweep_max_pages
    month_year = italian_month_year(datetime.now())

    templates = plan_queries()
    include, exclude = learning.domain_filters()
    hints = learning.extraction_hints()

    # One credit per call regardless of how many rows come back, so this counts
    # calls, not results. Recorded on the report because a monthly allowance
    # nobody can see is one nobody notices spending.
    tavily_calls = 0
    per_template: list[list[tavily.SearchHit]] = []
    queries: list[str] = []
    seen_urls: set[str] = set()
    url_query: dict[str, str] = {}
    for position, template in enumerate(templates):
        query = template.format(city=city, month_year=month_year)
        queries.append(template)
        tavily_calls += 1
        # Only the first slot is narrowed to what is already trusted. The rest
        # run open, because a search restricted to the sites it already knows
        # can only ever confirm them — the list would close around whatever it
        # found first and never see a venue that opened last month.
        focus = include if (position == 0 and len(include) >= 3) else None
        kept = []
        for hit in tavily.search(
            query,
            settings.sweep_results_per_query,
            country=settings.sweep_country,
            include_domains=focus,
            # Applied to every slot: dropping a known-empty domain costs
            # nothing and never narrows the field to the already-known.
            exclude_domains=exclude,
        ):
            if hit.url in seen_urls:
                continue
            seen_urls.add(hit.url)
            url_query[hit.url] = template
            kept.append(hit)
        per_template.append(kept)

    # Pages someone vouched for, fetched outright rather than searched for.
    # Search finds these sites and cannot read them, which is the whole reason
    # they are here.
    agenda: list[tavily.SearchHit] = []
    extracted = tavily.extract(learning.agenda_urls(city))
    for hit in extracted:
        if hit.url in seen_urls:
            continue
        seen_urls.add(hit.url)
        agenda.append(hit)
    # Billed per successful extraction, so a page that could not be fetched
    # costs nothing and must not be counted.
    tavily_calls += tavily.extract_credits(len(extracted))

    # Round-robin rather than concatenation. max_pages truncates below, and
    # appending template after template spends the whole budget on the first
    # one's results — the later, narrower phrasings are what reach the circuit,
    # so they must not be the ones that fall off the end.
    pages = agenda + [hit for row in zip_longest(*per_template) for hit in row if hit]
    # Bounds the LLM extraction below, never the Tavily spend above: the calls
    # have already been made and paid for by the time this runs.
    pages = pages[:max_pages]

    drafts: list[tuple[EventDraft, str]] = []
    pages_with_events = 0
    # Per-page bookkeeping, folded into the store at the end of the sweep.
    observed: dict[str, dict] = {}
    events_per_query: dict[str, int] = {}
    for hit in pages:
        domain = source_domain(hit.url)
        seen = observed.setdefault(
            domain,
            {"pages": 0, "pages_with_events": 0, "drafts": 0, "scores": []},
        )
        seen["pages"] += 1
        seen["scores"].append(hit.score)
        text = hit.raw_content or hit.content
        if not text.strip():
            continue
        found = extraction.extract_events_from_page(
            text, url=hit.url, city=city, hint=hints.get(domain, "")
        )
        if found:
            pages_with_events += 1
            seen["pages_with_events"] += 1
            # Attributed via url_query like candidates_new below — this was a
            # hardcoded 0 for every template (confirmed against the live
            # store). Display-only: the dashboard renders it; promotion reads
            # candidates_new alone (learning._query_yield).
            if template := url_query.get(hit.url):
                events_per_query[template] = events_per_query.get(template, 0) + 1
        seen["drafts"] += len(found)
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

    # ── Fold what this sweep learned into the store ──────────────────────────
    # Attribution runs on the "new" verdict, not on approval: the default
    # approve path takes every new candidate, so approval would measure the
    # dedup probe rather than anyone's judgement.
    new_per_domain: dict[str, int] = {}
    new_per_query: dict[str, int] = {}
    for candidate in candidates:
        if candidate.dedup_status != "new":
            continue
        domain = source_domain(candidate.source_url)
        new_per_domain[domain] = new_per_domain.get(domain, 0) + 1
        template = url_query.get(candidate.source_url)
        if template:
            new_per_query[template] = new_per_query.get(template, 0) + 1

    by_domain = {
        domain: {
            "pages": seen["pages"],
            "pages_with_events": seen["pages_with_events"],
            "drafts": seen["drafts"],
            "candidates_new": new_per_domain.get(domain, 0),
            "mean_score": (sum(seen["scores"]) / len(seen["scores"]))
            if seen["scores"]
            else 0.0,
        }
        for domain, seen in observed.items()
    }

    read_per_query: dict[str, int] = {}
    local_per_query: dict[str, int] = {}
    for hit in pages:
        template = url_query.get(hit.url)
        if not template:
            continue
        read_per_query[template] = read_per_query.get(template, 0) + 1
        if source_domain(hit.url).endswith(settings.sweep_local_tld):
            local_per_query[template] = local_per_query.get(template, 0) + 1

    by_query = {
        template: {
            "pages": read_per_query.get(template, 0),
            "pages_with_events": events_per_query.get(template, 0),
            "candidates_new": new_per_query.get(template, 0),
            "local_domain_share": (
                local_per_query.get(template, 0) / read_per_query[template]
            )
            if read_per_query.get(template)
            else 0.0,
        }
        for template in queries
    }

    try:
        learning.record_sources(by_domain)
        learning.record_queries(by_query)
        learning.promote_queries()
    except Exception as e:
        # The store is an optimisation for the next sweep, never a reason to
        # lose this one's candidates.
        logger.warning(f"Could not record what the sweep learned: {e}")

    return SweepResult(
        city=city,
        candidates=candidates,
        stats={
            "queries": len(queries),
            "tavily_credits": tavily_calls,
            "trial_query": queries[-1] if queries else None,
            "domains": len(by_domain),
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
