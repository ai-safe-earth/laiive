"""Internet search tool for discovering live music events from the web.

Runs in parallel with the knowledge graph query and returns results
in the same frontend-compatible format with a "source" label.
"""

import json
from typing import List, Dict, Any, Optional
from loguru import logger
import httpx

from config import settings
from ..utils.llm_utils import get_openai_client, chat_completion_with_retry


EXTRACTION_PROMPT = """You are a structured-data extractor for live music events.

You will receive raw web search results. Extract every distinct live music event you can identify.

For EACH event return a JSON object with these fields (artist, venue, time are REQUIRED; the rest are optional):

{{
  "artist": "Artist or band name",
  "tagline": "Event title or name",
  "venue": "Venue name, address, city",
  "time": "Date and time as a human-readable string (e.g. 'Wed, Jan 15, 2026 at 8:00 PM')",
  "price": "Price with currency (e.g. '25.00 EUR') or 'Price TBA'",
  "description": "Short description of the event",
  "ticketUrl": "URL to buy tickets or event page"
}}

Rules:
- Only extract REAL events found in the search results. Never invent events.
- If a required field (artist, venue, time) cannot be determined, skip that event entirely.
- The venue field should include city when available (e.g. "Blue Note, Berlin").
- Return ONLY a JSON array of event objects. No markdown, no explanation.
- If no events are found, return an empty array: []

Search query context: "{query}"

Raw search results:
{search_results}"""


class InternetSearchTool:
    """Searches the internet for live music events and extracts structured data."""

    def __init__(self):
        self.llm_client = get_openai_client()
        self.http_client = httpx.Client(timeout=httpx.Timeout(15.0, connect=5.0))

    def run(self, query: str) -> str:
        """Search the web for events and return structured JSON.

        Returns a JSON string with:
            status: "success" or "error"
            results: list of frontend-compatible event dicts with source label
            result_count: number of events found
        """
        try:
            raw_results = self._web_search(query)
            if not raw_results:
                return json.dumps({
                    "status": "success",
                    "results": [],
                    "result_count": 0,
                    "message": "No internet results found",
                })

            events = self._extract_events(query, raw_results)

            # Tag every event with internet source
            for event in events:
                event["source"] = "internet"

            return json.dumps({
                "status": "success",
                "results": events[:settings.max_results_limit],
                "result_count": len(events),
                "message": f"Found {len(events)} event(s) from internet search",
            }, default=str)

        except Exception as e:
            logger.error(f"Internet search failed: {e}")
            return json.dumps({
                "status": "error",
                "error": str(e),
                "results": [],
            })

    def _web_search(self, query: str) -> str:
        """Execute a web search and return raw text results."""
        search_query = f"live music events {query}"

        # Try Brave Search API first
        if settings.brave_search_api_key:
            return self._brave_search(search_query)

        # Fallback: use the LLM's knowledge (less accurate but always available)
        logger.warning(
            "No search API key configured (BRAVE_SEARCH_API_KEY). "
            "Internet search tool is disabled."
        )
        return ""

    def _brave_search(self, query: str) -> str:
        """Search using Brave Search API."""
        try:
            response = self.http_client.get(
                "https://api.search.brave.com/res/v1/web/search",
                params={
                    "q": query,
                    "count": 10,
                    "search_lang": "en",
                    "freshness": "pm",  # past month
                },
                headers={
                    "Accept": "application/json",
                    "Accept-Encoding": "gzip",
                    "X-Subscription-Token": settings.brave_search_api_key,
                },
            )
            response.raise_for_status()
            data = response.json()

            # Extract text snippets from web results
            snippets = []
            for result in data.get("web", {}).get("results", []):
                title = result.get("title", "")
                description = result.get("description", "")
                url = result.get("url", "")
                snippets.append(f"Title: {title}\nSnippet: {description}\nURL: {url}")

            return "\n\n---\n\n".join(snippets)

        except httpx.HTTPStatusError as e:
            logger.error(f"Brave Search API HTTP error: {e.response.status_code}")
            return ""
        except Exception as e:
            logger.error(f"Brave Search API error: {e}")
            return ""

    def _extract_events(self, query: str, raw_results: str) -> List[Dict[str, Any]]:
        """Use LLM to extract structured event data from raw search results."""
        prompt = EXTRACTION_PROMPT.format(
            query=query,
            search_results=raw_results,
        )

        response = chat_completion_with_retry(
            self.llm_client,
            model=settings.internet_search_extraction_model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0,
        )

        content = response.choices[0].message.content.strip()

        # Strip markdown code fences if present
        if content.startswith("```"):
            lines = content.split("\n")
            content = "\n".join(
                lines[1:-1] if lines[-1].strip() == "```" else lines[1:]
            )

        try:
            events = json.loads(content)
        except json.JSONDecodeError:
            logger.warning(f"Failed to parse LLM extraction output: {content[:200]}")
            return []

        if not isinstance(events, list):
            return []

        # Validate required fields
        valid_events = []
        for event in events:
            if not isinstance(event, dict):
                continue
            if all(event.get(f) for f in ("artist", "venue", "time")):
                valid_events.append({
                    "artist": event["artist"],
                    "tagline": event.get("tagline", f"{event['artist']} Live"),
                    "venue": event["venue"],
                    "time": event["time"],
                    "price": event.get("price", "Price TBA"),
                    "description": event.get("description", ""),
                    "ticketUrl": event.get("ticketUrl", ""),
                })

        return valid_events
