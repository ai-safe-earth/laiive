"""Conversational event submission — stateless, one clarification round.

State is client-carried (02-arch §4): the frontend sends the whole
conversation each turn, extraction runs over all of it, and the number of
assistant messages tells us how many clarification rounds already happened.
No in-process sessions, no hashed session ids, no "type yes" write path —
the form (form.extracted) is the only route to publication.

A turn that recognizes several events at once (a spreadsheet, a festival
line-up) starts a *walk*: the chat takes the promoter through the set one
event per turn — "event 1 of 5, here is what I have, I need the price and the
date" → form → publish → "let's go with event 2". The client persists the
draft list and echoes it back with the cursor each message (`WalkInput`), so
the server stays stateless and a walk turn refines only the event under the
cursor instead of re-extracting all N.
"""

from dataclasses import dataclass, field

from laiive_shared import (
    EventDraft,
    detect_language,
    missing_required,
    reply_language_instruction,
)
from loguru import logger
from openai import OpenAI

from config import settings

from .converters import extract_drafts_from_text, refine_draft


_client = OpenAI(api_key=settings.openai_api_key)

CONVERSATION_PROMPT_VERSION = "v5"

# How many events one walk may carry. Only the entry turn extracts a set now,
# but a 200-row sheet would still make a 200-stop walk and re-echo itself with
# every message — past the cap the reply asks for the rest separately.
MAX_EVENTS_PER_TURN = 25

CLARIFY_PROMPT = """You help event promoters publish live music events. Warm, brief, professional.

The promoter's message(s) did not include everything needed. Missing: {missing}.

Write ONE short message asking naturally for the missing details — conversational, not a form or a bullet list. Do not repeat back what they already gave you."""

HANDOFF_PROMPT = """You help event promoters publish live music events. Warm, brief, professional.

A review form with the extracted event details is being shown to the promoter right now, next to your message.{missing_note}

Write ONE short sentence telling them to check the details and publish when ready{missing_hint}."""

WALK_PROMPT = """You help event promoters publish live music events. Warm, brief, professional.

You are walking the promoter through publishing their events one at a time — one review form per event, in order.{opening_note}{truncation_note}

The form being shown next to your message is for event {position} of {total}: {summary}.{missing_note}

Write ONE short message: say which event this is ("event {position} of {total}") and {ask} — conversational, not a form or a bullet list. Do not list the other events, and do not repeat details the form already shows."""

# Field names as shown inside prompts — keep human, not schema-speak.
_FIELD_LABELS = {
    "artists": "the artist(s)",
    "start_at": "the date and time",
    "venue": "the venue",
    "address": "the street address",
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
class WalkInput:
    """The client-carried walk state, echoed back with each message.

    The browser persists the draft set walk.state gave it and sends it up with
    the cursor; the numbering cannot drift and the server holds nothing.
    """

    drafts: list[EventDraft] = field(default_factory=list)
    cursor: int = 0


@dataclass
class PusherTurn:
    drafts: list[EventDraft]
    missing: list[list[str]]  # parallel to drafts
    show_form: bool
    reply: str
    truncated: bool = False
    walk: bool = False  # emit walk.state; the form is drafts[cursor] only
    cursor: int = 0


def clarification_rounds(history: list[dict] | None) -> int:
    """How many times we already asked — assistant messages in the history."""
    return sum(1 for m in history or [] if m.get("role") == "assistant")


def process_turn(messages: list[dict], walk: WalkInput | None = None) -> PusherTurn:
    """One submission-chat turn.

    Mid-walk (`walk` carries drafts) nothing is re-extracted: only the event
    under the cursor is refined with the promoter's latest message.

    Otherwise every event described in the full conversation is extracted. One
    event keeps the old shape — at most one natural clarification round, then
    the form always, missing fields marked. Several events enter the walk
    immediately: the form for event 1 goes out with the gaps highlighted, and
    the intro *is* the ask, so there is no set-wide clarification round.
    """
    if walk is not None and walk.drafts:
        return _walk_turn(messages, walk)

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

    if len(drafts) > 1:
        return PusherTurn(
            drafts=drafts,
            missing=missing,
            show_form=True,
            reply=_walk_reply(
                messages,
                drafts,
                missing,
                0,
                language,
                entering=True,
                truncated=truncated,
            ),
            truncated=truncated,
            walk=True,
            cursor=0,
        )

    asked_before = clarification_rounds(history) > 0
    if missing[0] and not asked_before:
        return PusherTurn(
            drafts=drafts,
            missing=missing,
            show_form=False,
            reply=_clarify(messages, missing[0], language),
            truncated=truncated,
        )
    return PusherTurn(
        drafts=drafts,
        missing=missing,
        show_form=True,
        reply=_handoff(messages, missing[0], language),
        truncated=truncated,
    )


def _walk_turn(messages: list[dict], walk: WalkInput) -> PusherTurn:
    """Refine the event under the cursor, leave the rest of the set alone."""
    drafts = list(walk.drafts)
    cursor = min(max(walk.cursor, 0), len(drafts) - 1)

    drafts[cursor] = refine_draft(drafts[cursor], latest_user_text(messages))
    if drafts[cursor].city and not drafts[cursor].price_currency:
        drafts[cursor].price_currency = default_currency(drafts[cursor].city)
    missing = [missing_required(draft) for draft in drafts]

    language = detect_language(
        _client, settings.classifier_model, latest_user_text(messages)
    )
    return PusherTurn(
        drafts=drafts,
        missing=missing,
        show_form=True,
        reply=_walk_reply(messages, drafts, missing, cursor, language),
        walk=True,
        cursor=cursor,
    )


def _labels(missing: list[str]) -> str:
    return ", ".join(_FIELD_LABELS.get(f, f) for f in missing)


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


def _clarify(messages: list[dict], missing: list[str], language: str) -> str:
    return _chat(CLARIFY_PROMPT.format(missing=_labels(missing)), messages, language)


def _handoff(messages: list[dict], missing: list[str], language: str) -> str:
    note = (
        f" Some fields are still empty and highlighted: {_labels(missing)}."
        if missing
        else ""
    )
    hint = ", filling in what's highlighted" if missing else ""
    return _chat(
        HANDOFF_PROMPT.format(missing_note=note, missing_hint=hint),
        messages,
        language,
    )


def _event_summary(draft: EventDraft) -> str:
    """ "Go Go Dolls at the Butterfly Circus" — how the intro names the event."""
    who = draft.name or ", ".join(draft.artists) or "an event with no details yet"
    return f"{who} at {draft.venue}" if draft.venue else who


def _walk_reply(
    messages: list[dict],
    drafts: list[EventDraft],
    missing: list[list[str]],
    cursor: int,
    language: str,
    entering: bool = False,
    truncated: bool = False,
) -> str:
    gaps = missing[cursor]
    opening = (
        " They just sent the whole set at once — start by saying how many "
        "events you recognized."
        if entering
        else ""
    )
    truncation = (
        f" You could only take the first {MAX_EVENTS_PER_TURN} — ask them to send "
        "the rest in a separate message."
        if truncated
        else ""
    )
    note = (
        f" Still missing and highlighted on the form: {_labels(gaps)}." if gaps else ""
    )
    ask = (
        "ask naturally for the missing details"
        if gaps
        else "tell them to check the details and publish when ready"
    )
    return _chat(
        WALK_PROMPT.format(
            opening_note=opening,
            truncation_note=truncation,
            position=cursor + 1,
            total=len(drafts),
            summary=_event_summary(drafts[cursor]),
            missing_note=note,
            ask=ask,
        ),
        messages,
        language,
    )
