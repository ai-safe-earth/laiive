"""SEARCH service API (Phase 5) — internal, reached via the gateway's
`/api/admin/search/*` (admin only, SEARCH_ENABLED=true).

Sweeps are dry-run and persist a report; approve replays from the stored
report through the shared writer with source='admin_search'. Endpoints are
plain `def` — Starlette runs them in a threadpool, so the minutes-long sweep
never starves the event loop (the Phase-3 SSE lesson, applied here).
"""

from datetime import UTC, datetime

from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import JSONResponse
from laiive_shared import EventDraft
from loguru import logger
from pydantic import BaseModel, Field

from agent import discovery, graph, reports
from config import settings

app = FastAPI(title="laiive search", version="0.1.0")


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


@app.post("/sweep")
def sweep(body: SweepRequest):
    """Dry-run discovery for one city; persists a report, writes nothing."""
    result = discovery.sweep_city(body.city.strip(), body.max_pages)
    report = reports.create_report(
        result.city,
        [c.model_dump() for c in result.candidates],
        result.stats,
    )
    logger.info(f"Sweep of {result.city}: {result.stats}")
    return {
        "report_id": report["id"],
        "city": result.city,
        "stats": result.stats,
        "candidates": result.candidates,
    }


@app.get("/reports")
def get_reports(limit: int = 20):
    return {"reports": reports.list_reports(min(max(limit, 1), 100))}


@app.get("/reports/{report_id}")
def get_report(report_id: str):
    report = reports.get_report(report_id)
    if report is None:
        raise HTTPException(status_code=404, detail="No such report")
    return report


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
    if report["status"] == "approved":
        raise HTTPException(status_code=409, detail="Report already approved")

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

    results = []
    for index, candidate in selected:
        draft = EventDraft(**(candidate.get("draft") or {}))
        outcome = graph.write_event(draft)
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
    reports.update_report(
        report_id,
        {
            "status": "approved",
            "approved_by": x_user_id or None,
            "approved_at": datetime.now(UTC).isoformat(),
            "write_results": results,
        },
    )
    logger.info(
        f"Report {report_id} approved by {x_user_id or 'unknown'}: "
        f"{created}/{len(results)} created"
    )
    return {"report_id": report_id, "created": created, "results": results}


class BackfillRequest(BaseModel):
    max_venues: int = Field(25, ge=1, le=200)


@app.post("/backfill")
def backfill(body: BackfillRequest | None = None):
    """Fill missing embeddings and venue locations; bounded and idempotent."""
    result = graph.run_backfill((body or BackfillRequest()).max_venues)
    return result
