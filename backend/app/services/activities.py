"""Activities search using Overpass API (OpenStreetMap). Free, no API key."""
from __future__ import annotations

import hashlib

import httpx

from app.core.logging import get_logger
from app.models.schemas import ActivityOption
from app.services.geocoding import geocode

logger = get_logger(__name__)

OVERPASS_URL = "https://overpass-api.de/api/interpreter"
_HEADERS = {"User-Agent": "HolidayPilot/0.1.0 (ai-holiday-planner)"}

_CATEGORY_MAP = {
    "museum": "museum", "gallery": "museum", "artwork": "museum",
    "attraction": "sightseeing", "viewpoint": "sightseeing",
    "theme_park": "entertainment", "zoo": "entertainment", "aquarium": "entertainment",
    "park": "nature", "garden": "nature", "nature_reserve": "nature",
    "castle": "historic", "monument": "historic", "memorial": "historic",
    "archaeological_site": "historic", "ruins": "historic",
    "place_of_worship": "cultural",
    "stadium": "sports", "sports_centre": "sports",
    "beach": "nature", "marina": "nature",
    "marketplace": "shopping", "mall": "shopping",
    "information": "sightseeing",
}

_WEATHER_SENSITIVE = {"nature", "sightseeing", "sports", "entertainment"}


class ActivityService:
    async def search(
        self,
        destination: str,
        interests: list[str] | None = None,
        mood: str = "relaxing",
        radius: int = 10000,
        limit: int = 30,
    ) -> list[ActivityOption]:
        geo = await geocode(destination)
        if not geo:
            logger.warning("activities.no_geocode", destination=destination)
            return []

        fetch_limit = limit * 4  # fetch extra to filter and deduplicate

        query = f"""
[out:json][timeout:25];
(
  node["tourism"~"museum|gallery|attraction|viewpoint|artwork|zoo|theme_park|aquarium|information"](around:{radius},{geo.lat},{geo.lng});
  way["tourism"~"museum|gallery|attraction|viewpoint|artwork|zoo|theme_park|aquarium|information"](around:{radius},{geo.lat},{geo.lng});
  relation["tourism"~"museum|gallery|attraction|viewpoint|artwork|zoo|theme_park|aquarium"](around:{radius},{geo.lat},{geo.lng});
  node["leisure"~"park|garden|nature_reserve|marina|beach|stadium|sports_centre"](around:{radius},{geo.lat},{geo.lng});
  way["leisure"~"park|garden|nature_reserve|marina|beach|stadium|sports_centre"](around:{radius},{geo.lat},{geo.lng});
  node["historic"](around:{radius},{geo.lat},{geo.lng});
  way["historic"](around:{radius},{geo.lat},{geo.lng});
  node["amenity"~"marketplace|place_of_worship"](around:{radius},{geo.lat},{geo.lng});
  way["amenity"~"marketplace|place_of_worship"](around:{radius},{geo.lat},{geo.lng});
  node["shop"="mall"](around:{radius},{geo.lat},{geo.lng});
  way["shop"="mall"](around:{radius},{geo.lat},{geo.lng});
);
out center {fetch_limit};
"""
        try:
            async with httpx.AsyncClient(timeout=30, headers=_HEADERS) as client:
                resp = await client.post(OVERPASS_URL, data={"data": query})
                resp.raise_for_status()
                data = resp.json()
        except Exception as exc:
            logger.error("activities.api_error", error=str(exc))
            return []

        elements = data.get("elements", [])
        activities: list[ActivityOption] = []
        seen_names: set[str] = set()

        for el in elements:
            tags = el.get("tags", {})
            name = tags.get("name") or tags.get("name:en")
            if not name or name.lower() in seen_names:
                continue
            seen_names.add(name.lower())

            lat = el.get("lat") or el.get("center", {}).get("lat", geo.lat)
            lon = el.get("lon") or el.get("center", {}).get("lon", geo.lng)

            # Determine category
            category = "sightseeing"
            for tag_key in ("tourism", "leisure", "historic"):
                tag_val = tags.get(tag_key, "")
                if tag_val in _CATEGORY_MAP:
                    category = _CATEGORY_MAP[tag_val]
                    break

            # Estimate price (most attractions are free or cheap)
            fee = tags.get("fee", "no")
            if fee == "yes":
                price = 15.0  # default admission estimate
                charge = tags.get("charge")
                if charge:
                    import re
                    m = re.search(r'[\d.]+', charge)
                    if m:
                        price = float(m.group())
            else:
                price = 0.0

            # Estimate duration from type
            duration = {"museum": 120, "nature": 90, "historic": 60, "sightseeing": 60,
                        "entertainment": 150, "cultural": 45, "sports": 120}.get(category, 60)

            # Rating (OSM doesn't have ratings; use a reasonable default)
            rating = 4.3

            description = tags.get("description") or tags.get("description:en") or f"{category.capitalize()} in {destination}"
            address = ", ".join(filter(None, [tags.get("addr:street"), tags.get("addr:city", destination)]))

            aid = hashlib.md5(name.encode()).hexdigest()[:8]
            activities.append(ActivityOption(
                id=f"AC-{aid}",
                name=name,
                category=category,
                description=description[:200],
                price=price,
                duration_minutes=duration,
                rating=rating,
                address=address or destination,
                latitude=float(lat),
                longitude=float(lon),
                booking_url=f"https://www.google.com/maps/search/{name.replace(' ', '+')}+{destination.replace(' ', '+')}",
                weather_sensitive=category in _WEATHER_SENSITIVE,
            ))

            if len(activities) >= limit:
                break

        logger.info("activities.found", destination=destination, count=len(activities))
        return activities
