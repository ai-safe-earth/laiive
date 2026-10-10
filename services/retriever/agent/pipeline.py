"""The per-turn pipeline: moderation → classifier → router → executor → composer.

Stateless per request — the client sends history + location; the classifier
re-derives the resolved constraint state each turn. Yields shared-protocol
payload models; the API layer wraps them as named SSE events."""

import json
from collections.abc import Iterator
from dataclasses import dataclass, field

from laiive_shared import (
    Error,
    EventCard,
    EventsResult,
    MessageDelta,
    SearchContext,
    Status,
)
from laiive_shared.geocode import NominatimGeocoder
from laiive_shared.geocode_store import RedisGeocodeStore
from laiive_shared.tracing import get_tracer, stage, start_child
from loguru import logger
from opentelemetry.trace import use_span

from config import settings

from .classifier import (
    CLASSIFIER_PROMPT_VERSION,
    Classification,
    Classifier,
    now_in,
    previous_searches,
)
from .composer import COMPOSER_PROMPT_VERSION, Composer
from .executor import Executor
from .router import route
from .tools.query_builder import QUERY_BUILDER_PROMPT_VERSION, QueryBuilderTool
from .tools.safety_guard import SafetyGuardTool
from .utils.llm_utils import get_openai_client

tracer = get_tracer("retriever")


@dataclass
class TurnResult:
    """Everything the JSON endpoint (and tests) need from one turn."""

    text: str = ""
    cards: list[EventCard] = field(default_factory=list)
    classification: Classification | None = None
    cyphers: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    unsafe: bool = False

    @property
    def used_query(self) -> bool:
        return bool(self.cyphers)

    @property
    def needs_more_info(self) -> bool:
        return bool(self.classification and self.classification.moment == "ambiguous")


def verified_first(cards: list[EventCard]) -> None:
    """Promoter submissions to the top of the turn's cards, in place.

    A pro_submission is the only card somebody who can actually make it true
    has vouched for — that is exactly what the card's green mark claims — so it
    should not sit below a swept listing because a sub-query happened to return
    first. `list.sort` is stable, so within each group the retrieval order
    survives untouched: the template leg stays by date, the nearby leg stays by
    distance with its centroid penalty intact.

    The trade this accepts: on a "near me" ask a promoter's event 20 km out now
    leads a swept one 500 m away, and the composer reads the same order. The
    distance is printed on every card, and provenance is the signal the product
    leads with, so the sort is unconditional rather than skipped for NEARBY.
    """
    cards.sort(key=lambda card: card.source != "pro_submission")


def known_context(location: dict | None, timezone: str | None) -> str:
    """Place, day and hour, which the composer must always know (owner,
    2026-10-10). Without it "do you have my location?" got a guess."""
    now = now_in(timezone)
    place = (
        "shared"
        if location
        else "not shared; if asked, say so and suggest typing a town (the chat"
        " offers a share button once, so never insist)"
    )
    return f"the user's clock: {now:%A %Y-%m-%d %H:%M}; their location is {place}"


def many_results_note(count: int, capped: bool) -> str | None:
    """Tell the composer it reads only the first page of a longer list.

    The chat shows ten cards and a "show more" button for the rest; past two
    pages the list is too long to browse, so the reply suggests narrowing it.
    """
    page = settings.max_results_limit
    if count <= page:
        return None
    total = f"{count}+" if capped else str(count)
    note = f"{total} events matched; you see the first {page}, the chat shows the rest on demand"
    if count > 2 * page:
        note += "; in one short sentence, suggest narrowing by genre, distance or price"
    return note


