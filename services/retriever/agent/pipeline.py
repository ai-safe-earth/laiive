"""The per-turn pipeline: moderation → classifier → router → executor → composer.

Stateless per request — the client sends history + location; the classifier
re-derives the resolved constraint state each turn. Yields shared-protocol
payload models; the API layer wraps them as named SSE events."""

from collections.abc import Iterator
from dataclasses import dataclass, field

from laiive_shared import EventCard, EventsResult, MessageDelta, Status
from laiive_shared.geocode import NominatimGeocoder
from laiive_shared.geocode_store import RedisGeocodeStore
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
        timezone: str | None = None,
    ) -> Iterator[MessageDelta | EventsResult | Status]:
        """Stream one turn. Pass a TurnResult to collect side data as it runs.

        `timezone` is the asker's IANA zone; it decides what "today" means.
        """
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
                user_message, history, has_location=bool(location), timezone=timezone
            )
            plans = route(result.classification, has_location=bool(location))
            if plans:
                yield Status(state="searching")
                seen: set = set()
                for plan in plans:
                    outcome = self.executor.execute(plan, location, timezone)
                    if outcome.cypher:
                        result.cyphers.append(outcome.cypher)
                    if outcome.note:
                        result.notes.append(outcome.note)
                    if outcome.error:
                        result.errors.append(outcome.error)
                        logger.warning(f"Sub-query failed: {outcome.error}")
                    for card in outcome.cards:
                        key = card.uid or (card.name, card.start_at)
                        if key not in seen:
                            seen.add(key)
                            result.cards.append(card)
                # Cards go out the moment results exist, before any prose.
                verified_first(result.cards)
                yield EventsResult(events=result.cards)

        yield Status(state="composing")
        for delta in self.composer.compose_stream(
            user_message,
            history,
            result.classification,
            result.cards,
            unsafe=result.unsafe,
            notes=result.notes,
        ):
            result.text += delta
            yield MessageDelta(text=delta)

    def run_turn_collected(
        self,
        user_message: str,
        history: list[dict] | None = None,
        location: dict | None = None,
        timezone: str | None = None,
    ) -> TurnResult:
        """Non-streaming variant for the JSON endpoint."""
        result = TurnResult()
        for _ in self.run_turn(
            user_message, history, location, result=result, timezone=timezone
        ):
            pass
        return result
