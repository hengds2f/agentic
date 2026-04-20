"""Food Agent — finds restaurants and dining options."""
from __future__ import annotations

from typing import Any

from app.agents.base import BaseAgent
from app.models.schemas import AgentRole


class FoodAgent(BaseAgent):
    role = AgentRole.food
    goal = "Recommend restaurants and dining experiences"
    tools = ["search_restaurants"]
    guardrails = ["Respect dietary restrictions", "Vary cuisine types across days"]

    async def run(self, context: dict[str, Any]) -> dict[str, Any]:
        from datetime import date as dt_date

        from app.services.food import FoodService

        trip = context["trip"]
        travelers = trip.get("travelers", [])
        dietary = []
        for t in travelers:
            dietary.extend(t.get("dietary_restrictions", []))

        # Calculate how many restaurants we need (2 meals/day × num_days)
        start = trip.get("start_date", "")
        end = trip.get("end_date", "")
        try:
            num_days = max((dt_date.fromisoformat(str(end)) - dt_date.fromisoformat(str(start))).days, 1)
        except (ValueError, TypeError):
            num_days = 3
        needed = max(num_days * 2 + 4, 12)  # 2 meals/day + some extras

        service = FoodService()
        restaurants = await service.search(
            destination=trip.get("destination", ""),
            dietary_restrictions=dietary,
            budget=trip.get("budget_total"),
            limit=needed,
        )
        return {
            "restaurants": [r.model_dump() for r in restaurants],
            "summary": f"Found {len(restaurants)} recommended restaurants",
        }
