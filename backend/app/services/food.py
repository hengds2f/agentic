"""Restaurant search using Overpass API (OpenStreetMap). Free, no API key."""
from __future__ import annotations

import hashlib

import httpx

from app.core.logging import get_logger
from app.models.schemas import RestaurantOption
from app.services.geocoding import geocode

logger = get_logger(__name__)

OVERPASS_URL = "https://overpass-api.de/api/interpreter"
_HEADERS = {"User-Agent": "HolidayPilot/0.1.0 (ai-holiday-planner)"}

_PRICE_LEVEL = {
    "": 2,
    "cheap": 1,
    "moderate": 2,
    "expensive": 3,
    "luxury": 4,
}


class FoodService:
    async def search(
        self,
        destination: str,
        dietary_restrictions: list[str] | None = None,
        budget: float | None = None,
        radius: int = 3000,
        limit: int = 12,
    ) -> list[RestaurantOption]:
        geo = await geocode(destination)
        if not geo:
            logger.warning("food.no_geocode", destination=destination)
            return []

        query = f"""
[out:json][timeout:20];
(
  node["amenity"="restaurant"](around:{radius},{geo.lat},{geo.lng});
  node["amenity"="cafe"](around:{radius},{geo.lat},{geo.lng});
  node["amenity"="fast_food"](around:{radius},{geo.lat},{geo.lng});
  node["amenity"="bar"]["food"="yes"](around:{radius},{geo.lat},{geo.lng});
);
out body {limit * 3};
"""
        try:
            async with httpx.AsyncClient(timeout=25, headers=_HEADERS) as client:
                resp = await client.post(OVERPASS_URL, data={"data": query})
                resp.raise_for_status()
                data = resp.json()
        except Exception as exc:
            logger.error("food.api_error", error=str(exc))
            return []

        elements = data.get("elements", [])
        restaurants: list[RestaurantOption] = []
        seen: set[str] = set()

        dietary = set(d.lower() for d in (dietary_restrictions or []))

        for el in elements:
            tags = el.get("tags", {})
            name = tags.get("name") or tags.get("name:en")
            if not name or name.lower() in seen:
                continue
            seen.add(name.lower())

            # Filter by dietary needs if specified
            if dietary:
                diet_tags = {
                    tags.get("diet:vegetarian", ""),
                    tags.get("diet:vegan", ""),
                    tags.get("diet:gluten_free", ""),
                    tags.get("diet:halal", ""),
                    tags.get("diet:kosher", ""),
                }
                # Skip items that explicitly say "no" for requested diets
                skip = False
                for d in dietary:
                    tag_key = f"diet:{d}"
                    if tags.get(tag_key) == "no":
                        skip = True
                        break
                if skip:
                    continue

            cuisine = tags.get("cuisine", "").replace(";", ", ").replace("_", " ")
            if not cuisine:
                amenity = tags.get("amenity", "")
                cuisine = {"cafe": "Café", "fast_food": "Fast food", "bar": "Bar"}.get(amenity, "Local")

            price_tag = tags.get("price", "")
            price_level = _PRICE_LEVEL.get(price_tag, 2)

            address_parts = [tags.get("addr:housenumber", ""), tags.get("addr:street", "")]
            address = " ".join(filter(None, address_parts)).strip() or destination

            rid = hashlib.md5(name.encode()).hexdigest()[:8]
            restaurants.append(RestaurantOption(
                id=f"RS-{rid}",
                name=name,
                cuisine=cuisine.title() if len(cuisine) < 50 else cuisine[:50].title(),
                price_level=price_level,
                rating=4.2,  # OSM doesn't have ratings
                address=address,
                latitude=float(el.get("lat", geo.lat)),
                longitude=float(el.get("lon", geo.lng)),
                booking_url=f"https://www.google.com/maps/search/{name.replace(' ', '+')}+{destination.replace(' ', '+')}",
            ))

            if len(restaurants) >= limit:
                break

        logger.info("food.found", destination=destination, count=len(restaurants))
        return restaurants
