"""Nightly backfill — fill missing embeddings and venue locations.

The endpoint is bounded and idempotent, so a nightly run converges on a
fully-embedded, fully-geocoded graph without ever doing unbounded work.
"""

import httpx
from prefect import flow, task
from prefect.artifacts import create_markdown_artifact

try:
    from flows.auth import gateway_url, get_admin_jwt
except ImportError:  # loaded with flows/ itself on sys.path
    from auth import gateway_url, get_admin_jwt  # type: ignore[no-redef]

BACKFILL_TIMEOUT = 600.0


@task(retries=2, retry_delay_seconds=120, timeout_seconds=900)
def run_backfill(max_venues: int) -> dict:
    response = httpx.post(
        f"{gateway_url()}/api/admin/search/backfill",
        json={"max_venues": max_venues},
        headers={"Authorization": f"Bearer {get_admin_jwt()}"},
        timeout=BACKFILL_TIMEOUT,
    )
    response.raise_for_status()
    result: dict = response.json()
    return result


@flow(name="backfill")
def backfill(max_venues: int = 100) -> dict:
    result = run_backfill(max_venues)
    create_markdown_artifact(
        key="backfill",
        markdown="# Backfill\n\n```json\n" + str(result) + "\n```\n",
        description="Nightly embedding + venue-geocode backfill result",
    )
    return result


if __name__ == "__main__":
    backfill()
