"""What discovery has learned about where to look and how to ask (Phase D).

Two things are learned from one signal — whether a page yielded real, future,
not-already-known events — and both steer the next sweep:

  * `search_sources`  which domains to hand Tavily as include/exclude, and
                      per-site instructions for the extraction prompt.
  * `search_queries`  which phrasings are worth a credit, and which trial
                      phrasing to spend the reserved slot on.

There is no human label in any of it. The default approve path selects every
`dedup_status == "new"` candidate, so an approval-derived signal would measure
the extractor and the dedup probe rather than anyone's judgement.

Counters decay instead of accumulating: each update is
`(previous * DECAY) + observed`. A three-week festival otherwise earns a
permanent promotion on one month's evidence, and a site that has gone quiet
keeps its rank forever. Plain PostgREST over httpx, same shape as reports.py.
Tests patch `_http` (see tests/conftest.py).
"""

from datetime import datetime, timezone

import httpx
from loguru import logger

from config import settings

_http = httpx.Client(timeout=15.0)

# Per-sweep decay. At 0.85 a single burst is down to a tenth of its weight
# after about fourteen sweeps, so a summer festival fades by autumn while a
# venue that lists every week holds its place.
DECAY = 0.85


def _url(table: str) -> str:
    return f"{settings.supabase_url.rstrip('/')}/rest/v1/{table}"


def _headers(**extra: str) -> dict[str, str]:
    key = settings.supabase_service_role_key
    return {"apikey": key, "Authorization": f"Bearer {key}", **extra}


class LearningStoreError(RuntimeError):
    """Supabase refused or failed."""


def _get(table: str, params: dict) -> list[dict]:
    response = _http.get(_url(table), headers=_headers(), params=params)
    if response.status_code != 200:
        raise LearningStoreError(f"Could not read {table} ({response.status_code})")
    return response.json()


def _upsert(table: str, rows: list[dict]) -> None:
    """Insert or replace whole rows. The caller has already merged the decay."""
    if not rows:
        return
    response = _http.post(
        _url(table),
        headers=_headers(
            **{
                "Content-Type": "application/json",
                "Prefer": "resolution=merge-duplicates,return=minimal",
            }
        ),
        json=rows,
    )
    if response.status_code not in (200, 201, 204):
        raise LearningStoreError(f"Could not write {table} ({response.status_code})")


def _merged(previous: dict | None, observed: dict, keys: tuple[str, ...]) -> dict:
    """previous * DECAY + observed, per counter."""
    out = {}
    for key in keys:
        old = float((previous or {}).get(key) or 0.0)
        out[key] = round(old * DECAY + float(observed.get(key) or 0.0), 4)
    return out


# ── Sources ──────────────────────────────────────────────────────────────────

SOURCE_COUNTERS = ("pages", "pages_with_events", "drafts", "candidates_new")

# A domain has to have been seen enough times before its rate means anything;
# one lucky page is not evidence. Both thresholds are deliberately arithmetic
# rather than a model — see the plan's D4.
TRUST_MIN_PAGES = 4.0
TRUST_MIN_YIELD = 0.4
BLOCK_MIN_PAGES = 6.0
BLOCK_MAX_YIELD = 0.05


