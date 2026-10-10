"""Turn classifier — one cheap structured-output call per turn (02-arch §3).

Emits the query type, the conversational moment, and the FULL resolved
constraint state (previous constraints ± this turn's changes), split into
atomic sub-queries. The chat sends the previous turn's searches back, and on a
refinement `merge_previous` keeps whatever this turn left out, so refinements
("cheaper", "what about Berlin instead?") work without server-side sessions.
"""

import json
from datetime import datetime, timedelta, timezone as utc_timezone
from typing import Literal, Optional
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from laiive_shared import DEFAULT_LANGUAGE, DETECTION_RULE, normalize_language
from loguru import logger
from pydantic import BaseModel, ValidationError, field_validator

from config import settings

from .utils.llm_utils import get_openai_client

CLASSIFIER_PROMPT_VERSION = "v7"

CLASSIFIER_SYSTEM_PROMPT = """You are the query classifier of a live music events assistant backed by a graph database.

Today is {today} ({weekday}), {time} on the user's clock. The user's location is {location_note}.
The previous search in this conversation was: {previous}.

Read the conversation and the latest user message, then return ONE JSON object:

{{
  "query_type": "event_search" | "smalltalk" | "out_of_scope",
  "moment": "first_query" | "refinement" | "new_topic" | "ambiguous",
  "language": string,          // ISO 639-1 code of the LATEST user message
  "sub_queries": [Constraints, ...],
  "cleared": [string, ...],    // constraint names this turn REMOVES ("any genre" → ["genre"])
  "clarification": string or null
}}

Constraints object (every field optional, omit or null when not constrained):
{{
  "query_text": string,        // this atomic ask, in the user's words
  "city": string,              // where, at city scale or smaller, e.g. "Madrid"
  "country_code": string,      // ISO-3166-1 alpha-2 when a COUNTRY is asked, e.g. "ES"
  "genre": string,             // genre slug: lowercase, hyphenated, e.g. "indie-rock"
  "artist": string,
  "venue": string,
  "venue_type": "club" | "bar" | "concert_hall" | "arena" | "festival_site" | "open_air" | "other",
  "time_words": string,        // FIRST copy the user's time words verbatim, e.g. "next friday night"
  "when": string,              // THEN name them (see the rule below); never compute a date
  "near_me": boolean,          // the user means their own position
  "radius_km": number,         // "near/around/vicino a/cerca de X": the distance given, else 30
  "free_text": string,         // fuzzy/vibe ask for semantic search, e.g. "intimate candle-lit jazz"
  "price_max": number,
  "needs_custom_cypher": boolean  // aggregations or asks the fields above cannot express
}}

Rules:
- RE-EMIT THE FULL CONSTRAINT STATE: start from the constraints implied by the
  conversation so far, then apply this turn's additions/changes/removals.
  "cheaper" edits price_max; "what about Berlin?" replaces the city and keeps
  the rest; a completely different request is moment "new_topic" and starts clean.
- A follow-up that does not start a different request is a "refinement" of the
  previous search, even after "nothing found" and even when it only names a
  show or asks for "other" events. On a refinement, anything you leave out is
  kept from the previous search; to drop something, name it in `cleared`.
- Split multi-intent asks into several sub_queries entries
  (e.g. "jazz tonight and anything by Klangfeld this month" → two).
- `when` names the time; code turns it into dates, so never do calendar maths.
  Use exactly one of: "now", "tonight", "today", "tomorrow", "this_weekend",
  "next_weekend", "this_week", "next_week", "this_month", "next_month", a
  weekday ("friday"), a date "YYYY-MM-DD", a month "YYYY-MM", or a range of any
  two of these joined by ".." ("tomorrow..sunday", "2026-12-20..2026-12-31").
  "este finde" / "questo weekend" → "this_weekend"; "giovedì" → "thursday";
  "between friday and monday" → "friday..monday". Translate each time word
  in `time_words` to its name, word for word; write "YYYY-MM-DD" only when the
  user typed a calendar date ("on the 24th", "24 ottobre"). Code does all the
  calendar maths. No time word → no `when`. Never invent one.
- near_me is true only when the user means their OWN position ("near me",
  "nearby", "around here"). "near X", "around X", "towns near X", "X and its
  province" name a place: city X, near_me false, radius_km the distance they
  gave, else 30. "gigs near Bergamo" → city "Bergamo", radius_km 30;
  "concerti vicino a Lecco" → city "Lecco", radius_km 30. A place named in this
  turn replaces an earlier near_me and keeps the rest (genre, dates).
- Cities carry their LOCAL name, never the exonym the user happened to use:
  "Barcellona"/"Barcelone" → "Barcelona", "Londres" → "London", "Múnich" →
  "München". The graph matches city names exactly, so an exonym finds nothing.
- A place SMALLER than a city — a neighbourhood, barrio, district or a landmark
  ("Kreuzberg", "Malasaña", "El Raval", "near Sagrada Família") — goes in `city`
  too; it is still the answer to "where". Keep the parent city with it when the
  user gave one ("Kreuzberg, Berlin"), because the same neighbourhood name
  exists in several countries. Never leave a place in `free_text`.
- A music genre named anywhere in the ask ALWAYS becomes `genre`, as a slug,
  however terse the phrasing: "jazz in Madrid" is genre "jazz" + city "Madrid".
  Never drop it, and never leave it in `free_text` alone — `free_text` is for
  vibes that are not a genre ("intimate candle-lit", "something loud").
- "free" / "gratis" / "gratuito" means price_max 0. Never drop it.
- A message that is only a place name ("Granada") is a search in that place:
  one sub_query with that city, moment as usual.
- moment "ambiguous" + clarification: the search cannot run without ONE more
  detail (e.g. no place and no location share). "find me something" has no
  place, no genre, no artist, no date: that is ambiguous, ask for the place.
  Phrase clarification as the missing thing, not a full sentence to parrot.
  An ambiguous search still fills sub_queries with what WAS said (dates, genre,
  artist), so it can run as soon as the missing detail arrives.
- smalltalk covers greetings/thanks/goodbyes; out_of_scope is anything not
  about live music events. Both need no sub_queries.
- language: {language_rule} A follow-up in a new language switches it.
- JSON only. No prose, no markdown fences."""


