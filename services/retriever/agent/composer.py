"""Composer — runs after EVERY query, no exception (02-arch §3).

Gets the query type, the conversational moment, the ground-truth results, and
the conversation; streams a very short, moment-appropriate text in the
language of the conversation. Events go out separately as `events.result` —
the composer must never enumerate listings.
"""

from collections.abc import Iterator

from laiive_shared import EventCard
from loguru import logger

from config import settings

from .classifier import Classification
from .utils.llm_utils import get_openai_client

COMPOSER_PROMPT_VERSION = "v1"

COMPOSER_SYSTEM_PROMPT = """You are the voice of a live music events assistant: light, a bit jazzy, warm. Never neutral-robotic, never slangy, never trying too hard. Short sentences.

ALWAYS answer in the language the user writes in — their latest message decides, not the language of the event names.

The search already happened. You receive the situation and the found events as
ground truth. The user sees the events as rich cards NEXT TO your text, so:
- NEVER list events, dates, venues, or prices — the cards do that.
- You may nod to the vibe or the count ("three jazz nights waiting for you").
- 1–3 short sentences. That's the whole reply.

Situation-specific guidance:
- first_query with results: a warm confirmation of what was found.
- refinement: acknowledge the adjustment ("narrowed it down…").
- new_topic: fresh start, no reference to the old thread.
- empty (zero results): say it kindly, suggest ONE natural widening
  (another day, nearby city, another genre). No apology theater.
- ambiguous: ask for exactly the ONE missing detail, naturally inside the
  conversation — one question, never a form, never a list of options.
- smalltalk: reply briefly in kind; gently point toward live music.
- out_of_scope: say what you do help with, kindly, one sentence.
- unsafe: decline gently without lecturing; invite a music question instead.

Never fabricate events or details. If ground truth is empty, there are no
events — full stop."""


def _situation(
    classification: Classification, cards: list[EventCard], unsafe: bool
) -> str:
    if unsafe:
        return "unsafe"
    if classification.query_type in ("smalltalk", "out_of_scope"):
        return classification.query_type
    if classification.moment == "ambiguous":
        return "ambiguous"
    if not cards:
        return "empty"
    return classification.moment


class Composer:
    def __init__(self, client=None):
        self.client = client or get_openai_client()

    def compose_stream(
        self,
        user_message: str,
        history: list[dict] | None,
        classification: Classification,
        cards: list[EventCard],
        unsafe: bool = False,
    ) -> Iterator[str]:
        """Stream the reply text, token by token, as the model generates it."""
        situation = _situation(classification, cards, unsafe)
        ground_truth = [
            {
                "name": card.name,
                "artists": card.artists,
                "venue": card.venue,
                "city": card.city,
                "start_at": card.start_at,
                "genre_hint": card.description[:80] if card.description else None,
            }
            for card in cards[: settings.max_results_limit]
        ]
        context = (
            f"Situation: {situation}\n"
            f"Query type: {classification.query_type}\n"
            f"Clarification needed: {classification.clarification or 'none'}\n"
            f"Found events (ground truth, shown to the user as cards): {ground_truth}"
        )
        messages = [{"role": "system", "content": COMPOSER_SYSTEM_PROMPT}]
        messages.extend(history or [])
        messages.append({"role": "user", "content": user_message})
        messages.append({"role": "system", "content": context})

        try:
            stream = self.client.chat.completions.create(
                model=settings.composer_model,
                messages=messages,
                temperature=settings.llm_temperature_composer,
                stream=True,
            )
            for chunk in stream:
                if chunk.choices and (delta := chunk.choices[0].delta.content):
                    yield delta
        except Exception as e:
            logger.error(f"Composer stream failed: {e}")
            yield "I hit a snag putting words together — the results above still stand."
