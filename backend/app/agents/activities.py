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
        from app.services.activities import ActivityService

        trip = context["trip"]
        service = ActivityService()
        activities = await service.search(
            destination=trip.get("destination", ""),
            interests=trip.get("interests", []),
            mood=trip.get("mood", "relaxing"),
        )
        return {
            "activities": [a.model_dump() for a in activities],
            "summary": f"Found {len(activities)} activities",
        }
