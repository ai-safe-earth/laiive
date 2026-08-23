"""SEARCH service API (Phase 5) — internal, reached via the gateway's
`/api/admin/search/*` (admin only, SEARCH_ENABLED=true).

Sweeps are dry-run and persist a report; approve replays from the stored
report through the shared writer with source='admin_search'. Endpoints are
plain `def` — Starlette runs them in a threadpool, so blocking work never
starves the event loop (the Phase-3 SSE lesson, applied here).

Sweep and backfill answer 202 with a report id and finish in a background
task; callers poll GET /reports/{id} until the status leaves 'running'.
The synchronous shape died with Phase 6: PaaS proxies cut a silent 2–6 min
response long before the sweep returns.
"""

import uuid
from datetime import UTC, datetime

from fastapi import BackgroundTasks, FastAPI, Header, HTTPException
from fastapi.responses import JSONResponse
from laiive_shared import EventDraft, install_internal_auth, register_health
from laiive_shared.normalize import source_domain
from loguru import logger
from pydantic import BaseModel, Field

from agent import discovery, graph, learning, reports
from config import settings

app = FastAPI(title="laiive search", version="0.1.0")

# /livez and /readyz for the kubelet — the `/health` below stays for humans.
register_health(
    app,
    service="search",
    ready_check=graph.check_neo4j,
)

# Defence in depth behind the NetworkPolicy; unset key = no-op.
install_internal_auth(app, expected=settings.internal_api_key)


@app.exception_handler(reports.ReportStoreError)
async def _report_store_error(request, exc):
    return JSONResponse(status_code=502, content={"detail": str(exc)})


@app.get("/health")
def health():
    return {
        "status": "ok",
        "neo4j": "ok" if graph.check_neo4j() else "error",
        "extraction_model": settings.extraction_model,
    }


class SweepRequest(BaseModel):
    city: str = Field(min_length=1)
    max_pages: int | None = Field(None, ge=1, le=25)


@app.post("/sweep", status_code=202)
def sweep(body: SweepRequest, background: BackgroundTasks):
    """Dry-run discovery for one city; 202 now, results land on the report."""
    city = body.city.strip()
    report = reports.create_report(city, [], {}, status="running")
    background.add_task(_run_sweep, report["id"], city, body.max_pages)
    return {"report_id": report["id"], "city": city, "status": "running"}


def _run_sweep(report_id: str, city: str, max_pages: int | None) -> None:
    # Plain def — BackgroundTasks runs it in the threadpool after the 202.
    try:
        result = discovery.sweep_city(city, max_pages)
        reports.update_report(
            report_id,
            {
                "status": "dry_run",
                "candidates": [c.model_dump() for c in result.candidates],
                "stats": result.stats,
            },
        )
        logger.info(f"Sweep of {result.city}: {result.stats}")
    except Exception as e:  # noqa: BLE001 — a running report must never stay running
        logger.exception(f"Sweep of {city} failed")
        _mark_failed(report_id, e)


def _mark_failed(report_id: str, exc: Exception) -> None:
    try:
        reports.update_report(report_id, {"status": "failed", "error": str(exc)[:2000]})
    except reports.ReportStoreError as e:
        logger.error(f"Report {report_id} failed and could not be marked: {e}")


@app.get("/reports")
def get_reports(limit: int = 20, status: str = "", city: str = ""):
    """The review queue. `status` accepts one value or a comma-separated set."""
    return {
        "reports": reports.list_reports(
            min(max(limit, 1), 100), status=status or None, city=city or None
        )
    }


@app.get("/reports/{report_id}")
def get_report(report_id: str):
    report = reports.get_report(report_id)
    if report is None:
        raise HTTPException(status_code=404, detail="No such report")
    return report


class DismissRequest(BaseModel):
    # Free text, for the admin's own benefit later. Never shown to a user.
    note: str = ""


@app.post("/reports/{report_id}/dismiss")
def dismiss(report_id: str, body: DismissRequest, x_user_id: str = Header("")):
    """Clear a report without writing any of it.

    A sweep that found only junk had no exit before this: the queue could only
    be emptied by approving, which is the wrong verb and the wrong side effect.
    """
    report = reports.get_report(report_id)
    if report is None:
        raise HTTPException(status_code=404, detail="No such report")

    reviewed_at = datetime.now(UTC).isoformat()
    if not reports.dismiss_report(
        report_id, _as_uuid(x_user_id), reviewed_at, body.note
    ):
        current = reports.get_report(report_id)
        status = (current or {}).get("status") or "unknown"
        raise HTTPException(
            status_code=409,
            detail=f"Report is not dismissable (status: {status})",
        )
    logger.info(f"Report {report_id} dismissed by {x_user_id or 'unknown'}")
    return {"report_id": report_id, "status": "dismissed"}


