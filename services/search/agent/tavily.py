"""Tavily search client (D13, revised: Tavily over Brave — see 05-decisions).

Tavily returns cleaned page content with each hit, so there is no separate
fetch-and-strip step: one call per query yields extraction-ready text.
Tests patch `_http` (see tests/conftest.py).
"""

import httpx
from loguru import logger
from pydantic import BaseModel

from config import settings

TAVILY_SEARCH_URL = "https://api.tavily.com/search"

_http = httpx.Client(timeout=30.0)


class SearchHit(BaseModel):
    url: str
    title: str = ""
    content: str = ""  # Tavily's cleaned snippet
    raw_content: str = ""  # full cleaned page text (include_raw_content)
    score: float = 0.0


def search(
    query: str,
    max_results: int,
    *,
    country: str = "",
    include_domains: list[str] | None = None,
    exclude_domains: list[str] | None = None,
) -> list[SearchHit]:
    """One Tavily search; failures return [] so a sweep survives a bad query.

    A call costs one API credit whatever it returns, so `max_results` is the
    cheapest lever there is: the credit is spent on the query, not the rows.
    `country` boosts a locale (general topic only) and the domain lists are
    what a learned source ranking steers with.
    """
    body: dict = {
        "query": query,
        "max_results": max_results,
        "include_raw_content": True,
    }
    if country:
        body["country"] = country
    # Sent only when non-empty: an empty include_domains is not "no preference"
    # to every search API, and a silently over-restricted query returns nothing
    # while looking like a city with no music.
    if include_domains:
        body["include_domains"] = include_domains
    if exclude_domains:
        body["exclude_domains"] = exclude_domains
    try:
        response = _http.post(
            TAVILY_SEARCH_URL,
            headers={"Authorization": f"Bearer {settings.tavily_api_key}"},
            json=body,
        )
        response.raise_for_status()
        payload = response.json()
    except Exception as e:
        logger.error(f"Tavily search failed for {query!r}: {e}")
        return []

    hits = []
    for item in payload.get("results", []):
        if not isinstance(item, dict) or not item.get("url"):
            continue
        hits.append(
            SearchHit(
                url=item["url"],
                title=item.get("title") or "",
                content=item.get("content") or "",
                raw_content=item.get("raw_content") or "",
                score=item.get("score") or 0.0,
            )
        )
    return hits
