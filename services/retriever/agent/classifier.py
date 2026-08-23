"""Turn classifier — one cheap structured-output call per turn (02-arch §3).

Emits the query type, the conversational moment, and the FULL resolved
constraint state (previous constraints ± this turn's changes), split into
atomic sub-queries. Re-emitting the whole state every turn is how refinements
("cheaper", "what about Berlin instead?") work without server-side sessions.
"""

from datetime import datetime, timezone as utc_timezone
from typing import Literal, Optional
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from laiive_shared import DEFAULT_LANGUAGE, DETECTION_RULE, normalize_language
from loguru import logger
from pydantic import BaseModel, ValidationError, field_validator

from config import settings

from .utils.llm_utils import chat_completion_with_retry, get_openai_client

CLASSIFIER_PROMPT_VERSION = "v2"

CLASSIFIER_SYSTEM_PROMPT = """You are the query classifier of a live music events assistant backed by a graph database.

Today is {today} ({weekday}). The user's location is {location_note}.

Read the conversation and the latest user message, then return ONE JSON object:

{{
  "query_type": "event_search" | "nearby" | "smalltalk" | "out_of_scope",
  "moment": "first_query" | "refinement" | "new_topic" | "ambiguous",
  "language": string,          // ISO 639-1 code of the LATEST user message
  "sub_queries": [Constraints, ...],
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
  "date_from": "YYYY-MM-DDTHH:MM:SS",   // resolved from relative words using today's date
  "date_to": "YYYY-MM-DDTHH:MM:SS",
  "near_me": boolean,          // the user means their own position
  "radius_km": number,
  "free_text": string,         // fuzzy/vibe ask for semantic search, e.g. "intimate candle-lit jazz"
  "price_max": number,
  "needs_custom_cypher": boolean  // aggregations or asks the fields above cannot express
}}

Rules:
- RE-EMIT THE FULL CONSTRAINT STATE: start from the constraints implied by the
  conversation so far, then apply this turn's additions/changes/removals.
  "cheaper" edits price_max; "what about Berlin?" replaces the city and keeps
  the rest; a completely different request is moment "new_topic" and starts clean.
- Split multi-intent asks into several sub_queries entries
  (e.g. "jazz tonight and anything by Klangfeld this month" → two).
- "tonight" → date_from today 18:00, date_to tomorrow 06:00. "this weekend" →
  Friday 00:00 to Sunday 24:00. A bare month → the whole month. Never invent dates.
- near_me is true only for "near me / nearby / around here" style asks. If the
  user names a place, use city/venue instead.
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
- moment "ambiguous" + clarification: the search cannot run without ONE more
  detail (e.g. no place and no location share). Phrase clarification as the
  missing thing, not a full sentence to parrot.
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
    query_type: Literal["event_search", "nearby", "smalltalk", "out_of_scope"]
    moment: Literal["first_query", "refinement", "new_topic", "ambiguous"]
    # Decided here so the composer is told the language instead of inferring it
    # from a result set full of Spanish venue names (laiive_shared.language).
    language: str = DEFAULT_LANGUAGE
    sub_queries: list[Constraints] = []
    clarification: Optional[str] = None

    @field_validator("language", mode="before")
    @classmethod
    def _clean_language(cls, v):
        return normalize_language(v)


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
    ) -> Classification:
        now = now_in(timezone)
        system = CLASSIFIER_SYSTEM_PROMPT.format(
            today=now.date().isoformat(),
            weekday=now.strftime("%A"),
            location_note="known (they shared coordinates)"
            if has_location
            else "NOT available",
            language_rule=DETECTION_RULE,
        )
        messages = [{"role": "system", "content": system}]
        messages.extend(history or [])
        messages.append({"role": "user", "content": user_message})

        for attempt in range(2):
            response = chat_completion_with_retry(
                self.client,
                model=settings.classifier_model,
                messages=messages,
                temperature=settings.llm_temperature_classifier,
                response_format={"type": "json_object"},
            )
            raw = response.choices[0].message.content
            try:
                return Classification.model_validate_json(raw)
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
