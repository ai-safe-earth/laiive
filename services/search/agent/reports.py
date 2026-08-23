"""Sweep reports persisted in Supabase `search_reports` (service-role only).

Reports outlive a restart and approve replays from the stored report — no
re-fetch, no re-extraction at approve time (owner-confirmed shape). Plain
PostgREST over httpx, same spirit as the gateway's conversation_logs insert.
Tests patch `_http` (see tests/conftest.py).
"""

import httpx
from loguru import logger

from config import settings

_http = httpx.Client(timeout=15.0)


def _url() -> str:
    return settings.supabase_url.rstrip("/") + "/rest/v1/search_reports"


def _headers(**extra: str) -> dict[str, str]:
    key = settings.supabase_service_role_key
    return {"apikey": key, "Authorization": f"Bearer {key}", **extra}


class ReportStoreError(RuntimeError):
    """Supabase refused or failed — the caller turns this into a 502."""


def create_report(
    city: str | None,
    candidates: list[dict],
    stats: dict,
    status: str = "dry_run",
    kind: str = "sweep",
) -> dict:
    response = _http.post(
        _url(),
        headers=_headers(Prefer="return=representation"),
        json={
            "city": city,
            "status": status,
            "kind": kind,
            "candidates": candidates,
            "stats": stats,
        },
    )
    if response.status_code != 201:
        logger.error(
            f"search_reports insert failed: {response.status_code} {response.text[:300]}"
        )
        raise ReportStoreError(f"Could not persist the report ({response.status_code})")
    return response.json()[0]


def get_report(report_id: str) -> dict | None:
    response = _http.get(
        _url(),
        headers=_headers(),
        params={"id": f"eq.{report_id}", "limit": "1"},
    )
    if response.status_code != 200:
        raise ReportStoreError(f"Could not read the report ({response.status_code})")
    rows = response.json()
    return rows[0] if rows else None


def list_reports(
    limit: int = 20, status: str | None = None, city: str | None = None
) -> list[dict]:
    """Newest reports first, optionally narrowed to a status or a city.

    `candidates` stays out of the select on purpose — it is the large jsonb and
    a queue listing twenty reports does not need twenty candidate arrays. The
    detail read is where it comes from.
    """
    params = {
        # Exactly what the queue renders, and nothing that a later migration
        # added: naming a column PostgREST does not have yet 400s the whole
        # listing, which would make reading the queue depend on being able to
        # dismiss from it. The detail read selects * and picks those up.
        "select": "id,city,status,kind,error,stats,created_at,approved_at",
        "order": "created_at.desc",
        "limit": str(limit),
    }
    if status:
        # `in.(a,b)` so the queue can ask for one status or several.
        params["status"] = f"in.({status})" if "," in status else f"eq.{status}"
    if city:
        params["city"] = f"eq.{city}"
    response = _http.get(_url(), headers=_headers(), params=params)
    if response.status_code != 200:
        raise ReportStoreError(f"Could not list reports ({response.status_code})")
    return response.json()


def claim_report(report_id: str, approved_by: str | None, approved_at: str) -> bool:
    """Flip dry_run → approved, returning False if someone already did.

    A compare-and-set in Postgres: the `status=eq.dry_run` filter is part of the
    UPDATE, so two concurrent approves cannot both match. `return=representation`
    makes the outcome visible — an empty array means this caller lost the race.

    Claiming happens *before* the graph writes. If the process dies in between,
    the report reads approved with no `write_results`, and a re-run is safe
    because the shared writer's dedup probe answers `duplicate` per candidate.
    """
    response = _http.patch(
        _url(),
        headers=_headers(Prefer="return=representation"),
        params={"id": f"eq.{report_id}", "status": "eq.dry_run"},
        json={
            "status": "approved",
            "approved_by": approved_by,
            "approved_at": approved_at,
        },
    )
    # `return=representation` means PostgREST answers 200 with the updated rows;
    # anything else is a real failure, not a lost race.
    if response.status_code != 200:
        raise ReportStoreError(f"Could not claim the report ({response.status_code})")
    return bool(response.json())


def update_report(report_id: str, patch: dict) -> None:
    response = _http.patch(
        _url(),
        headers=_headers(),
        params={"id": f"eq.{report_id}"},
        json=patch,
    )
    if response.status_code not in (200, 204):
        raise ReportStoreError(f"Could not update the report ({response.status_code})")


def dismiss_report(
    report_id: str, reviewed_by: str | None, reviewed_at: str, note: str = ""
) -> bool:
    """Flip dry_run → dismissed, returning False if it was no longer dry_run.

    Same compare-and-set as claim_report, and for the same reason: dismissing
    and approving race against each other, and exactly one of them should win.
    Recorded under reviewed_* rather than approved_* — "who cleared this" and
    "who wrote these events" are different questions.
    """
    response = _http.patch(
        _url(),
        headers=_headers(Prefer="return=representation"),
        params={"id": f"eq.{report_id}", "status": "eq.dry_run"},
        json={
            "status": "dismissed",
            "reviewed_by": reviewed_by,
            "reviewed_at": reviewed_at,
            "review_note": note,
        },
    )
    if response.status_code != 200:
        raise ReportStoreError(f"Could not dismiss the report ({response.status_code})")
    return bool(response.json())