# Sources the owner vouches for, from knowing the place rather than from any
# measurement. They bootstrap the ranking, which otherwise has to discover a
# good site by accident before it can prefer it — and they are exempt from
# being auto-blocked: if one of these stops yielding, that is an extraction
# problem to look at, not a verdict on the source.
#
# `agenda` is fetched with Tavily's extract endpoint rather than found by
# search, because search will not read these pages. Restricted to those three
# domains it answered with 106-156 characters each; extract returns 17,965 for
# Eppen's agenda and 102,313 for Daste's events page.
#
# `cities` is what keeps that affordable. These are province-wide sources, so
# extracting them once while sweeping Bergamo is enough — doing it for all ten
# towns in the province would be the same pages fetched ten times.
#
# Bergamo. Druso in Ranica is the province's main live club; Daste is the
# cultural centre in the old Daste e Spalenga power station; Eppen is L'Eco di
# Bergamo's events agenda, which is the paper's own domain rather than a
# separate one — it covers the whole province, so it is the broadest of them.
# Dieci10 is a live-music restaurant with a second room in Grassobbio. The
# clubs are here because Eppen does not carry them: none of them appeared
# among its 85 music events on 2026-09-19.
#
# `depth` is the extract depth, 'basic' unless a source needs otherwise. It is
# per source because neither setting is safe for all of them: advanced failed
# outright on Druso where basic worked, and basic strips Eppen's listing down
# to titles (see its entry). `tail_chars` is for a page that keeps its
# programme at the end, behind an archive (see Daste's). `date_first` says
# the page's entries open with their date, which is what lets a long one be
# read in chunks of whole entries (extraction._entry_chunks); it is said
# here and never guessed, because on a page that puts the title first a cut
# at a date line parts every title from its date.
#
# Deliberately absent: Ink Club, https://www.inkclub.bergamo.it/calendario. The
# page reads fine and the extractor cannot date it. It is one month heading
# ("Luglio") and then "GIO 2", "VEN 3"... running on into the next month with
# no new heading, and shown that on 2026-09-19 — still July's programme — both
# gpt-4o-mini and gpt-4o, with and without a hint spelling the format out,
# moved the nights to September and October, "2026-09-31" among them. A source
# that turns a stale page into future gigs is worse than no source. It needs
# the dates resolved in code before the model sees them.
SEED_SOURCES: dict[str, dict] = {
    "drusobg.com": {
        "cities": ["Bergamo"],
        # Moved here from drusobg.it, which stopped resolving (NXDOMAIN on
        # 2026-09-19) and had been failing every sweep in silence since.
        # /event-list is the whole upcoming programme as "name, sab 19 set,
        # Druso": 17 of its 18 nights came back, rightly dated, and the one
        # left out was a flea market. The home page is its first three.
        "agenda": ["https://www.drusobg.com/event-list"],
    },
    "dastebergamo.com": {
        "cities": ["Bergamo"],
        # /spazio-eventi/ is the venue-hire pitch, not a listing. This page is
        # every event since 2021, oldest first, and what is coming up is the
        # LAST 1,800 of its 104,000 characters — so the head cut that every
        # page used to get read a vouched source and found nothing, each
        # sweep. Only the end is read, and not for the cost: the 2021 entries
        # give a day and no year ("Il 16 novembre"), and read whole the model
        # turned three of them into next November's gigs. The recent past that
        # 4,000 characters still reaches carries its year, and is dropped; it
        # is one call's worth, so the upcoming nights are never skimmed over.
        "tail_chars": 4000,
        "agenda": ["https://www.dastebergamo.com/eventi/"],
    },
    "ecodibergamo.it": {
        "cities": ["Bergamo"],
        # The music listing rather than /eventi/eppen/, which mixes every
        # category. Advanced, at twice the price, because basic keeps each
        # event's title and blurb and DROPS its date, hour, venue and town:
        # the model then dated every one of them "tomorrow". Measured on this
        # URL, 2026-09-19: basic has "Settembre" 0 times, advanced 44.
        # ponytail: two pages is the whole listing today ("Pagina 1 di 2", 85
        # events) and a third is not followed. Read the page count off the
        # first page when the listing outgrows this.
        "depth": "advanced",
        # "19 Sab Settembre h.11:00 / 13:00", then the venue, then the title.
        "date_first": True,
        "agenda": [
            "https://www.ecodibergamo.it/eventi/eppen/ricerca/?q=&start_date=&end_date=&category=musica&city=",
            "https://www.ecodibergamo.it/eventi/eppen/ricerca/?q=&page=2&start_date=&end_date=&category=musica&city=",
        ],
    },
    "livemusicdieci10.it": {
        "cities": ["Bergamo"],
        # One page for both rooms; the programme is its #tour-eventi section,
        # dated DD.MM.YY, and every live is free entry.
        "agenda": ["https://livemusicdieci10.it/"],
    },
}


def programme_of(domain: str, text: str) -> str:
    """The part of a vouched page that is its programme: all of it, unless the
    source says its programme is at the end (`tail_chars`)."""
    tail = SEED_SOURCES.get(domain, {}).get("tail_chars")
    return text[-tail:] if tail else text


def date_first(domain: str) -> bool:
    """Whether this vouched source says its entries open with their date."""
    return bool(SEED_SOURCES.get(domain, {}).get("date_first"))


def agenda_urls(city: str, depth: str = "basic") -> list[str]:
    """Pages to fetch outright while sweeping this city, at one extract depth."""
    urls = []
    for seed in SEED_SOURCES.values():
        if city in seed.get("cities", []) and seed.get("depth", "basic") == depth:
            urls.extend(seed.get("agenda", []))
    return urls


def _source_status(row: dict) -> str:
    """trusted / blocked / candidate, from the decayed counters alone."""
    pages = float(row.get("pages") or 0.0)
    yield_rate = float(row.get("pages_with_events") or 0.0) / pages if pages else 0.0
    if pages >= TRUST_MIN_PAGES and yield_rate >= TRUST_MIN_YIELD:
        return "trusted"
    if pages >= BLOCK_MIN_PAGES and yield_rate <= BLOCK_MAX_YIELD:
        return "blocked"
    return "candidate"


