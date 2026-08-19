"""The city sweep: search → extract → dedup → dry-run candidates.

Writes nothing. Each candidate carries its source URL and a dedup verdict so
the reviewer sees exactly what an approve would add; the writer's own probe
still guards the actual write.
"""

from datetime import datetime

from laiive_shared import EventDraft, missing_required
from laiive_shared.neo4j_writer import parse_start_at
from laiive_shared.normalize import norm
from loguru import logger
from pydantic import BaseModel

from agent import extraction, graph, tavily
from config import settings

# City name goes into every template; the templates stay English because
# Tavily handles the translation problem better than we would guess locales.
QUERY_TEMPLATES = [
    "live music concerts in {city} {month_year} agenda",
    "{city} concert venues upcoming gigs tickets",
]


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
    month_year = datetime.now().strftime("%B %Y")

    pages: list[tavily.SearchHit] = []
    seen_urls: set[str] = set()
    for template in QUERY_TEMPLATES:
        query = template.format(city=city, month_year=month_year)
        for hit in tavily.search(query, settings.sweep_results_per_query):
            if hit.url in seen_urls:
                continue
            seen_urls.add(hit.url)
            pages.append(hit)
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