class ApproveRequest(BaseModel):
    # Candidate positions to write; None = every candidate the dry run
    # marked "new". "exists" candidates are never written unless explicitly
    # indexed (and the writer's probe will still 409 a real duplicate).
    indices: list[int] | None = None


@app.post("/reports/{report_id}/approve")
def approve(report_id: str, body: ApproveRequest, x_user_id: str = Header("")):
    report = reports.get_report(report_id)
    if report is None:
        raise HTTPException(status_code=404, detail="No such report")

    candidates = report.get("candidates") or []
    if body.indices is None:
        selected = [
            (i, c) for i, c in enumerate(candidates) if c.get("dedup_status") == "new"
        ]
    else:
        bad = [i for i in body.indices if i < 0 or i >= len(candidates)]
        if bad:
            raise HTTPException(status_code=422, detail=f"No such candidates: {bad}")
        selected = [(i, candidates[i]) for i in body.indices]

    # Claim before writing. A read-then-check let two concurrent approves both
    # pass and write the same candidates twice; the writer's dedup probe would
    # have caught most of it, but not the wasted geocodes and embeddings.
    approved_at = datetime.now(UTC).isoformat()
    if not reports.claim_report(report_id, _as_uuid(x_user_id), approved_at):
        # The CAS matches only dry_run, so say what state actually blocked it.
        current = reports.get_report(report_id)
        status = (current or {}).get("status") or "unknown"
        raise HTTPException(
            status_code=409,
            detail=f"Report is not approvable (status: {status})",
        )

    results = []
    written_domains: list[str] = []
    for index, candidate in selected:
        draft = EventDraft(**(candidate.get("draft") or {}))
        # The page this was read off. It has been on the candidate since the
        # sweep and was dropped here, which left the card promising a source
        # it could not name.
        source_url = candidate.get("source_url") or ""
        outcome = graph.write_event(draft, source_url)
        if outcome.status == "created":
            written_domains.append(source_domain(source_url))
        results.append(
            {
                "index": index,
                "status": outcome.status,
                "uid": outcome.uid,
                "name": outcome.name or draft.name,
                "message": outcome.message,
                "warnings": outcome.warnings,
            }
        )

    created = sum(1 for r in results if r["status"] == "created")
    # The only signal in the ranking that survives the writer's own duplicate
    # and validity probes: a site whose listings parse but never write is not
    # actually producing events.
    learning.record_writes(written_domains)
    # The report is already marked approved by the claim above; this only records
    # what the writes did. The graph writes are committed, so a failure here must
    # not turn them into a 502 that hides what was written.
    warnings = []
    try:
        reports.update_report(report_id, {"write_results": results})
    except reports.ReportStoreError as e:
        logger.error(f"Report {report_id} written but results not recorded: {e}")
        warnings.append(f"Events written, but the report update failed: {e}")
    logger.info(
        f"Report {report_id} approved by {x_user_id or 'unknown'}: "
        f"{created}/{len(results)} created"
    )
    return {
        "report_id": report_id,
        "created": created,
        "results": results,
        "warnings": warnings,
    }


def _as_uuid(value: str) -> str | None:
    """approved_by is a uuid column; anything else must not break the update."""
    try:
        return str(uuid.UUID(value))
    except (ValueError, AttributeError, TypeError):
        return None


class BackfillRequest(BaseModel):
    max_venues: int = Field(25, ge=1, le=200)


@app.post("/backfill", status_code=202)
def backfill(background: BackgroundTasks, body: BackfillRequest | None = None):
    """Fill missing embeddings and venue locations; bounded and idempotent."""
    report = reports.create_report(None, [], {}, status="running", kind="backfill")
    background.add_task(
        _run_backfill, report["id"], (body or BackfillRequest()).max_venues
    )
    return {"report_id": report["id"], "status": "running"}


def _run_backfill(report_id: str, max_venues: int) -> None:
    try:
        result = graph.run_backfill(max_venues)
        reports.update_report(
            report_id, {"status": "done", "stats": result.model_dump()}
        )
        logger.info(f"Backfill: {result}")
    except Exception as e:  # noqa: BLE001 — a running report must never stay running
        logger.exception("Backfill failed")
        _mark_failed(report_id, e)
