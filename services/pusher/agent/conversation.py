"""Conversational event submission — stateless, one clarification round.

State is client-carried (02-arch §4): the frontend sends the whole
conversation each turn, extraction runs over all of it, and the number of
assistant messages tells us how many clarification rounds already happened.
No in-process sessions, no hashed session ids, no "type yes" write path —
the form (form.extracted) is the only route to publication.

A turn can recognize several events at once (a spreadsheet, a festival
line-up). That is the same path, not a batch mode: the drafts are a list, the
clarification round covers the whole set at once, and the forms then go out
one per event. Since every turn re-extracts the whole conversation, a promoter
correcting one of them ("the third is at 21:00") needs no state on either side.
"""

from collections import Counter
from dataclasses import dataclass

from laiive_shared import (
    EventDraft,
    detect_language,
    missing_required,
    reply_language_instruction,
)
from loguru import logger
from openai import OpenAI

from config import settings

from .converters import extract_drafts_from_text


_client = OpenAI(api_key=settings.openai_api_key)

CONVERSATION_PROMPT_VERSION = "v4"

# How many events one conversation may carry. Past this the reply asks for the
# rest separately: every turn re-emits all of the drafts, so a 200-row sheet
# would spend the whole turn re-writing itself and drift while doing it.
MAX_EVENTS_PER_TURN = 25

CLARIFY_PROMPT = """You help event promoters publish live music events. Warm, brief, professional.

The promoter's message(s) did not include everything needed. Missing: {missing}.

Write ONE short message asking naturally for the missing details — conversational, not a form or a bullet list. Do not repeat back what they already gave you."""

CLARIFY_MANY_PROMPT = """You help event promoters publish live music events. Warm, brief, professional.

You recognized {total} events in what the promoter sent, and some are incomplete: {gaps}.

Write ONE short message: tell them how many events you recognized, then ask naturally for what is missing — conversational, not a form or a bullet list. Ask once for anything several events are missing, rather than event by event. Do not repeat back what they already gave you."""

HANDOFF_PROMPT = """You help event promoters publish live music events. Warm, brief, professional.

A review form with the extracted event details is being shown to the promoter right now, next to your message.{missing_note}

Write ONE short sentence telling them to check the details and publish when ready{missing_hint}."""

HANDOFF_MANY_PROMPT = """You help event promoters publish live music events. Warm, brief, professional.

{total} review forms — one per event you recognized — are being shown to the promoter, one at a time.{missing_note}{truncation_note}

Write ONE short sentence telling them how many events you recognized and to check each form and publish it when ready{missing_hint}."""

# Field names as shown inside prompts — keep human, not schema-speak.
_FIELD_LABELS = {
    "artists": "the artist(s)",
    "start_at": "the date and time",
    "venue": "the venue",
    "city": "the city",
    "price_min": "the ticket price",
}

# City → currency default for drafts that never stated one (major non-EUR markets).
CITY_CURRENCY = {
    "new york": "USD",
    "los angeles": "USD",
    "chicago": "USD",
    "san francisco": "USD",
    "miami": "USD",
    "london": "GBP",
    "manchester": "GBP",
    "glasgow": "GBP",
    "edinburgh": "GBP",
    "zurich": "CHF",
    "geneva": "CHF",
    "copenhagen": "DKK",
    "stockholm": "SEK",
    "oslo": "NOK",
    "warsaw": "PLN",
    "prague": "CZK",
    "tokyo": "JPY",
    "toronto": "CAD",
    "sydney": "AUD",
    "mexico city": "MXN",
}


def default_currency(city: str | None) -> str:
    return CITY_CURRENCY.get((city or "").lower().strip(), "EUR")


@dataclass
class PusherTurn:
    drafts: list[EventDraft]
    missing: list[list[str]]  # parallel to drafts
    show_form: bool
    reply: str
    truncated: bool = False

    @property
    def draft(self) -> EventDraft:
        """The first event — all the single-draft callers (legacy frames, the
        `/extract-event-*` endpoints) ever wanted."""
        return self.drafts[0]

    @property
    def draft_missing(self) -> list[str]:
        return self.missing[0] if self.missing else []


def clarification_rounds(history: list[dict] | None) -> int:
    """How many times we already asked — assistant messages in the history."""
    return sum(1 for m in history or [] if m.get("role") == "assistant")


