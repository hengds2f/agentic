"""Maps/routing service using OSRM (Open Source Routing Machine). Free, no API key."""
from __future__ import annotations

import math

import httpx

from app.core.logging import get_logger

logger = get_logger(__name__)

OSRM_URL = "https://router.project-osrm.org"


class MapsService:
    def cluster_locations(self, locations: list[dict], max_clusters: int = 4) -> list[list[dict]]:
        """Simple geographic clustering by grid partitioning."""
        if not locations:
            return []

        if len(locations) <= max_clusters:
            return [[loc] for loc in locations]

        lats = [loc["lat"] for loc in locations]
        lngs = [loc["lng"] for loc in locations]
        mid_lat = sum(lats) / len(lats)
        mid_lng = sum(lngs) / len(lngs)

        quadrants: dict[str, list[dict]] = {"NE": [], "NW": [], "SE": [], "SW": []}
        for loc in locations:
            ns = "N" if loc["lat"] >= mid_lat else "S"
            ew = "E" if loc["lng"] >= mid_lng else "W"
            quadrants[ns + ew].append(loc)

        return [v for v in quadrants.values() if v]

    async def get_route(
        self, origin_lat: float, origin_lng: float, dest_lat: float, dest_lng: float
    ) -> dict:
        """Get real driving route from OSRM."""
        url = (
            f"{OSRM_URL}/route/v1/driving/"
            f"{origin_lng},{origin_lat};{dest_lng},{dest_lat}"
            f"?overview=false"
        )
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(url)
                resp.raise_for_status()
                data = resp.json()

            if data.get("code") == "Ok" and data.get("routes"):
                route = data["routes"][0]
                return {
                    "distance_km": round(route["distance"] / 1000, 1),
                    "duration_minutes": int(route["duration"] / 60),
                    "mode": "driving",
                }
        except Exception as exc:
            logger.warning("osrm.error", error=str(exc))

        # Fallback to haversine estimate
        dist = self._haversine(origin_lat, origin_lng, dest_lat, dest_lng)
        return {
            "distance_km": round(dist * 1.3, 1),  # ~1.3x road factor
            "duration_minutes": int(dist * 1.3 / 0.5),
            "mode": "driving",
        }

    @staticmethod
    def _haversine(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
        R = 6371
        dlat = math.radians(lat2 - lat1)
        dlng = math.radians(lng2 - lng1)
        a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlng / 2) ** 2
        return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
