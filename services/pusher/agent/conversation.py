"""Conversational event submission — stateless, one clarification round.

State is client-carried (02-arch §4): the frontend sends the whole
conversation each turn, extraction runs over all of it, and the number of
assistant messages tells us how many clarification rounds already happened.
No in-process sessions, no hashed session ids, no "type yes" write path —
the form (form.extracted) is the only route to publication.
"""

from dataclasses import dataclass

from laiive_shared import EventDraft, missing_required
from openai import OpenAI

from config import settings

from .converters import extract_draft_from_text

_client = OpenAI(api_key=settings.openai_api_key)

CONVERSATION_PROMPT_VERSION = "v2"

CLARIFY_PROMPT = """You help event promoters publish live music events. Warm, brief, professional.

The promoter's message(s) did not include everything needed. Missing: {missing}.

Write ONE short message asking naturally for the missing details — conversational, not a form or a bullet list. Reply in the language the promoter writes in. Do not repeat back what they already gave you."""

HANDOFF_PROMPT = """You help event promoters publish live music events. Warm, brief, professional.

A review form with the extracted event details is being shown to the promoter right now, next to your message.{missing_note}

Write ONE short sentence telling them to check the details and publish when ready{missing_hint}. Reply in the language the promoter writes in."""

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
    draft: EventDraft
    missing: list[str]
    show_form: bool
    reply: str


def clarification_rounds(history: list[dict] | None) -> int:
    """How many times we already asked — assistant messages in the history."""
    return sum(1 for m in history or [] if m.get("role") == "assistant")


def process_turn(messages: list[dict], one_round_rule: bool = True) -> PusherTurn:
    """One submission-chat turn.

    Extracts a draft from the full conversation. If required fields are
    missing and we have not asked yet: exactly one natural clarification
    round. After that the form always goes out, missing fields marked
    (one_round_rule=False keeps asking instead — legacy frontend behavior,
    it cannot render a partial form).
    """
    history = messages[:-1]
    user_text = "\n".join(m["content"] for m in messages if m.get("role") == "user")

    draft = extract_draft_from_text(user_text)
    if draft.city and not draft.price_currency:
        draft.price_currency = default_currency(draft.city)
    missing = missing_required(draft)

    asked_before = clarification_rounds(history) > 0
    if missing and not (one_round_rule and asked_before):
        return PusherTurn(
            draft=draft,
            missing=missing,
            show_form=False,
            reply=_clarify(messages, missing),
        )
    return PusherTurn(
        draft=draft, missing=missing, show_form=True, reply=_handoff(messages, missing)
    )


def _labels(missing: list[str]) -> str:
    return ", ".join(_FIELD_LABELS.get(f, f) for f in missing)


def _chat(system: str, messages: list[dict]) -> str:
    response = _client.chat.completions.create(
        model=settings.conversation_model,
        messages=[{"role": "system", "content": system}, *messages],
        temperature=0.5,
    )
    return response.choices[0].message.content.strip()


def _clarify(messages: list[dict], missing: list[str]) -> str:
    return _chat(CLARIFY_PROMPT.format(missing=_labels(missing)), messages)


def _handoff(messages: list[dict], missing: list[str]) -> str:
    if missing:
        note = f" Some fields are still empty and highlighted: {_labels(missing)}."
        hint = ", filling in what's highlighted"
    else:
        note = ""
        hint = ""
    return _chat(HANDOFF_PROMPT.format(missing_note=note, missing_hint=hint), messages)
