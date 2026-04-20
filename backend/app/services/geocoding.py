"""Geocoding service using Nominatim (OpenStreetMap). Free, no API key needed."""
from __future__ import annotations

import httpx
from dataclasses import dataclass

from app.core.logging import get_logger

logger = get_logger(__name__)

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
HEADERS = {"User-Agent": "HolidayPilot/0.1.0 (ai-holiday-planner)"}

_cache: dict[str, "GeoResult | None"] = {}


@dataclass
class GeoResult:
    lat: float
    lng: float
    display_name: str


async def geocode(place: str) -> GeoResult | None:
    """Convert a place name to coordinates. Results are cached."""
    key = place.strip().lower()
    if key in _cache:
        return _cache[key]

    try:
        async with httpx.AsyncClient(timeout=10, headers=HEADERS) as client:
            resp = await client.get(
                NOMINATIM_URL,
                params={"q": place, "format": "json", "limit": 1, "addressdetails": 0},
            )
            resp.raise_for_status()
            data = resp.json()

        if not data:
            logger.warning("geocode.not_found", place=place)
            _cache[key] = None
            return None

        result = GeoResult(
            lat=float(data[0]["lat"]),
            lng=float(data[0]["lon"]),
            display_name=data[0].get("display_name", place),
        )
        _cache[key] = result
        logger.info("geocode.ok", place=place, lat=result.lat, lng=result.lng)
        return result

    except Exception as exc:
        logger.error("geocode.error", place=place, error=str(exc))
        _cache[key] = None
        return None