def _seeded(domain: str) -> bool:
    """A vouched source, or a subdomain of one."""
    return any(domain == seed or domain.endswith("." + seed) for seed in SEED_SOURCES)


def record_sources(by_domain: dict[str, dict]) -> None:
    """Fold one sweep's per-domain observations into the store."""
    if not by_domain:
        return
    domains = sorted(by_domain)
    previous = {
        row["domain"]: row
        for row in _get(
            "search_sources",
            {"domain": f"in.({','.join(domains)})", "select": "*"},
        )
    }
    rows = []
    for domain in domains:
        before = previous.get(domain)
        row = {"domain": domain, **_merged(before, by_domain[domain], SOURCE_COUNTERS)}
        row["mean_score"] = round(float(by_domain[domain].get("mean_score") or 0.0), 4)
        row["last_seen_at"] = datetime.now(timezone.utc).isoformat()
        # Blocked is sticky against the owner's hand: a domain the owner sets
        # to blocked is not un-blocked by a good week. Only the store decides
        # 'trusted' and 'candidate'.
        if before and before.get("status") == "blocked":
            row["status"] = "blocked"
        elif _seeded(domain):
            # Vouched for by hand, so it starts trusted and never falls out of
            # the focused slot on a quiet fortnight.
            row["status"] = "trusted"
        else:
            row["status"] = _source_status(row)
        # Carried through the upsert, which replaces the whole row.
        row["extraction_hints"] = (before or {}).get("extraction_hints") or ""
        row["events_written"] = float((before or {}).get("events_written") or 0.0)
        if before and before["status"] != row["status"]:
            logger.info(
                f"source {domain}: {before['status']} -> {row['status']} "
                f"(pages={row['pages']:.1f}, with_events={row['pages_with_events']:.1f})"
            )
        rows.append(row)
    _upsert("search_sources", rows)


def record_writes(domains: list[str]) -> None:
    """Count events that actually reached the graph, per source domain.

    The one signal here that is not about a page being parseable: it survives
    the writer's own duplicate and validity probes, so a site whose listings
    look right but never survive a write stops looking good. Not decayed --
    this is a tally of what exists, not a measure of current relevance.
    """
    if not domains:
        return
    unique = sorted(set(d for d in domains if d))
    if not unique:
        return
    try:
        previous = {
            row["domain"]: row
            for row in _get(
                "search_sources",
                {"domain": f"in.({','.join(unique)})", "select": "*"},
            )
        }
        rows = []
        for domain in unique:
            before = previous.get(domain)
            if not before:
                # A domain the sweep never recorded cannot be scored on a write
                # alone, and inventing a row here would create one with no
                # pages behind it.
                continue
            rows.append(
                {
                    **before,
                    "events_written": float(before.get("events_written") or 0.0)
                    + domains.count(domain),
                }
            )
        _upsert("search_sources", rows)
    except Exception as e:
        logger.warning(f"Could not record writes by source: {e}")


def domain_filters(city: str, limit: int = 50) -> tuple[list[str], list[str]]:
    """(include, exclude) for the next Tavily call, for this city's sweep.

    Include is deliberately capped and never used alone — the caller keeps
    unrestricted slots, or the list ossifies around whatever it found first.
    """
    try:
        rows = _get(
            "search_sources",
            {
                "status": "in.(trusted,blocked)",
                "select": "domain,status",
                "order": "candidates_new.desc",
                "limit": str(limit),
            },
        )
    except Exception as e:
        # A ranking that cannot be read is not a reason to skip the sweep, and
        # that holds for a dead socket as much as a refusal.
        logger.warning(f"Could not read source ranking: {e}")
        return [], []
    # .get throughout: these two reads ask for different column sets from the
    # same table, and PostgREST returns exactly what was selected.
    include = [r["domain"] for r in rows if r.get("status") == "trusted"]
    exclude = [r["domain"] for r in rows if r.get("status") == "blocked"]
    # The seeds hold from the first sweep, before anything has been recorded --
    # which is the whole point of vouching for them. Ordered first so a capped
    # include list never drops them. But only THIS city's seeds: every seed is
    # vouched for somewhere, and prepending all of them made the first-slot
    # focus guard fire for every city, so Torino's best-earning query ran
    # restricted to Bergamo-only sites — a guaranteed zero that then counted
    # against the phrasing's yield.
    local_seeds = [
        d for d, seed in SEED_SOURCES.items() if city in seed.get("cities", [])
    ]
    include = local_seeds + [d for d in include if not _seeded(d)]
    exclude = [d for d in exclude if not _seeded(d)]
    return include, exclude


