"""Route/Maps Agent — optimizes routes between locations."""
from __future__ import annotations

from typing import Any

from app.agents.base import BaseAgent
from app.models.schemas import AgentRole


class RouteAgent(BaseAgent):
    role = AgentRole.route
    goal = "Optimize routes and group activities by geography"
    tools = ["get_route", "get_distance_matrix"]
    guardrails = ["Minimize unnecessary travel", "Consider transit options"]

    async def run(self, context: dict[str, Any]) -> dict[str, Any]:
        from app.services.maps import MapsService

        gathered = context.get("gathered", {})
        activities = gathered.get("activities", {}).get("activities", [])
        restaurants = gathered.get("food", {}).get("restaurants", [])

        service = MapsService()

        # Get all locations with coordinates
        locations = []
        for item in activities + restaurants:
            if item.get("latitude") and item.get("longitude"):
                locations.append({
                    "name": item.get("name", ""),
                    "lat": item["latitude"],
                    "lng": item["longitude"],
                    "type": "activity" if item in activities else "food",
                })

        # Cluster by proximity for day grouping
        clusters = service.cluster_locations(locations)

        return {
            "clusters": clusters,
            "total_locations": len(locations),
            "summary": f"Grouped {len(locations)} locations into {len(clusters)} clusters",
        }
