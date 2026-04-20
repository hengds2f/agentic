"""City discovery service — finds major tourist cities within a destination."""
from __future__ import annotations

import httpx

from app.core.logging import get_logger
from app.services.geocoding import geocode

logger = get_logger(__name__)

OVERPASS_URL = "https://overpass-api.de/api/interpreter"
NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
_HEADERS = {"User-Agent": "HolidayPilot/0.1.0 (ai-holiday-planner)"}


async def find_cities(destination: str, num_cities: int = 5) -> list[dict]:
    """Find major cities within a destination region.

    Returns list of dicts: {name, lat, lon, population}.
    If the destination itself is a city, returns just that.
    """
    geo = await geocode(destination)
    if not geo:
        return [{"name": destination, "lat": 0.0, "lon": 0.0, "population": 0}]

    # Query Nominatim for destination type and bounding box
    try:
        async with httpx.AsyncClient(timeout=15, headers=_HEADERS) as client:
            resp = await client.get(
                NOMINATIM_URL,
                params={"q": destination, "format": "json", "limit": 1,
                        "addressdetails": 1, "extratags": 1},
            )
            resp.raise_for_status()
            data = resp.json()
    except Exception as exc:
        logger.error("cities.nominatim_error", error=str(exc))
        return [{"name": destination, "lat": geo.lat, "lon": geo.lng, "population": 0}]

    if not data:
        return [{"name": destination, "lat": geo.lat, "lon": geo.lng, "population": 0}]

    result = data[0]
    osm_type = result.get("type", "")
    bbox = result.get("boundingbox", [])  # [south, north, west, east]

    # If it's already a city/town, return it as the single city
    if osm_type in ("city", "town", "village", "suburb", "hamlet", "borough",
                     "neighbourhood", "quarter"):
        return [{"name": destination, "lat": geo.lat, "lon": geo.lng, "population": 0}]

    # For countries/states/regions, find cities within bounding box
    if len(bbox) < 4:
        return [{"name": destination, "lat": geo.lat, "lon": geo.lng, "population": 0}]

    south, north, west, east = [float(b) for b in bbox]

    # Overpass query for cities and large towns
    query = f"""
[out:json][timeout:30];
(
  node["place"="city"]({south},{west},{north},{east});
  node["place"="town"]["population"~"^[0-9]{{5,}}"]({south},{west},{north},{east});
);
out {num_cities * 5};
"""
    try:
        async with httpx.AsyncClient(timeout=35, headers=_HEADERS) as client:
            resp = await client.post(OVERPASS_URL, data={"data": query})
            resp.raise_for_status()
            osm_data = resp.json()
    except Exception as exc:
        logger.error("cities.overpass_error", error=str(exc))
        return [{"name": destination, "lat": geo.lat, "lon": geo.lng, "population": 0}]

    elements = osm_data.get("elements", [])
    cities: list[dict] = []
    seen: set[str] = set()

    for el in elements:
        tags = el.get("tags", {})
        name = tags.get("name:en") or tags.get("name")
        if not name or name.lower() in seen:
            continue
        seen.add(name.lower())

        pop = 0
        try:
            pop = int(str(tags.get("population", "0")).replace(",", "").replace(" ", ""))
        except (ValueError, TypeError):
            pass

        cities.append({
            "name": name,
            "lat": float(el.get("lat", 0)),
            "lon": float(el.get("lon", 0)),
            "population": pop,
        })

    # Sort by population descending, take top N
    cities.sort(key=lambda c: c["population"], reverse=True)
    cities = cities[:num_cities]

    if not cities:
        return [{"name": destination, "lat": geo.lat, "lon": geo.lng, "population": 0}]

    logger.info("cities.found", destination=destination, count=len(cities),
                names=[c["name"] for c in cities])
    return cities
