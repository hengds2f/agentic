"""Flights Agent — searches for flight options."""
from __future__ import annotations

from typing import Any

from app.agents.base import BaseAgent
from app.models.schemas import AgentRole


class FlightsAgent(BaseAgent):
    role = AgentRole.flights
    goal = "Search and compare flight options for the trip"
    tools = ["search_flights"]
    guardrails = ["Never book without user approval", "Always show multiple options"]

    async def run(self, context: dict[str, Any]) -> dict[str, Any]:
        from app.services.flights import FlightService

        trip = context["trip"]
        service = FlightService()
        flights = await service.search(
            origin=trip.get("origin", ""),
            destination=trip.get("destination", ""),
            departure_date=trip.get("start_date", ""),
            return_date=trip.get("end_date", ""),
        )
        return {
            "flights": [f.model_dump() for f in flights],
            "summary": f"Found {len(flights)} flight options",
        }
