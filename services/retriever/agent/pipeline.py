"""The per-turn pipeline: moderation → classifier → router → executor → composer.

Stateless per request — the client sends history + location; the classifier
re-derives the resolved constraint state each turn. Yields shared-protocol
payload models; the API layer decides the wire format (named SSE events, or
the legacy OpenAI-shaped frames until the new frontend lands)."""

from collections.abc import Iterator
from dataclasses import dataclass, field

from laiive_shared import EventCard, EventsResult, MessageDelta, Status
from loguru import logger

from config import settings

from .classifier import Classification, Classifier
from .composer import Composer
from .executor import Executor
from .router import route
from .tools.query_builder import QueryBuilderTool
from .tools.safety_guard import SafetyGuardTool
from .utils.llm_utils import embedding_with_retry, get_openai_client


@dataclass
class TurnResult:
    """Everything the JSON endpoint (and tests) need from one turn."""

    text: str = ""
    cards: list[EventCard] = field(default_factory=list)
    classification: Classification | None = None
    cyphers: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    unsafe: bool = False

    @property
    def used_query(self) -> bool:
        return bool(self.cyphers)

    @property
    def needs_more_info(self) -> bool:
        return bool(self.classification and self.classification.moment == "ambiguous")


class Pipeline:
    def __init__(self, neo4j_client):
        self.client = get_openai_client()
        self.classifier = Classifier(self.client)
        self.composer = Composer(self.client)
        self.safety = SafetyGuardTool(self.client)
        self.query_builder = QueryBuilderTool(neo4j_client=neo4j_client)
        self.executor = Executor(neo4j_client, self._embed, self.query_builder)

    def _embed(self, text: str) -> list[float]:
        response = embedding_with_retry(
            self.client, model=settings.embeddings_model, input=text
        )
        return response.data[0].embedding

    def run_turn(
        self,
        user_message: str,
        history: list[dict] | None = None,
        location: dict | None = None,
        result: TurnResult | None = None,
    ) -> Iterator[MessageDelta | EventsResult | Status]:
        """Stream one turn. Pass a TurnResult to collect side data as it runs."""
        result = result if result is not None else TurnResult()

        result.unsafe = settings.enable_moderation and (
            self.safety.detect_injection(user_message)
            or self.safety.moderate(user_message)
        )

        if result.unsafe:
            result.classification = Classification(
                query_type="out_of_scope", moment="first_query"
            )
        else:
            yield Status(state="classifying")
            result.classification = self.classifier.classify(
                user_message, history, has_location=bool(location)
            )
            plans = route(result.classification, has_location=bool(location))
            if plans:
                yield Status(state="searching")
                seen: set = set()
                for plan in plans:
                    outcome = self.executor.execute(plan, location)
                    if outcome.cypher:
                        result.cyphers.append(outcome.cypher)
                    if outcome.error:
                        result.errors.append(outcome.error)
                        logger.warning(f"Sub-query failed: {outcome.error}")
                    for card in outcome.cards:
                        key = card.uid or (card.name, card.start_at)
                        if key not in seen:
                            seen.add(key)
                            result.cards.append(card)
                # Cards go out the moment results exist, before any prose.
                yield EventsResult(events=result.cards)

        yield Status(state="composing")
        for delta in self.composer.compose_stream(
            user_message,
            history,
            result.classification,
            result.cards,
            unsafe=result.unsafe,
        ):
            result.text += delta
            yield MessageDelta(text=delta)

    def run_turn_collected(
        self,
        user_message: str,
        history: list[dict] | None = None,
        location: dict | None = None,
    ) -> TurnResult:
        """Non-streaming variant for the JSON endpoint."""
        result = TurnResult()
        for _ in self.run_turn(user_message, history, location, result=result):
            pass
        return result
