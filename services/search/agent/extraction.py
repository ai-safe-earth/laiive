"""Extract EventDrafts from a fetched web page.

Cheap model first, gpt-4o only when mini comes back empty or unparseable on a
page whose search snippet plainly promised events (05-decisions: batch cost).
Tests patch `_client` (see tests/conftest.py).
"""

import json
import re
from datetime import date

from laiive_shared import EventDraft
from laiive_shared.drafts import entries_from_json, entry_to_draft, strip_fences
from loguru import logger
from openai import OpenAI

from config import settings

_client = OpenAI(api_key=settings.openai_api_key)

# v2 spells out what "live music" means. "Skip anything that is not live music"
# alone let every one of Ink Club's ten non-music nights through (tournaments,
# a screen-printing lab, closing-down drinks); with the list below, one or two.
# It keeps 9 to 12 of the page's 12 music nights, varying from run to run: what
# it drops is a night whose title is not the music ("LOCK IN: RESIDENZA
# ARTISTICA", then "a seguire SYNTH CAFE': OPEN JAM"). Placing the list just
# before the page text instead varied the same way. On the other vouched pages
# it dropped four listings and added none: a photo exhibition and a
# science-fair schools day, rightly, and a choir workshop with a live orchestra
# and Druso's "Balera" with no act named, which are arguable. Measured
# 2026-09-19 (evals/inkclub_dates/live_page.py).
EXTRACTION_PROMPT_VERSION = "search-v2"

# How much of a searched page reaches the model. A constant rather than a
# setting: SEARCH_PAGE_MAX_CHARS was never set anywhere, and this is its only
# reader. A vouched agenda is chunked instead — see AGENDA_MAX_CHUNKS.
PAGE_MAX_CHARS = 12000

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
  "price_min": number,       // OMIT unless a price is stated. 0 means the page
                             // says free/gratis, never "no price found"
  "price_max": number,       // only when a range is stated
  "price_currency": string,  // ISO code (EUR, USD...) only when stated or implied by symbol
  "description": string,     // short description in the page's own words
  "genre": string,           // lowercase-hyphenated slug, e.g. "indie-rock"
  "ticket_url": string       // only a URL actually on the page
}}

Rules:
- Skip past events, undated events, and anything that is not live music.
- Live music means a concert or band night, a DJ set, a jam session, or a singer,
  choir or ensemble performing for an audience. It does NOT include, even at a
  music venue: tournaments and games, workshops, courses, laboratories and artist
  residencies, talks, readings and screenings, markets, swap parties and clothes
  exchanges, drinks or closing nights (for example "ultimo giro"), and parties
  with no music act named. When an entry mixes the two (a swap party with a DJ
  set, a residency followed by an open jam), keep it, and name the music act.
- One entry per event. Omit any field that is not present. NEVER invent data.
- Numbers for prices — no currency symbols.
- A missing price is not a free event. Leave price_min out entirely unless the
  page states an amount or says the entry is free.
