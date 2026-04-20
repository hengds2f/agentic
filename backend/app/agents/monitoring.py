"""Monitoring/Replanning Agent — watches for disruptions and re-plans."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from app.agents.base import BaseAgent
from app.models.schemas import AgentRole, AlertEvent, AlertSeverity


class MonitoringAgent(BaseAgent):
    role = AgentRole.monitoring
    goal = "Monitor for trip disruptions and suggest re-plans"
    tools = ["check_flight_status", "check_weather_alerts", "check_price_changes"]
    guardrails = ["Only alert on actionable changes", "Suggest alternatives, don't force changes"]

    async def run(self, context: dict[str, Any]) -> dict[str, Any]:
        trip = context.get("trip", {})
        itinerary = context.get("itinerary", {})

        alerts: list[dict] = []

        # Check weather changes
        weather_alerts = await self._check_weather(trip)
        alerts.extend(weather_alerts)

        # Check flight status changes
        flight_alerts = await self._check_flights(trip, itinerary)
        alerts.extend(flight_alerts)

        return {
            "alerts": alerts,
            "summary": f"Generated {len(alerts)} alerts",
        }

    async def _check_weather(self, trip: dict) -> list[dict]:
        """Check for severe weather alerts at destination."""
        # In production, this would call a weather alert API
        # For MVP, return empty or sample alerts
        return []

    async def _check_flights(self, trip: dict, itinerary: dict) -> list[dict]:
        """Check for flight delays or cancellations."""
        # In production, this would check flight status APIs
        return []

    def create_alert(
        self,
        trip_id: str,
        severity: AlertSeverity,
        title: str,
        description: str,
        action: str = "",
    ) -> AlertEvent:
        return AlertEvent(
            id=uuid.uuid4().hex[:8],
            trip_id=trip_id,
            severity=severity,
            title=title,
            description=description,
            agent=self.role,
            suggested_action=action,
        )