class Constraints(BaseModel):
    query_text: Optional[str] = None
    city: Optional[str] = None
    country_code: Optional[str] = None
    genre: Optional[str] = None
    artist: Optional[str] = None
    venue: Optional[str] = None
    venue_type: Optional[str] = None
    # Named by the model, turned into date_from/date_to by resolve_when().
    when: Optional[str] = None
    date_from: Optional[str] = None
    date_to: Optional[str] = None
    near_me: bool = False
    radius_km: Optional[float] = None
    free_text: Optional[str] = None
    price_max: Optional[float] = None
    needs_custom_cypher: bool = False

    @field_validator("near_me", "needs_custom_cypher", mode="before")
    @classmethod
    def _null_bool_is_false(cls, v):
        return False if v is None else v

    def is_empty(self) -> bool:
        return not any(
            [
                self.city,
                self.country_code,
                self.genre,
                self.artist,
                self.venue,
                self.venue_type,
                self.date_from,
                self.date_to,
                self.near_me,
                self.free_text,
                self.price_max is not None,
            ]
        )


class Classification(BaseModel):
    # No "nearby": route() reads near_me, so a separate type was a value
    # nothing used. A model that still says it means an event search.
    query_type: Literal["event_search", "smalltalk", "out_of_scope"]
    moment: Literal["first_query", "refinement", "new_topic", "ambiguous"]
    # Decided here so the composer is told the language instead of inferring it
    # from a result set full of Spanish venue names (laiive_shared.language).
    language: str = DEFAULT_LANGUAGE
    sub_queries: list[Constraints] = []
    # Constraint names this turn removes, so the merge does not put them back.
    cleared: list[str] = []
    clarification: Optional[str] = None

    @field_validator("query_type", mode="before")
    @classmethod
    def _nearby_is_a_search(cls, v):
        return "event_search" if v == "nearby" else v

    @field_validator("language", mode="before")
    @classmethod
    def _clean_language(cls, v):
        return normalize_language(v)


# Kept from the previous search on a refinement. Each group carries over whole
# or not at all: "and in Torino?" after a venue in Bergamo must not keep the
# venue, and a new "from" date must not pair with the old "to".
CARRIED_GROUPS = [
    ("city", "country_code", "venue", "near_me"),
    ("radius_km",),
    ("date_from", "date_to"),
    ("genre",),
    ("artist",),
    ("venue_type",),
    ("free_text",),
    ("price_max",),
]
# Client-carried text is capped before it reaches a prompt or a query.
PREVIOUS_TEXT_MAX = 80


def previous_searches(raw: list[dict] | None) -> list[Constraints]:
    """The previous turn's searches as the chat sent them back.

    Hostile input: the chat is ours, but the request is anyone's. Only the
    carried fields survive, as validated Constraints with short strings; never
    `needs_custom_cypher` or `query_text`, which steer the LLM-written query.
    """
    keep = {name for group in CARRIED_GROUPS for name in group}
    out = []
    for item in (raw or [])[:5]:
        if not isinstance(item, dict):
            continue
        fields = {
            k: v[:PREVIOUS_TEXT_MAX] if isinstance(v, str) else v
            for k, v in item.items()
            if k in keep
        }
        try:
            out.append(Constraints(**fields))
        except ValidationError:
            continue
    return out


