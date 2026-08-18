"""Extract EventDrafts from a fetched web page.

Cheap model first, gpt-4o only when mini comes back empty or unparseable on a
page whose search snippet plainly promised events (05-decisions: batch cost).
Tests patch `_client` (see tests/conftest.py).
"""

import json
from datetime import date

from laiive_shared import EventDraft
from laiive_shared.drafts import entries_from_json, entry_to_draft, strip_fences
from loguru import logger
from openai import OpenAI

from config import settings

_client = OpenAI(api_key=settings.openai_api_key)

EXTRACTION_PROMPT_VERSION = "search-v1"

EXTRACTION_PROMPT = """Extract upcoming live music events from this web page. Today is {today}.
The page was found searching for live music in {city}; its URL is {url}.

The page may be a venue agenda, a listings site, a festival page, or something
irrelevant. Return ONLY real, dated, upcoming live music events. Return JSON of
the form {{"events": [ ... ]}} — an empty list when the page has none — where
each entry carries ONLY the fields you can actually identify:
{{
  "name": string,            // event title if stated (do NOT invent one)
  "artists": [string, ...],  // performing artists/bands/DJs
  "start_at": "YYYY-MM-DDTHH:MM:SS", // resolve relative dates using today's date;
                                     // "YYYY-MM-DD" when no time is stated
  "venue": string,
  "address": string,         // street address if stated
  "city": string,
  "venue_type": "club" | "bar" | "concert_hall" | "arena" | "festival_site" | "open_air" | "other",  // only when the page says so — omit rather than guessing "other"
  "price_min": number,       // 0 for free events
  "price_max": number,       // only when a range is stated
  "price_currency": string,  // ISO code (EUR, USD...) only when stated or implied by symbol
  "description": string,     // short description in the page's own words
  "genre": string,           // lowercase-hyphenated slug, e.g. "indie-rock"
  "ticket_url": string       // only a URL actually on the page
}}

Rules:
- Skip past events, undated events, and anything that is not live music.
- One entry per event. Omit any field that is not present. NEVER invent data.
- Numbers for prices — no currency symbols.
- JSON only. No explanation, no markdown fences.

Page text:
{text}"""


def extract_events_from_page(text: str, *, url: str, city: str) -> list[EventDraft]:
    """LLM extraction over one page's text; [] when the page has no events."""
    text = text[: settings.page_max_chars]
    drafts = _extract(settings.extraction_model, text, url=url, city=city)
    if drafts is None:  # unparseable reply — the one "low confidence" signal we trust
        logger.info(f"Falling back to {settings.extraction_fallback_model} for {url}")
        drafts = _extract(settings.extraction_fallback_model, text, url=url, city=city)
    return drafts or []


def _extract(model: str, text: str, *, url: str, city: str) -> list[EventDraft] | None:
    """One extraction call; None signals a reply we could not parse at all."""
    response = _client.chat.completions.create(
        model=model,
        messages=[
            {
                "role": "user",
                "content": EXTRACTION_PROMPT.format(
                    today=date.today().isoformat(), city=city, url=url, text=text
                ),
            }
        ],
        temperature=0.0,
    )
    content = strip_fences(response.choices[0].message.content.strip())
    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        logger.warning(f"Unparseable extraction reply for {url}: {content[:200]}")
        return None
    return [
        draft
        for entry in entries_from_json(data)
        if (draft := entry_to_draft(entry)) is not None
    ]
