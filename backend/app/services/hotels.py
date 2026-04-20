"""Hotel search using Overpass API (OpenStreetMap) + price estimation. Free, no API key."""
from __future__ import annotations

import hashlib
import random

import httpx

from app.core.logging import get_logger
from app.models.schemas import HotelOption
from app.services.geocoding import geocode

logger = get_logger(__name__)

OVERPASS_URL = "https://overpass-api.de/api/interpreter"
_HEADERS = {"User-Agent": "HolidayPilot/0.1.0 (ai-holiday-planner)"}

# Price estimation per night by type
_BASE_PRICES = {
    "hostel": (25, 60),
    "guest_house": (40, 90),
    "motel": (50, 100),
    "hotel": (80, 220),
    "apartment": (60, 150),
}


class HotelService:
    async def search(
        self,
        destination: str,
        check_in: str = "",
        check_out: str = "",
        budget: float | None = None,
        radius: int = 5000,
        limit: int = 10,
    ) -> list[HotelOption]:
        geo = await geocode(destination)
        if not geo:
            logger.warning("hotels.no_geocode", destination=destination)
            return []

        query = f"""
[out:json][timeout:20];
(
  node["tourism"~"hotel|hostel|guest_house|motel|apartment"](around:{radius},{geo.lat},{geo.lng});
  way["tourism"~"hotel|hostel|guest_house|motel|apartment"](around:{radius},{geo.lat},{geo.lng});
);
out center {limit * 3};
"""
        try:
            async with httpx.AsyncClient(timeout=25, headers=_HEADERS) as client:
                resp = await client.post(OVERPASS_URL, data={"data": query})
                resp.raise_for_status()
                data = resp.json()
        except Exception as exc:
            logger.error("hotels.api_error", error=str(exc))
            return []

        elements = data.get("elements", [])
        hotels: list[HotelOption] = []
        seen: set[str] = set()

        for el in elements:
            tags = el.get("tags", {})
            name = tags.get("name") or tags.get("name:en")
            if not name or name.lower() in seen:
                continue
            seen.add(name.lower())

            lat = el.get("lat") or el.get("center", {}).get("lat", geo.lat)
            lon = el.get("lon") or el.get("center", {}).get("lon", geo.lng)

            tourism_type = tags.get("tourism", "hotel")
            stars_str = tags.get("stars", "")

            # Estimate price
            low, high = _BASE_PRICES.get(tourism_type, (80, 200))
            if stars_str:
                try:
                    stars = int(stars_str)
                    low = max(low, stars * 30)
                    high = max(high, stars * 70)
                except ValueError:
                    pass
            price = round(random.uniform(low, high), 0)

            # Rating from stars, or estimate
            if stars_str:
                try:
                    rating = min(float(stars_str) + 0.3, 5.0)
                except ValueError:
                    rating = 4.0
            else:
                rating = {"hostel": 3.8, "guest_house": 4.0, "motel": 3.5, "hotel": 4.2}.get(tourism_type, 4.0)

            # Amenities from tags
            amenities = ["Wi-Fi"] if tags.get("internet_access") != "no" else []
            if tags.get("swimming_pool") == "yes":
                amenities.append("Pool")
            if tags.get("breakfast") == "yes":
                amenities.append("Breakfast")
            if tags.get("air_conditioning") == "yes":
                amenities.append("A/C")
            if tags.get("parking") and tags.get("parking") != "no":
                amenities.append("Parking")
            if tourism_type == "hostel":
                amenities.append("Shared kitchen")

            address_parts = [tags.get("addr:housenumber", ""), tags.get("addr:street", "")]
            address = " ".join(filter(None, address_parts)).strip() or destination

            hid = hashlib.md5(name.encode()).hexdigest()[:8]
            hotels.append(HotelOption(
                id=f"HT-{hid}",
                name=name,
                address=address,
                rating=rating,
                price_per_night=price,
                amenities=amenities if amenities else ["Wi-Fi"],
                booking_url=f"https://www.google.com/travel/hotels/{destination.replace(' ', '+')}",
                latitude=float(lat),
                longitude=float(lon),
            ))

            if len(hotels) >= limit:
                break

        # Sort by price
        hotels.sort(key=lambda h: h.price_per_night)

        logger.info("hotels.found", destination=destination, count=len(hotels))
        return hotels
