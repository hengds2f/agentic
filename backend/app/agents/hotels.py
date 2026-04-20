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
        service = HotelService()
        hotels = await service.search(
            destination=trip.get("destination", ""),
            check_in=trip.get("start_date", ""),
            check_out=trip.get("end_date", ""),
            budget=trip.get("budget_total"),
        )
        return {
            "hotels": [h.model_dump() for h in hotels],
            "summary": f"Found {len(hotels)} hotel options",
        }
