"""Activities Agent — finds local attractions, tours, and events."""
from __future__ import annotations

from typing import Any

from app.agents.base import BaseAgent
from app.models.schemas import AgentRole


class ActivitiesAgent(BaseAgent):
    role = AgentRole.activities
    goal = "Find activities, attractions, and events matching traveler interests"
    tools = ["search_activities", "search_events"]
    guardrails = ["Prefer activities matching stated interests", "Include weather-sensitive flags"]

    async def run(self, context: dict[str, Any]) -> dict[str, Any]:
        from datetime import date as dt_date

        from app.services.activities import ActivityService

        trip = context["trip"]

        # Calculate how many activities we need (3 per day minimum)
        start = trip.get("start_date", "")
        end = trip.get("end_date", "")
        try:
            num_days = max((dt_date.fromisoformat(str(end)) - dt_date.fromisoformat(str(start))).days, 1)
        except (ValueError, TypeError):
            num_days = 3
        needed = max(num_days * 3, 15)

        service = ActivityService()
        activities = await service.search(
            destination=trip.get("destination", ""),
            interests=trip.get("interests", []),
            mood=trip.get("mood", "relaxing"),
            limit=needed,
        )
        return {
            "activities": [a.model_dump() for a in activities],
            "summary": f"Found {len(activities)} sightseeing locations",
        }
