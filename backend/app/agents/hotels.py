"""Hotels Agent — searches for accommodation options."""
from __future__ import annotations

from typing import Any

from app.agents.base import BaseAgent
from app.models.schemas import AgentRole


class HotelsAgent(BaseAgent):
    role = AgentRole.hotels
    goal = "Search and compare hotel/accommodation options"
    tools = ["search_hotels"]
    guardrails = ["Never book without user approval", "Verify availability"]

    async def run(self, context: dict[str, Any]) -> dict[str, Any]:
        from app.services.hotels import HotelService

        trip = context["trip"]
        cities = context.get("cities", [])
        service = HotelService()

        if cities and len(cities) > 1:
            all_hotels: list[dict] = []
            for city in cities:
                hotels = await service.search(
                    destination=city["name"],
                    check_in=trip.get("start_date", ""),
                    check_out=trip.get("end_date", ""),
                    budget=trip.get("budget_total"),
                    limit=3,
                )
                for h in hotels:
                    d = h.model_dump()
                    d["_city"] = city["name"]
                    all_hotels.append(d)
            return {
                "hotels": all_hotels,
                "summary": f"Found {len(all_hotels)} hotels across {len(cities)} cities",
            }

        hotels = await service.search(
            destination=trip.get("destination", ""),
            check_in=trip.get("start_date", ""),
            check_out=trip.get("end_date", ""),
            budget=trip.get("budget_total"),
        )
        city_name = cities[0]["name"] if cities else trip.get("destination", "")
        return {
            "hotels": [{**h.model_dump(), "_city": city_name} for h in hotels],
            "summary": f"Found {len(hotels)} hotel options",
        }