- JSON only. No explanation, no markdown fences.
{hint}
Page text:
{text}"""


# How a vouched page is read, and the three ways that were built, measured and
# thrown away first (2026-09-19; Eppen's first music page, ~48 events, truth
# read off the page's own date lines; and evals/inkclub_dates).
#
# The model skims a long list: asked for all of Eppen at once it returned 16.
# It has to be shown less at a time — and everything turns on WHERE the text is
# cut, because the model is only reliable asked one plain question about one
# block of whole entries:
#
# - Overlapping character windows: full recall, wrong dates. An entry's date
#   sits on its own line above its title, a window's edge falls between the
#   two, and shown a title whose date was cut away the model gave it the NEXT
#   entry's date and carried the slip on: 2 wrong of 48 at one cut, 9 of 41 at
#   another. Margins, line-snapped cuts and telling it the text was a slice
#   changed nothing.
# - The whole page in every call, events asked for twelve at a time ("the next
#   twelve after «X»"): right dates, until the page ran out. Asked for more
#   when there was no more, it did not answer "none" — it re-listed March's
#   nights with May dates, and on a stale page invented "HIP HOP NIGHT" and
#   "REGGAE PARTY" outright. Resuming by exclusion instead ("not in this
#   list") stopped at 21 of 48.
#
# So: cut ONLY at a line that opens with a date, which in a date-first listing
# is where an entry begins. Every chunk is whole entries, no overlap, one plain
# question each, and nothing that asks for "more". The size is measured too:
# chunks of 4,000 characters (a dozen entries) brought back 39 of Eppen's 48,
# 2,500 brought 41, and 1,500 — four or five entries — all 48. Every date
# right at every size, nothing invented, and the same answer run after run.
AGENDA_CHUNK_CHARS = 1500
# ponytail: a ceiling on calls per page (~45,000 characters). What falls off is
# the END. A page that long is long because it carries an archive, and an
# archive is worse read than unread: Daste's 2021 entries give a day and no
# year ("Il 16 novembre") and were dated as upcoming. Such a source says where
# its programme is (learning.SEED_SOURCES, `tail_chars`) instead of this
# growing.
AGENDA_MAX_CHUNKS = 30

# A date, in the ways a listing writes one: 2026-09-19, 18.09 or 18/09/2026,
# "19 settembre" / "19 Sab Settembre" / "Sept 19", and "sab 19" or "GIO 2club".
# Deliberately loose: it finds where entries begin and tells a listing from a
# page whose dates were lost on the way here. It never supplies a date.
_IT_MONTHS = "gen|feb|mar|apr|mag|giu|lug|ago|set|ott|nov|dic"
_EN_MONTHS = "jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec"
_WEEKDAYS = "lun|mar|mer|gio|ven|sab|dom"
_DATE = re.compile(
    r"\b\d{4}-\d{2}-\d{2}\b"
    r"|\b(?:0?[1-9]|[12]\d|3[01])[./](?:0?[1-9]|1[0-2])(?![\d:])"
    rf"|\b\d{{1,2}}°?\s+(?:(?:{_WEEKDAYS})[a-zì]*\s+)?(?:{_IT_MONTHS}|{_EN_MONTHS})[a-z]*\b"
    rf"|\b(?:{_EN_MONTHS})[a-z]*\s+\d{{1,2}}(?!\d)"
    rf"|\b(?:{_WEEKDAYS})[a-zì]*\.?\s+\d{{1,2}}(?!\d)",
    re.IGNORECASE,
)


def _dated(text: str) -> bool:
    """Whether the text carries dates at the rate a listing does.

    One for every 2,000 characters, which every vouched page clears many times
    over (Eppen one per 340, Dieci10 one per 520, Druso one per 70). What does
    not clear it is a page whose dates were stripped before it got here:
    Tavily's advanced extract sometimes answers with its basic text, and
    Eppen's then has 2 date-like tokens in 10,854 characters. Read anyway, the
    model invents a date for every title — Oct 1, Oct 2, Oct 3, down the list.
    """
    return len(_DATE.findall(text)) * 2000 >= len(text)


def _entry_chunks(text: str) -> list[str]:
    """The text in chunks of whole entries: cut only where a line opens with a date."""
    chunks: list[str] = []
    current = ""
    for line in text.splitlines(keepends=True):
        opens_entry = _DATE.match(line.lstrip()) is not None
        if opens_entry and current and len(current) + len(line) > AGENDA_CHUNK_CHARS:
            chunks.append(current)
            current = ""
        current += line
    chunks.append(current)
    return chunks[:AGENDA_MAX_CHUNKS]


def _extract_with_fallback(
    text: str, *, url: str, city: str, hint: str
) -> list[EventDraft]:
    drafts = _extract(settings.extraction_model, text, url=url, city=city, hint=hint)
    if drafts is None:  # unparseable reply — the one "low confidence" signal we trust
        logger.info(f"Falling back to {settings.extraction_fallback_model} for {url}")
        drafts = _extract(
            settings.extraction_fallback_model, text, url=url, city=city, hint=hint
        )
    return drafts or []


def extract_events_from_page(
    text: str,
    *,
    url: str,
    city: str,
    hint: str = "",
    vouched: bool = False,
    date_first: bool = False,
) -> list[EventDraft]:
    """LLM extraction over one page's text; [] when the page has no events.

    `hint` is whatever search_sources holds for this page's domain — a note
    about how that particular site lays its listings out. Empty for a domain
    nobody has written one for, which is all of them until somebody does.

    `vouched` is a page somebody vouched for. It is refused when its text has
    lost its dates (see _dated), because then every date would be invented.
    `date_first` is the source saying its entries OPEN with their date, which
    is what lets a long listing be read in chunks of whole entries (see
    AGENDA_CHUNK_CHARS). It is the source's to say, and not guessed: on a page
    that puts the title first, a cut at a date line parts every title from its
    date. Anything else is one call over the first page_max_chars.
    """
    if vouched and not _dated(text):
        # Loud, because somebody vouched for this page: read in silence as
        # "nothing on", it is how Daste and Druso went unnoticed for weeks.
        logger.warning(
            f"{url}: its text carries almost no dates, so it was not read - "
            "any date taken from it would be invented. A bad fetch, most likely."
        )
        return []
    if not (vouched and date_first):
        return _extract_with_fallback(
            text[:PAGE_MAX_CHARS], url=url, city=city, hint=hint
        )
    drafts: list[EventDraft] = []
    for chunk in _entry_chunks(text):
        drafts.extend(_extract_with_fallback(chunk, url=url, city=city, hint=hint))
    return drafts


def _extract(
    model: str, text: str, *, url: str, city: str, hint: str = ""
) -> list[EventDraft] | None:
    """One extraction call; None signals a reply we could not parse at all."""
    response = _client.chat.completions.create(
        model=model,
        messages=[
            {
                "role": "user",
                "content": EXTRACTION_PROMPT.format(
                    today=date.today().isoformat(),
                    city=city,
                    url=url,
                    text=text,
                    # Its own paragraph when present, nothing at all when not —
                    # an empty "Notes:" heading reads as an instruction to the
                    # model to find something that is not there.
                    hint=(f"\nNotes on this site:\n{hint}\n" if hint else ""),
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
