"""Activities search using Overpass API (OpenStreetMap). Free, no API key.

Uses progressively larger search radii to ensure enough POIs are found, even
for large regions like Hokkaido or rural destinations. Falls back to generating
Google Maps discovery suggestions when Overpass returns too few results.
"""
from __future__ import annotations

import hashlib
from urllib.parse import quote_plus

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

# Google Maps suggested attraction categories for fallback
_GMAPS_CATEGORIES = [
    ("Top attractions", "top+things+to+do"),
    ("Museums", "museums"),
    ("Temples & shrines", "temples+shrines"),
    ("Parks & gardens", "parks+gardens"),
    ("Scenic viewpoints", "scenic+viewpoints"),
    ("Historical sites", "historical+sites"),
    ("Markets & shopping", "markets+shopping"),
    ("Beaches", "beaches"),
    ("Art galleries", "art+galleries"),
    ("Landmarks", "landmarks"),
    ("Nature walks", "nature+walks+hiking"),
    ("Hot springs & spas", "hot+springs+onsen+spa"),
    ("Amusement parks", "amusement+parks"),
    ("Aquariums & zoos", "aquarium+zoo"),
    ("Nightlife & entertainment", "nightlife+entertainment"),
    ("Cultural experiences", "cultural+experiences"),
    ("Festivals & events", "festivals+events"),
    ("Boat tours", "boat+tours+cruises"),
    ("Local workshops", "workshops+classes"),
    ("Photography spots", "photography+spots+instagram"),
]


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
            return self._google_maps_fallback(destination, limit)

        activities: list[ActivityOption] = []
        seen_names: set[str] = set()

        # Try progressively larger radii until we have enough
        radii = [radius, 25000, 50000, 100000]
        for r in radii:
            if len(activities) >= limit:
                break
            new_acts = await self._query_overpass(
                geo.lat, geo.lng, r, destination, limit * 4, seen_names
            )
            activities.extend(new_acts)
            if new_acts:
                logger.info("activities.radius_search", radius=r, found=len(new_acts), total=len(activities))

        # If we still don't have enough, fill with Google Maps suggestions
        if len(activities) < limit:
            activities.extend(
                self._google_maps_fallback(destination, limit - len(activities), geo.lat, geo.lng)
            )

        logger.info("activities.found", destination=destination, count=len(activities))
        return activities[:limit]

    async def _query_overpass(
        self, lat: float, lng: float, radius: int, destination: str,
        fetch_limit: int, seen_names: set[str],
    ) -> list[ActivityOption]:
        query = f"""
[out:json][timeout:30];
(
  node["tourism"~"museum|gallery|attraction|viewpoint|artwork|zoo|theme_park|aquarium|information"](around:{radius},{lat},{lng});
  way["tourism"~"museum|gallery|attraction|viewpoint|artwork|zoo|theme_park|aquarium|information"](around:{radius},{lat},{lng});
  relation["tourism"~"museum|gallery|attraction|viewpoint|artwork|zoo|theme_park|aquarium"](around:{radius},{lat},{lng});
  node["leisure"~"park|garden|nature_reserve|marina|beach|stadium|sports_centre"](around:{radius},{lat},{lng});
  way["leisure"~"park|garden|nature_reserve|marina|beach|stadium|sports_centre"](around:{radius},{lat},{lng});
  node["historic"](around:{radius},{lat},{lng});
  way["historic"](around:{radius},{lat},{lng});
  node["amenity"~"marketplace|place_of_worship"](around:{radius},{lat},{lng});
  way["amenity"~"marketplace|place_of_worship"](around:{radius},{lat},{lng});
  node["shop"="mall"](around:{radius},{lat},{lng});
  way["shop"="mall"](around:{radius},{lat},{lng});
);
out center {fetch_limit};
"""
        try:
            async with httpx.AsyncClient(timeout=35, headers=_HEADERS) as client:
                resp = await client.post(OVERPASS_URL, data={"data": query})
                resp.raise_for_status()
                data = resp.json()
        except Exception as exc:
            logger.error("activities.api_error", error=str(exc), radius=radius)
            return []

        elements = data.get("elements", [])
        activities: list[ActivityOption] = []

        for el in elements:
            tags = el.get("tags", {})
            name = tags.get("name") or tags.get("name:en")
            if not name or name.lower() in seen_names:
                continue
            seen_names.add(name.lower())

            elat = el.get("lat") or el.get("center", {}).get("lat", lat)
            elon = el.get("lon") or el.get("center", {}).get("lon", lng)

            category = "sightseeing"
            for tag_key in ("tourism", "leisure", "historic"):
                tag_val = tags.get(tag_key, "")
                if tag_val in _CATEGORY_MAP:
                    category = _CATEGORY_MAP[tag_val]
                    break

            fee = tags.get("fee", "no")
            if fee == "yes":
                price = 15.0
                charge = tags.get("charge")
                if charge:
                    import re
                    m = re.search(r'[\d.]+', charge)
                    if m:
                        price = float(m.group())
            else:
                price = 0.0

            duration = {"museum": 120, "nature": 90, "historic": 60, "sightseeing": 60,
                        "entertainment": 150, "cultural": 45, "sports": 120}.get(category, 60)

            rating = 4.3
            description = tags.get("description") or tags.get("description:en") or f"{category.capitalize()} in {destination}"
            address = ", ".join(filter(None, [tags.get("addr:street"), tags.get("addr:city", destination)]))

            maps_query = quote_plus(f"{name}, {destination}")
            booking_url = f"https://www.google.com/maps/search/{maps_query}/@{elat},{elon},15z"

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
                latitude=float(elat),
                longitude=float(elon),
                booking_url=booking_url,
                weather_sensitive=category in _WEATHER_SENSITIVE,
            ))

        return activities

    def _google_maps_fallback(
        self, destination: str, count: int, lat: float = 0, lng: float = 0,
    ) -> list[ActivityOption]:
        """Generate Google Maps discovery links as suggested activities."""
        activities: list[ActivityOption] = []
        cats = list(_GMAPS_CATEGORIES)
        for i, (label, query_part) in enumerate(cats):
            if len(activities) >= count:
                break
            maps_query = quote_plus(f"{label} in {destination}")
            url = f"https://www.google.com/maps/search/{maps_query}"
            if lat and lng:
                url += f"/@{lat},{lng},12z"

            aid = hashlib.md5(f"{destination}-{label}".encode()).hexdigest()[:8]
            # Cycle through categories for variety
            cat_map = {"Museums": "museum", "Temples & shrines": "cultural",
                       "Parks & gardens": "nature", "Scenic viewpoints": "sightseeing",
                       "Historical sites": "historic", "Markets & shopping": "shopping",
                       "Beaches": "nature", "Art galleries": "museum",
                       "Hot springs & spas": "entertainment", "Amusement parks": "entertainment"}
            category = cat_map.get(label, "sightseeing")

            activities.append(ActivityOption(
                id=f"GM-{aid}",
                name=f"{label} in {destination}",
                category=category,
                description=f"Explore {label.lower()} — click to see top-rated places on Google Maps",
                price=10.0,
                duration_minutes=120,
                rating=4.5,
                address=destination,
                latitude=lat,
                longitude=lng,
                booking_url=url,
                weather_sensitive=category in _WEATHER_SENSITIVE,
            ))

        logger.info("activities.gmaps_fallback", destination=destination, count=len(activities))
        return activities
