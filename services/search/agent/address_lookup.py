"""Find a venue's street address on the open web, for geocoding (D12 follow-up).

Nominatim answers a street address far more reliably than a venue name. The
bake-off (scripts/geocode_bakeoff.py) left 10 venues that no query form of the
name could resolve — all small independent rooms that OSM simply has no named
POI for — while only 26% of swept drafts carried an address at all. Rather than
adding a second geocoding provider, this recovers the missing *address* using
the Tavily client the sweep already depends on, and hands it back to Nominatim.

Only ever called on a geocode miss, and the answer is cached in the shared
geocode store, so a venue costs at most one search + one extraction, ever.
Tests patch `_client` (see tests/conftest.py).
"""

import json

from laiive_shared.drafts import strip_fences
from loguru import logger
from openai import OpenAI

from agent import tavily
from config import settings

_client = OpenAI(api_key=settings.openai_api_key)

SEARCH_RESULTS = 3
MAX_CHARS = 6000

ADDRESS_PROMPT = """From the search results below, find the street address of this venue:

Venue: {venue}
City: {city}

Return ONLY JSON: {{"address": "<street address>"}} or {{"address": null}}.

Rules:
- The address must be for THIS venue in THIS city. A same-name venue elsewhere
  is not a match — return null instead.
- Street and number at minimum; include the postcode when stated.
- Do NOT include the venue name in the address.
- Do NOT guess. If the results do not state an address, return null.

Search results:
{results}"""


def resolve_address(venue: str, city: str | None = None) -> str | None:
    """Best-effort street address for a venue; None when the web does not say.

    Never raises: a failure here must degrade to the city-centroid fallback,
    not fail an event submission.
    """
    if not venue:
        return None
    where = f" {city}" if city else ""
    hits = tavily.search(f"{venue}{where} venue address location", SEARCH_RESULTS)
    if not hits:
        return None

    results = "\n\n".join(
        f"{h.title}\n{h.url}\n{h.content}" for h in hits if h.title or h.content
    )[:MAX_CHARS]
    if not results.strip():
        return None

    try:
        response = _client.chat.completions.create(
            model=settings.extraction_model,
            messages=[
                {
                    "role": "user",
                    "content": ADDRESS_PROMPT.format(
                        venue=venue, city=city or "", results=results
                    ),
                }
            ],
            temperature=0,
        )
        payload = json.loads(strip_fences(response.choices[0].message.content or ""))
    except Exception as e:
        logger.warning(f"Address lookup failed for {venue!r}: {e}")
        return None

    address = payload.get("address") if isinstance(payload, dict) else None
    if not isinstance(address, str) or not address.strip():
        return None
    address = address.strip()
    # A bare city name or a one-word answer is not an address; it would geocode
    # to the centroid and read as a real venue pin.
    if len(address) < 6 or address.lower() == (city or "").lower():
        return None
    logger.info(f"Resolved address for {venue!r}: {address!r}")
    return address
