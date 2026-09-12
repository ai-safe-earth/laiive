"""The pusher's write path — owns the clients, delegates to the shared writer.

All graph writes go through laiive_shared.neo4j_writer (MERGE-by-identity,
dedup probe, provenance, geocoded venue location). This module only wires up
the OpenAI client, the Neo4j driver, and the Nominatim geocoder.
Tests patch _openai / _driver / _geocoder here (see tests/conftest.py).
"""

from laiive_shared import EventDraft
from laiive_shared.geocode import NominatimGeocoder
from laiive_shared.geocode_store import RedisGeocodeStore
from laiive_shared.neo4j_writer import WriteResult
from laiive_shared.neo4j_writer import write_event as _shared_write_event
from neo4j import GraphDatabase
from openai import OpenAI

from config import settings

_openai = OpenAI(api_key=settings.openai_api_key)


def _build_driver():
    return GraphDatabase.driver(
        settings.neo4j_uri,
        auth=(settings.neo4j_user, settings.neo4j_password),
        connection_timeout=10,
        # One writer replica, one write at a time per request — a small pool keeps
        # this service's share of Aura's connection budget out of the retriever's way.
        max_connection_pool_size=settings.neo4j_max_pool_size,
    )


_driver = _build_driver()

# What a paused-or-waking Aura sounds like through the shared writer's typed
# error. Matched on the message because the writer already swallowed the
# exception type — and that is fine: these strings are the driver's own.
_TRANSIENT_SIGNATURES = (
    "routing information",
    "write service",
    "read service",
    "SessionExpired",
    "ServiceUnavailable",
    "defunct connection",
)


def is_transient_graph_error(message: str) -> bool:
    """A graph failure that a retry (or a rebuilt driver) can heal."""
    return any(s.lower() in message.lower() for s in _TRANSIENT_SIGNATURES)


def _reset_driver() -> None:
    """Replace the module driver: a driver that built its routing table while
    Aura was paused keeps failing after Aura is back, until it is rebuilt —
    on 2026-09-12 the pusher stayed not_ready through a whole flap recovery
    and needed a process restart. A fresh driver reconnects immediately."""
    global _driver
    try:
        _driver.close()
    except Exception:  # noqa: BLE001 - a poisoned driver may fail to close
        pass
    _driver = _build_driver()


_geocoder = NominatimGeocoder(
    cache_path=settings.geocode_cache_path,
    store=RedisGeocodeStore(settings.redis_url) if settings.redis_url else None,
)


def verify_connectivity() -> bool:
    """One round-trip to Aura, for the readiness probe and `/health`.

    Reads `_driver` at call time so tests patching the module attribute still
    take effect (see tests/conftest.py).
    """
    _driver.verify_connectivity()
    return True


def _embed_texts(texts: list[str]) -> list[list[float]]:
    response = _openai.embeddings.create(model=settings.embedding_model, input=texts)
    return [d.embedding for d in response.data]


def write_event(
    draft: EventDraft,
    owner_id: str | None = None,
    source: str = "pro_submission",
    venue_uid: str | None = None,
) -> WriteResult:
    result = _write_once(draft, owner_id, source, venue_uid)
    if result.status == "error" and is_transient_graph_error(result.message):
        # One retry on a fresh driver. Safe to re-send: the write MERGEs by
        # identity and the dedup probe runs again, so a half-landed first
        # attempt answers "duplicate"/"adopted" rather than doubling.
        _reset_driver()
        result = _write_once(draft, owner_id, source, venue_uid)
    return result


def _write_once(
    draft: EventDraft,
    owner_id: str | None,
    source: str,
    venue_uid: str | None,
) -> WriteResult:
    with _driver.session(database=settings.neo4j_database) as session:
        return _shared_write_event(
            session,
            draft,
            source=source,
            owner_id=owner_id,
            embed_texts=_embed_texts,
            embedding_model=settings.embedding_model,
            geocoder=_geocoder,
            venue_uid=venue_uid,
        )