WEEKDAYS = [
    "monday",
    "tuesday",
    "wednesday",
    "thursday",
    "friday",
    "saturday",
    "sunday",
]
# A night out ends at 06:00 the next morning, so a 01:00 DJ set is "tonight".
NIGHT_END = 6


def _span(start: datetime, last_day: datetime) -> tuple[datetime, datetime]:
    """From `start` to 06:00 after `last_day`. The executor's end is exclusive."""
    end = last_day.replace(hour=NIGHT_END, minute=0, second=0, microsecond=0)
    return start, end + timedelta(days=1)


def _month_start(d: datetime, months_ahead: int = 0) -> datetime:
    month = d.month - 1 + months_ahead
    return d.replace(
        year=d.year + month // 12,
        month=month % 12 + 1,
        day=1,
        hour=0,
        minute=0,
        second=0,
        microsecond=0,
    )


def _resolve(when: str, now: datetime) -> tuple[datetime, datetime] | None:
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    # Before 06:00 the night before is still going: "tonight" at 01:00 is now.
    night = today - timedelta(days=1) if now.hour < NIGHT_END else today
    days_to_friday = (4 - today.weekday()) % 7
    # Friday to Sunday; asked during the weekend, it starts today.
    friday = today if today.weekday() >= 4 else today + timedelta(days=days_to_friday)
    monday = today + timedelta(days=7 - today.weekday())
    if when == "now":
        return _span(now.replace(second=0, microsecond=0), night)
    if when == "tonight":
        return _span(
            max(now, night.replace(hour=18)).replace(second=0, microsecond=0), night
        )
    if when == "today":
        return _span(today, today)
    if when == "tomorrow":
        return _span(today + timedelta(days=1), today + timedelta(days=1))
    if when == "this_weekend":
        return _span(friday, monday - timedelta(days=1))
    if when == "next_weekend":
        next_friday = monday + timedelta(days=4)
        return _span(next_friday, next_friday + timedelta(days=2))
    if when == "this_week":
        return _span(today, monday - timedelta(days=1))
    if when == "next_week":
        return _span(monday, monday + timedelta(days=6))
    if when == "this_month":
        return _span(today, _month_start(today, 1) - timedelta(days=1))
    if when == "next_month":
        return _span(_month_start(today, 1), _month_start(today, 2) - timedelta(days=1))
    if when in WEEKDAYS:
        day = today + timedelta(days=(WEEKDAYS.index(when) - today.weekday()) % 7)
        return _span(day, day)
    try:
        day = datetime.strptime(when, "%Y-%m-%d").replace(tzinfo=now.tzinfo)
        return _span(day, day)
    except ValueError:
        pass
    try:
        first = datetime.strptime(when, "%Y-%m").replace(tzinfo=now.tzinfo)
    except ValueError:
        return None
    return _span(max(first, today), _month_start(first, 1) - timedelta(days=1))


def resolve_when(when: str, now: datetime) -> tuple[str, str] | None:
    """A named time ("this_weekend", "friday..sunday") as dates on the user's clock.

    The model names the interval and this does the calendar maths (owner,
    2026-10-10): "this weekend" asked on a Saturday once came back as
    Wednesday to Friday. None for a name this does not know.
    """
    when = when.strip().lower().replace(" ", "_")
    first, _, last = when.partition("..")
    a = _resolve(first, now)
    b = _resolve(last, now) if last else a
    if a is None or b is None:
        return None
    return a[0].strftime("%Y-%m-%dT%H:%M:%S"), b[1].strftime("%Y-%m-%dT%H:%M:%S")


def resolve_dates(c: "Classification", now: datetime) -> "Classification":
    """Fill each sub-query's dates from its `when`; an unknown name keeps the model's."""
    for q in c.sub_queries:
        if q.when:
            dates = resolve_when(q.when, now)
            if dates:
                q.date_from, q.date_to = dates
            else:
                logger.warning(f"Unknown when {q.when!r}; keeping the model's dates")
    return c


def merge_previous(c: Classification, previous: list[Constraints]) -> Classification:
    """On a refinement, what this turn left out comes from the previous search.

    The model only has to say what changed (owner, 2026-10-10): re-reading the
    chat to restate the whole search lost the town after a "nothing found"
    reply in one run out of two.
    """
    if c.moment != "refinement" or not previous:
        return c
    if c.query_type == "event_search" and not c.sub_queries:
        c.sub_queries = [Constraints()]
    for i, q in enumerate(c.sub_queries):
        before = previous[min(i, len(previous) - 1)]
        for group in CARRIED_GROUPS:
            if any(name in c.cleared for name in group):
                continue
            if any(getattr(q, name) not in (None, False) for name in group):
                continue
            for name in group:
                setattr(q, name, getattr(before, name))
    return c