class Pipeline:
    def __init__(self, neo4j_client):
        self.client = get_openai_client()
        self.classifier = Classifier(self.client)
        self.composer = Composer(self.client)
        self.safety = SafetyGuardTool(self.client)
        self.query_builder = QueryBuilderTool(neo4j_client=neo4j_client)
        # Read-only use: the named-place fallback resolves a neighbourhood to a
        # bounding box. Same store as the writers, so it mostly answers from
        # cache and shares their one-request-per-second gate rather than adding
        # a second one.
        self.executor = Executor(
            neo4j_client,
            self._embed,
            self.query_builder,
            geocoder=NominatimGeocoder(
                cache_path=settings.geocode_cache_path,
                store=RedisGeocodeStore(settings.redis_url)
                if settings.redis_url
                else None,
            ),
        )

    def _embed(self, text: str) -> list[float]:
        response = self.client.embeddings.create(
            model=settings.embeddings_model, input=text
        )
        return response.data[0].embedding

    def run_turn(
        self,
        user_message: str,
        history: list[dict] | None = None,
        location: dict | None = None,
        result: TurnResult | None = None,
        timezone: str | None = None,
        request_id: str = "",
        previous: list[dict] | None = None,
    ) -> Iterator[MessageDelta | EventsResult | SearchContext | Status | Error]:
        """Stream one turn. Pass a TurnResult to collect side data as it runs.

        `timezone` is the asker's IANA zone; it decides what "today" means.
        `request_id` is the gateway's, and is what joins this turn's trace to
        its `eval_records` row and to the gateway's own log line.
        `previous` is the last answer's search.context, sent back by the chat.
        """
        result = result if result is not None else TurnResult()

        turn = tracer.start_span(
            "turn",
            attributes={
                # Phoenix reads these three to show the span as a chain with a
                # question and an answer rather than an unnamed block.
                "openinference.span.kind": "CHAIN",
                "input.value": user_message,
                "laiive.request_id": request_id,
                "laiive.timezone": timezone or "",
                "laiive.has_location": bool(location),
                "laiive.history_turns": len(history or []),
                "laiive.model.classifier": settings.classifier_model,
                "laiive.model.query_builder": settings.query_builder_model,
                "laiive.model.composer": settings.composer_model,
                "laiive.prompt.classifier": CLASSIFIER_PROMPT_VERSION,
                "laiive.prompt.query_builder": QUERY_BUILDER_PROMPT_VERSION,
                "laiive.prompt.composer": COMPOSER_PROMPT_VERSION,
            },
        )
        try:
            yield from self._traced_turn(
                turn, user_message, history, location, result, timezone, previous
            )
        except Exception as e:
            turn.record_exception(e)
            raise
        finally:
            # Also the path a client disconnect takes (GeneratorExit), which is
            # why the span is ended here and not after the last yield.
            turn.set_attributes(
                {
                    "output.value": result.text,
                    "laiive.unsafe": result.unsafe,
                    "laiive.card_count": len(result.cards),
                    "laiive.errors": result.errors,
                    "laiive.notes": result.notes,
                }
            )
            turn.end()

    def _traced_turn(
        self,
        turn,
        user_message: str,
        history: list[dict] | None,
        location: dict | None,
        result: TurnResult,
        timezone: str | None,
        previous: list[dict] | None = None,
    ) -> Iterator[MessageDelta | EventsResult | SearchContext | Status | Error]:
        """The turn itself. Every stage names `turn` as its parent explicitly —
        see the span-shape note in `laiive_shared.tracing`."""
        if settings.enable_moderation:
            with stage(tracer, turn, "moderate"):
                result.unsafe = self.safety.detect_injection(
                    user_message
                ) or self.safety.moderate(user_message)

        if result.unsafe:
            result.classification = Classification(
                query_type="out_of_scope", moment="first_query"
            )
        else:
            yield Status(state="classifying")
            with stage(tracer, turn, "classify") as span:
                result.classification = self.classifier.classify(
                    user_message,
                    history,
                    has_location=bool(location),
                    timezone=timezone,
                    previous=previous_searches(previous),
                )
                span.set_attributes(
                    {
                        "laiive.query_type": result.classification.query_type,
                        "laiive.moment": result.classification.moment,
                        "laiive.language": result.classification.language,
                        "laiive.sub_queries": json.dumps(
                            [
                                c.model_dump(mode="json", exclude_none=True)
                                for c in result.classification.sub_queries
                            ],
                            ensure_ascii=False,
                        ),
                    }
                )
            if result.classification.sub_queries:
                # Sent back with the next message, so a follow-up keeps what it
                # does not change (classifier.merge_previous).
                yield SearchContext(
                    searches=[
                        q.model_dump(
                            mode="json",
                            exclude_none=True,
                            exclude_defaults=True,
                            exclude={"query_text", "needs_custom_cypher"},
                        )
                        for q in result.classification.sub_queries
                    ]
                )
            if not location and any(
                q.near_me for q in result.classification.sub_queries
            ):
                # The reply asks for a city; the chat also offers a button that
                # shares the browser's location and asks the same question again.
                yield Status(state="needs_location")
            with stage(tracer, turn, "route") as span:
                plans = route(result.classification, has_location=bool(location))
                span.set_attribute(
                    "laiive.plan_kinds", [str(plan.kind) for plan in plans]
                )
            if plans:
                yield Status(state="searching")
                seen: set = set()
                unreachable = 0
                capped = False
                for plan in plans:
                    with stage(
                        tracer, turn, "execute", {"laiive.plan_kind": str(plan.kind)}
                    ) as span:
                        outcome = self.executor.execute(plan, location, timezone)
                        span.set_attributes(
                            {
                                "laiive.row_count": len(outcome.cards),
                                "laiive.cypher": outcome.cypher or "",
                                "laiive.note": outcome.note or "",
                                "laiive.error": outcome.error or "",
                            }
                        )
                    if outcome.cypher:
                        result.cyphers.append(outcome.cypher)
                    if outcome.note:
                        result.notes.append(outcome.note)
                    if outcome.error:
                        result.errors.append(outcome.error)
                        logger.warning(f"Sub-query failed: {outcome.error}")
                    unreachable += outcome.unavailable
                    capped |= len(outcome.cards) >= settings.fetch_results_limit
                    for card in outcome.cards:
                        key = card.uid or (card.name, card.start_at)
                        if key not in seen:
                            seen.add(key)
                            result.cards.append(card)
                # An unreachable graph is an outage, not an empty city: left to
                # the composer it read as "a quiet spell, try another city"
                # while Aura was paused. The client words it in the UI language.
                if unreachable == len(plans) and not result.cards:
                    yield Error(
                        code="graph_unavailable",
                        message="The events database cannot be reached.",
                    )
                    return
                # Cards go out the moment results exist, before any prose.
                verified_first(result.cards)
                if (note := many_results_note(len(result.cards), capped)) is not None:
                    result.notes.append(note)
                yield EventsResult(events=result.cards, capped=capped)

        result.notes.append(known_context(location, timezone))
        yield Status(state="composing")
        yield from self._compose(turn, user_message, history, result)

    def _compose(
        self,
        turn,
        user_message: str,
        history: list[dict] | None,
        result: TurnResult,
    ) -> Iterator[MessageDelta]:
        """Compose, one token per yield.

        The only stage that outlives a `yield`, so its span cannot be held open
        with a `with` block: it is made current around each `next()` instead,
        which is what nests the composer's OpenAI span under it.
        """
        span = start_child(tracer, turn, "compose")
        try:
            deltas = self.composer.compose_stream(
                user_message,
                history,
                result.classification,
                result.cards,
                unsafe=result.unsafe,
                notes=result.notes,
            )
            while True:
                with use_span(span, end_on_exit=False):
                    try:
                        delta = next(deltas)
                    except StopIteration:
                        break
                result.text += delta
                yield MessageDelta(text=delta)
        finally:
            span.set_attribute("laiive.text_length", len(result.text))
            span.end()
