import re
import json
from typing import Optional, Dict, List
from loguru import logger
from config import settings
from ..clients.neo4j_client import neo4j_client


PROXIMITY_PATTERNS = [
    r"\bnear\s+me\b",
    r"\bnearby\b",
    r"\baround\s+me\b",
    r"\bclose\s+to\s+me\b",
    r"\bin\s+my\s+area\b",
    r"\bnear\s+here\b",
    r"\baround\s+here\b",
    r"\bnear\s+my\s+location\b",
    r"\bmy\s+city\b",
    r"\bmy\s+neighborhood\b",
    r"\bcerca\s+de\s+m[íi]\b",
    r"\bcerca\s+m[ií]o\b",
    r"\ben\s+mi\s+zona\b",
    r"\bpor\s+aqu[ií]\b",
    r"\bin\s+der\s+n[äa]he\b",
    r"\bà\s+proximit[ée]\b",
]

_PROXIMITY_RE = re.compile("|".join(PROXIMITY_PATTERNS), re.IGNORECASE)

DISTANCE_PATTERN = re.compile(
    r"(\d+(?:\.\d+)?)\s*(?:km|kil[oó]?met(?:er|ro)s?|miles?|mi)\b",
    re.IGNORECASE,
)


class LocationTool:
    """Handles location-aware event searches with progressive radius expansion."""

    def is_proximity_query(self, message: str) -> bool:
        """Check if the user message is asking for events near their location."""
        return bool(_PROXIMITY_RE.search(message))

    def extract_radius_km(self, message: str) -> Optional[float]:
        """Extract an explicit distance from the message. Returns km."""
        match = DISTANCE_PATTERN.search(message)
        if not match:
            return None
        value = float(match.group(1))
        unit = match.group(0).lower()
        if "mi" in unit and "km" not in unit:
            value *= 1.609  # miles to km
        return min(value, settings.location_max_radius_km)

    def search_with_progressive_radius(
        self,
        latitude: float,
        longitude: float,
        base_query_filter: str = "",
        explicit_radius_km: Optional[float] = None,
    ) -> Dict:
        """Search events near coordinates, expanding radius until enough results found.

        Args:
            latitude: User latitude.
            longitude: User longitude.
            base_query_filter: Additional Cypher WHERE clauses (e.g. genre/date filters).
            explicit_radius_km: If set, use this radius only (no expansion).

        Returns:
            Dict with keys: results, radius_km, total_found.
        """
        if explicit_radius_km is not None:
            results = self._query_by_radius(
                latitude, longitude, explicit_radius_km, base_query_filter
            )
            return {
                "results": results,
                "radius_km": explicit_radius_km,
                "total_found": len(results),
            }

        for radius_km in settings.location_radius_steps:
            results = self._query_by_radius(
                latitude, longitude, radius_km, base_query_filter
            )
            logger.debug(
                f"Location search: radius={radius_km}km → {len(results)} events"
            )
            if len(results) >= settings.location_min_events:
                return {
                    "results": results,
                    "radius_km": radius_km,
                    "total_found": len(results),
                }

        # Return whatever we found at max radius
        return {
            "results": results,
            "radius_km": settings.location_radius_steps[-1],
            "total_found": len(results),
        }

    def _query_by_radius(
        self,
        latitude: float,
        longitude: float,
        radius_km: float,
        base_query_filter: str = "",
    ) -> List[Dict]:
        """Execute a spatial Cypher query for events within a radius."""
        radius_m = radius_km * 1000

        extra_where = ""
        if base_query_filter:
            extra_where = f"AND {base_query_filter}"

        cypher = f"""
        MATCH (e:Event)-[:HOSTED_AT]->(v:Venue)
        WHERE v.latitude IS NOT NULL AND v.longitude IS NOT NULL
          AND point.distance(
                point({{latitude: v.latitude, longitude: v.longitude}}),
                point({{latitude: {latitude}, longitude: {longitude}}})
              ) <= {radius_m}
          {extra_where}
        OPTIONAL MATCH (a:Artist)-[:PERFORMS_AT]->(e)
        OPTIONAL MATCH (v)-[:LOCATED_IN]->(c:City)
        WITH e, v, c,
             collect(DISTINCT a.name) AS artists,
             point.distance(
                point({{latitude: v.latitude, longitude: v.longitude}}),
                point({{latitude: {latitude}, longitude: {longitude}}})
             ) AS distance_m
        RETURN e AS event,
               v.name AS venue,
               c.name AS city,
               artists,
               distance_m,
               e.embedding AS event_embedding,
               v.embedding AS venue_embedding
        ORDER BY distance_m ASC
        LIMIT {settings.max_results_limit}
        """

        try:
            return neo4j_client.execute_read(cypher)
        except Exception as exc:
            logger.error(f"Spatial query failed: {exc}")
            return []

    def build_location_context(
        self,
        latitude: float,
        longitude: float,
        radius_km: Optional[float] = None,
    ) -> str:
        """Build a context string to inject into the query builder prompt."""
        r = radius_km or settings.location_default_radius_km
        return (
            f"\nLOCATION FILTER:\n"
            f"The user is located at latitude {latitude}, longitude {longitude}.\n"
            f"Filter events within {r} km of the user's location using:\n"
            f"  WHERE v.latitude IS NOT NULL AND v.longitude IS NOT NULL\n"
            f"    AND point.distance(\n"
            f"          point({{latitude: v.latitude, longitude: v.longitude}}),\n"
            f"          point({{latitude: {latitude}, longitude: {longitude}}})\n"
            f"        ) <= {r * 1000}\n"
            f"  ORDER BY point.distance(...) ASC\n"
        )