def process_turn(messages: list[dict], one_round_rule: bool = True) -> PusherTurn:
    """One submission-chat turn.

    Extracts every event described in the full conversation. If a required
    field is missing anywhere and we have not asked yet: exactly one natural
    clarification round, covering the whole set at once. After that the forms
    always go out, missing fields marked (one_round_rule=False keeps asking
    instead — legacy frontend behavior, it cannot render a partial form).
    """
    history = messages[:-1]
    user_text = "\n".join(m["content"] for m in messages if m.get("role") == "user")

    extracted = extract_drafts_from_text(user_text)
    truncated = len(extracted) > MAX_EVENTS_PER_TURN
    if truncated:
        logger.warning(
            f"Conversation carries {len(extracted)} events — keeping the first "
            f"{MAX_EVENTS_PER_TURN}"
        )
    # An empty extraction is still a turn: one blank draft keeps the promoter
    # in the same clarification round they would get from a vague sentence.
    drafts = extracted[:MAX_EVENTS_PER_TURN] or [EventDraft()]

    for draft in drafts:
        if draft.city and not draft.price_currency:
            draft.price_currency = default_currency(draft.city)
    missing = [missing_required(draft) for draft in drafts]

    language = detect_language(
        _client, settings.classifier_model, latest_user_text(messages)
    )

    asked_before = clarification_rounds(history) > 0
    if any(missing) and not (one_round_rule and asked_before):
        return PusherTurn(
            drafts=drafts,
            missing=missing,
            show_form=False,
            reply=_clarify(messages, missing, language),
            truncated=truncated,
        )
    return PusherTurn(
        drafts=drafts,
        missing=missing,
        show_form=True,
        reply=_handoff(messages, missing, language, truncated),
        truncated=truncated,
    )


def _labels(missing: list[str]) -> str:
    return ", ".join(_FIELD_LABELS.get(f, f) for f in missing)


def _gaps(missing: list[list[str]]) -> str:
    """ "3 of them are missing the ticket price; 1 is missing the venue" — the
    set-wide view, so the assistant asks once instead of event by event."""
    counts = Counter(field for fields in missing for field in fields)
    return "; ".join(
        f"{counts[field]} of them {'is' if counts[field] == 1 else 'are'} missing {label}"
        for field, label in _FIELD_LABELS.items()
        if counts.get(field)
    )


def latest_user_text(messages: list[dict]) -> str:
    """The promoter's own last words — what decides the reply language.

    Not the whole conversation: that carries pasted flyers and spreadsheets,
    and a Spanish venue in an English flyer is what used to flip the reply.
    """
    for message in reversed(messages):
        if message.get("role") == "user" and message.get("content"):
            return str(message["content"])
    return ""


def _chat(system: str, messages: list[dict], language: str) -> str:
    response = _client.chat.completions.create(
        model=settings.conversation_model,
        messages=[
            {"role": "system", "content": system},
            *messages,
            # Last, after the conversation: the pasted event details are what
            # the model used to take its language cue from.
            {"role": "system", "content": reply_language_instruction(language)},
        ],
        temperature=0.5,
    )
    return response.choices[0].message.content.strip()


def _clarify(messages: list[dict], missing: list[list[str]], language: str) -> str:
    if len(missing) == 1:
        return _chat(
            CLARIFY_PROMPT.format(missing=_labels(missing[0])), messages, language
        )
    return _chat(
        CLARIFY_MANY_PROMPT.format(total=len(missing), gaps=_gaps(missing)),
        messages,
        language,
    )


def _handoff(
    messages: list[dict],
    missing: list[list[str]],
    language: str,
    truncated: bool = False,
) -> str:
    incomplete = any(missing)
    hint = ", filling in what's highlighted" if incomplete else ""

    if len(missing) == 1:
        note = (
            f" Some fields are still empty and highlighted: {_labels(missing[0])}."
            if incomplete
            else ""
        )
        return _chat(
            HANDOFF_PROMPT.format(missing_note=note, missing_hint=hint),
            messages,
            language,
        )

    note = f" Some are still incomplete: {_gaps(missing)}." if incomplete else ""
    truncation = (
        f" You could only take the first {MAX_EVENTS_PER_TURN} — ask them to send "
        "the rest in a separate message."
        if truncated
        else ""
    )
    return _chat(
        HANDOFF_MANY_PROMPT.format(
            total=len(missing),
            missing_note=note,
            truncation_note=truncation,
            missing_hint=hint,
        ),
        messages,
        language,
    )
