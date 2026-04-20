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
        cities = context.get("cities", [])

        # Calculate how many activities we need (3 per day minimum)
        start = trip.get("start_date", "")
        end = trip.get("end_date", "")
        try:
            num_days = max((dt_date.fromisoformat(str(end)) - dt_date.fromisoformat(str(start))).days, 1)
        except (ValueError, TypeError):
            num_days = 3

        service = ActivityService()

        if cities and len(cities) > 1:
            # Multi-city: search each city and tag results
            per_city = max(num_days * 3 // len(cities), 5)
            all_activities: list[dict] = []
            for city in cities:
                acts = await service.search(
                    destination=city["name"],
                    interests=trip.get("interests", []),
                    mood=trip.get("mood", "relaxing"),
                    limit=per_city,
                )
                for a in acts:
                    d = a.model_dump()
                    d["_city"] = city["name"]
                    all_activities.append(d)
            return {
                "activities": all_activities,
                "summary": f"Found {len(all_activities)} activities across {len(cities)} cities",
            }

        # Single city
        needed = max(num_days * 3, 15)
        activities = await service.search(
            destination=trip.get("destination", ""),
            interests=trip.get("interests", []),
            mood=trip.get("mood", "relaxing"),
            limit=needed,
        )
        city_name = cities[0]["name"] if cities else trip.get("destination", "")
        return {
            "activities": [{**a.model_dump(), "_city": city_name} for a in activities],
            "summary": f"Found {len(activities)} sightseeing locations",
        }
