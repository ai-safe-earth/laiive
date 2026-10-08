"""Per-turn eval records persisted in Supabase `eval_records` (service-role only).

The answer side of the turn: joins the gateway's `conversation_logs` (request
side) on request_id. Plain PostgREST over httpx, same shape as
services/search/agent/reports.py. Telemetry, so failures are logged and
swallowed — a turn must never break because the record write did. An empty
SUPABASE_URL disables the write (local runs, tests). Tests patch `_http`.
"""

import httpx
from loguru import logger

from config import settings

from .pipeline import TurnResult

_http = httpx.Client(timeout=15.0)

# Every failure below is swallowed so a turn cannot break on telemetry, which is
# the right availability trade and the wrong observability one: a rotated
# service-role key empties the corpus while every turn stays green and the only
# evidence is a log line nobody tails. This counter is the cheapest thing that
# makes that visible — /health reports it, so a degraded corpus shows up on the
# same page as a degraded dependency.
#
# ponytail: a process-local int, so it resets on deploy and is per replica. That
# is enough to answer "is it failing right now"; it is not a time series, and if
# one is ever wanted the answer is a real metrics exporter, not a bigger int.
writes_failed = 0


def _url() -> str:
    return settings.supabase_url.rstrip("/") + "/rest/v1/eval_records"


def _headers() -> dict[str, str]:
    key = settings.supabase_service_role_key
    return {"apikey": key, "Authorization": f"Bearer {key}", "Prefer": "return=minimal"}


def write(request_id: str, result: TurnResult, latency_ms: int) -> None:
    global writes_failed
    if not settings.supabase_url:
        return
    c = result.classification
    try:
        response = _http.post(
            _url(),
            headers=_headers(),
            json={
                "request_id": request_id,
                "final_text": result.text,
                "card_uids": [card.uid for card in result.cards],
                "cyphers": result.cyphers,
                "query_type": c.query_type if c else None,
                "moment": c.moment if c else None,
                "retrieval_notes": result.notes,
                "row_count": len(result.cards),
                "latency_ms": latency_ms,
                "errors": result.errors,
            },
        )
        if response.status_code != 201:
            writes_failed += 1
            logger.error(
                f"eval_records insert failed: {response.status_code} "
                f"{response.text[:300]}"
            )
    except Exception as e:
        writes_failed += 1
        logger.error(f"eval_records insert failed: {e}")