def enforce(c: Classification, has_history: bool, has_location: bool) -> Classification:
    """Rules that must always hold, so they are code and not prompt wording.

    A first message cannot refine or change anything. A named place is never "near
    me": "near Bergamo" searches around Bergamo, and asking for the user's location
    instead was the biggest line in the 2026-10-09 feedback replay. A "near me" ask
    with no shared location cannot run (route() drops it), so the turn asks where
    instead of answering "nothing found". A search that says nothing about where
    ("events today") needs the user's position just the same (owner, 2026-10-10):
    it is near me. An artist, venue or country is a place; an aggregation
    (needs_custom_cypher) is left alone.
    """
    if c.moment in ("refinement", "new_topic") and not has_history:
        c.moment = "first_query"
    if (
        c.query_type == "event_search"
        and c.moment == "ambiguous"
        and not has_location
        and not c.sub_queries
    ):
        # A search the model could not fill in ("any events today?" came back
        # empty one run in three) still has no place: ask, with the button.
        c.sub_queries = [Constraints(near_me=True)]
    for q in c.sub_queries:
        if q.city or q.venue:
            q.near_me = False
        if (
            c.query_type == "event_search"
            and not has_location
            and not (q.city or q.country_code or q.venue or q.artist)
            and not q.needs_custom_cypher
            and not q.is_empty()
        ):
            q.near_me = True
    if not has_location and any(q.near_me for q in c.sub_queries):
        c.moment = "ambiguous"
        c.clarification = c.clarification or "your city or your location"
    return c


FALLBACK = Classification(
    query_type="event_search",
    moment="ambiguous",
    sub_queries=[],
    clarification="what to search for (place, artist, genre, or date)",
)


def now_in(timezone: str | None) -> datetime:
    """The current moment on the asker's clock.

    "Tonight" is a question about the asker's evening, and the server has no
    standing to answer it: in production the container carries no TZ, so
    datetime.now() was UTC, and a user in Madrid asking at 00:30 was told it
    was still yesterday. An unknown or unparseable zone falls back to UTC,
    which is exactly what every caller got before this existed.
    """
    if timezone:
        try:
            return datetime.now(ZoneInfo(timezone))
        except (ZoneInfoNotFoundError, ValueError):
            # A client is free to send nonsense; it must not fail the turn.
            logger.warning(f"Unknown timezone {timezone!r}; falling back to UTC")
    return datetime.now(utc_timezone.utc)


class Classifier:
    def __init__(self, client=None):
        self.client = client or get_openai_client()

    def classify(
        self,
        user_message: str,
        history: list[dict] | None = None,
        has_location: bool = False,
        timezone: str | None = None,
        previous: list[Constraints] | None = None,
        now: datetime | None = None,
    ) -> Classification:
        """`previous` is the last turn's searches, carried by the chat; `now`
        pins the clock for the eval cases."""
        now = now or now_in(timezone)
        system = CLASSIFIER_SYSTEM_PROMPT.format(
            today=now.date().isoformat(),
            weekday=now.strftime("%A"),
            time=now.strftime("%H:%M"),
            location_note="known (they shared coordinates)"
            if has_location
            else "NOT available",
            language_rule=DETECTION_RULE,
            previous=json.dumps(
                [
                    q.model_dump(exclude_none=True, exclude_defaults=True)
                    for q in previous
                ],
                ensure_ascii=False,
            )
            if previous
            else "none",
        )
        messages = [{"role": "system", "content": system}]
        messages.extend(history or [])
        messages.append({"role": "user", "content": user_message})

        for attempt in range(2):
            response = self.client.chat.completions.create(
                model=settings.classifier_model,
                messages=messages,
                temperature=settings.llm_temperature_classifier,
                response_format={"type": "json_object"},
            )
            raw = response.choices[0].message.content
            try:
                return enforce(
                    merge_previous(
                        resolve_dates(Classification.model_validate_json(raw), now),
                        previous or [],
                    ),
                    has_history=bool(history),
                    has_location=has_location,
                )
            except ValidationError as e:
                logger.warning(
                    f"Classifier output invalid (attempt {attempt + 1}): {e}"
                )
                messages.append({"role": "assistant", "content": raw})
                messages.append(
                    {
                        "role": "user",
                        "content": f"That JSON was invalid: {e}. Return a corrected JSON object only.",
                    }
                )
        logger.error("Classifier failed twice; using fallback classification")
        return FALLBACK.model_copy(deep=True)
