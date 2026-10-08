"""Per-write verdict records persisted in Supabase `push_records`.

The pusher's half of what `eval_records` does for the retriever, and deliberately
the same shape: plain PostgREST over httpx, no Supabase SDK, failures logged and
swallowed. A submission must never fail because the record write did.

What it answers that nothing could before: did this write create, adopt,
duplicate, or bounce. `services/pusher/evals/dedup_review.csv` says today's code
silently duplicates in 21 of 52 realistic cases — derived by hand, because
production keeps no trace of it. These rows are that trace.

An empty SUPABASE_URL disables the write (local runs, tests). Tests patch
`_http`; see tests/conftest.py, which must know about every module-level client
in this package.
"""

from typing import Any

import httpx
from loguru import logger

from config import settings

_http = httpx.Client(timeout=15.0)

# See eval_records.writes_failed for the reasoning: swallowing failures is right
# for availability and blind on its own, so /health reports the count.
writes_failed = 0


def _url() -> str:
    return settings.supabase_url.rstrip("/") + "/rest/v1/push_records"


def _headers() -> dict[str, str]:
    key = settings.supabase_service_role_key
    return {"apikey": key, "Authorization": f"Bearer {key}", "Prefer": "return=minimal"}


def write(
    request_id: str,
    *,
    kind: str,
    entity_type: str,
    result: Any,
    user_id: str | None = None,
    draft: dict | None = None,
    latency_ms: int | None = None,
) -> None:
    """Record one write attempt. `result` is a WriteResult or an UpdateResult.

    Called for every outcome including the ones that raise — the interesting
    verdicts (duplicate, invalid, error) all leave the API as HTTPExceptions, so
    recording only the returns would capture successes and nothing else.
    """
    global writes_failed
    if not settings.supabase_url:
        return
    try:
        response = _http.post(
            _url(),
            headers=_headers(),
            json={
                "request_id": request_id,
                "user_id": user_id,
                "kind": kind,
                "entity_type": entity_type,
                "writer_verdict": result.status,
                "entity_uid": result.uid,
                # Only a WriteResult names the thing it wrote; an edit knows the
                # uid it was handed and nothing else.
                "entity_name": getattr(result, "name", None),
                "venue_uid": getattr(result, "venue_uid", None),
                "venue_created": getattr(result, "venue_created", None),
                "artist_uids_created": getattr(result, "artist_uids_created", None),
                "draft": draft,
                "changed": getattr(result, "changed", None) or None,
                "warnings": result.warnings,
                "message": result.message or None,
                "latency_ms": latency_ms,
            },
        )
        if response.status_code != 201:
            writes_failed += 1
            logger.error(
                f"push_records insert failed: {response.status_code} "
                f"{response.text[:300]}"
            )
    except Exception as e:
        writes_failed += 1
        logger.error(f"push_records insert failed: {e}")