def extraction_hints() -> dict[str, str]:
    """domain -> per-site instructions, for the extraction prompt."""
    try:
        rows = _get(
            "search_sources",
            {"extraction_hints": "neq.", "select": "domain,extraction_hints"},
        )
    except Exception as e:
        logger.warning(f"Could not read extraction hints: {e}")
        return {}
    return {
        r["domain"]: r["extraction_hints"] for r in rows if r.get("extraction_hints")
    }


# ── Queries ──────────────────────────────────────────────────────────────────

QUERY_COUNTERS = ("pages", "pages_with_events", "candidates_new")

# A trial phrasing gets this many runs before it is judged, so one quiet week
# in one town cannot retire a good one.
QUERY_MIN_RUNS = 3


def record_queries(by_query: dict[str, dict]) -> None:
    """Fold one sweep's per-query observations into the store."""
    if not by_query:
        return
    templates = sorted(by_query)
    previous = {
        row["template"]: row
        for row in _get("search_queries", {"select": "*", "limit": "500"})
        if row["template"] in templates
    }
    rows = []
    for template in templates:
        before = previous.get(template)
        row = {
            "template": template,
            **_merged(before, by_query[template], QUERY_COUNTERS),
            "runs": int((before or {}).get("runs") or 0) + 1,
            "local_domain_share": round(
                float(by_query[template].get("local_domain_share") or 0.0), 4
            ),
            "status": (before or {}).get("status") or "trial",
            "last_used_at": datetime.now(timezone.utc).isoformat(),
        }
        rows.append(row)
    _upsert("search_queries", rows)


def _query_yield(row: dict) -> float:
    """New candidates per credit — one run is one credit, by construction."""
    runs = int(row.get("runs") or 0)
    return float(row.get("candidates_new") or 0.0) / runs if runs else 0.0


def promote_queries() -> None:
    """Standing phrasings earn their slot; a trial that beats them takes one.

    Arithmetic, not a model: a trial with enough runs and a yield at or above
    the standing median becomes standing, and a standing one below a fifth of
    that median retires. Every transition is logged, because a vocabulary that
    reclassifies itself silently is one nobody can debug later.
    """
    try:
        rows = _get("search_queries", {"select": "*", "limit": "500"})
    except Exception as e:
        logger.warning(f"Could not read query ranking: {e}")
        return

    ready = [r for r in rows if int(r.get("runs") or 0) >= QUERY_MIN_RUNS]
    standing = [r for r in ready if r["status"] == "standing"]
    if not standing:
        # Nothing to compare against yet: the first phrasings to reach the
        # minimum become the baseline rather than being judged against zero.
        baseline = 0.0
    else:
        yields = sorted(_query_yield(r) for r in standing)
        baseline = yields[len(yields) // 2]

    changed = []
    for row in ready:
        rate = _query_yield(row)
        status = row["status"]
        if status == "trial" and rate >= baseline:
            new_status = "standing"
        elif status == "standing" and standing and rate < baseline * 0.2:
            new_status = "retired"
        else:
            continue
        logger.info(
            f"query {row['template']!r}: {status} -> {new_status} "
            f"({rate:.2f} new/credit vs baseline {baseline:.2f})"
        )
        changed.append({**row, "status": new_status})
    _upsert("search_queries", changed)


def select_trial(candidates: list[str]) -> str | None:
    """The least-tested phrasing that has not been retired.

    Round-robin rather than a score, because the point of the slot is coverage:
    a phrasing with no runs has no score to rank it by, and the ones already
    winning do not need the exploration.
    """
    if not candidates:
        return None
    try:
        rows = {
            r["template"]: r
            for r in _get("search_queries", {"select": "template,status,runs"})
        }
    except Exception as e:
        logger.warning(f"Could not read query pool: {e}")
        return candidates[0]
    # Not retired — that phrasing lost its probation — and not standing
    # either: a promoted phrasing already earns a standing slot, and keeping
    # it eligible here ran the identical query twice in one sweep (the second
    # call's results all fell to seen_urls, so it was a credit spent on
    # nothing) and double-counted its runs against its yield.
    live = [
        c
        for c in candidates
        if (rows.get(c) or {}).get("status") not in ("retired", "standing")
    ]
    if not live:
        return None
    return min(live, key=lambda c: int((rows.get(c) or {}).get("runs") or 0))


def standing_templates(fallback: list[str], limit: int) -> list[str]:
    """The best-earning phrasings, or the file's list before anything is known."""
    try:
        rows = _get(
            "search_queries",
            {
                "status": "eq.standing",
                "select": "template,candidates_new,runs",
                "order": "candidates_new.desc",
                "limit": str(limit),
            },
        )
    except Exception as e:
        logger.warning(f"Could not read standing queries: {e}")
        return fallback[:limit]
    return [r["template"] for r in rows if r.get("template")] or fallback[:limit]
