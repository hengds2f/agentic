"""Weather Agent — forecasts and weather-aware recommendations."""
from __future__ import annotations

from typing import Any

from app.agents.base import BaseAgent
from app.models.schemas import AgentRole


class WeatherAgent(BaseAgent):
    role = AgentRole.weather
    goal = "Provide weather forecasts and suggest weather-safe timing"
    tools = ["get_forecast"]
    guardrails = ["Flag outdoor activities on rainy days", "Suggest indoor backups"]

    async def run(self, context: dict[str, Any]) -> dict[str, Any]:
        from app.services.weather import WeatherService

        trip = context["trip"]
        service = WeatherService()
        forecasts = await service.get_forecast(
            destination=trip.get("destination", ""),
            start_date=trip.get("start_date", ""),
            end_date=trip.get("end_date", ""),
        )
        return {
            "forecasts": [f.model_dump() for f in forecasts],
            "summary": f"Got {len(forecasts)}-day forecast",
        }
