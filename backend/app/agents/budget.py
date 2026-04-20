"""Budget Agent — scores options against budget, suggests trade-offs."""
from __future__ import annotations

from typing import Any

from app.agents.base import BaseAgent
from app.models.schemas import AgentRole, BudgetBreakdown, BudgetCategory


class BudgetAgent(BaseAgent):
    role = AgentRole.budget
    goal = "Optimize plan for budget constraints and suggest trade-offs"
    tools = ["calculate_budget", "suggest_savings"]
    guardrails = ["Never exceed budget without warning", "Show category breakdown"]

    async def run(self, context: dict[str, Any]) -> dict[str, Any]:
        trip = context["trip"]
        gathered = context.get("gathered", {})
        total_budget = trip.get("budget_total", 0) or 5000

        # Calculate costs per category
        flights = gathered.get("flights", {}).get("flights", [])
        hotels = gathered.get("hotels", {}).get("hotels", [])
        activities = gathered.get("activities", {}).get("activities", [])
        restaurants = gathered.get("food", {}).get("restaurants", [])

        cheapest_flight = min((f["price"] for f in flights), default=0)
        cheapest_hotel = min((h["price_per_night"] for h in hotels), default=0)

        # Estimate number of nights
        num_nights = 1
        if trip.get("start_date") and trip.get("end_date"):
            from datetime import date as dt_date
            try:
                sd = dt_date.fromisoformat(str(trip["start_date"]))
                ed = dt_date.fromisoformat(str(trip["end_date"]))
                num_nights = max((ed - sd).days, 1)
            except (ValueError, TypeError):
                pass

        hotel_total = cheapest_hotel * num_nights
        activity_total = sum(a.get("price", 0) for a in activities[:num_nights * 2])
        food_daily = 60  # estimate per person per day
        food_total = food_daily * num_nights * max(len(trip.get("travelers", [])), 1)
        transport_est = 30 * num_nights

        total_estimated = cheapest_flight + hotel_total + activity_total + food_total + transport_est

        categories = [
            BudgetCategory(category="Flights", allocated=cheapest_flight, spent=0, items=["Round trip"]),
            BudgetCategory(category="Accommodation", allocated=hotel_total, spent=0, items=[f"{num_nights} nights"]),
            BudgetCategory(category="Activities", allocated=activity_total, spent=0),
            BudgetCategory(category="Food", allocated=food_total, spent=0),
            BudgetCategory(category="Transport", allocated=transport_est, spent=0),
        ]

        savings = []
        if total_estimated > total_budget:
            savings.append("Consider budget hotels or hostels")
            savings.append("Look for free walking tours and parks")
            savings.append("Cook some meals instead of eating out")

        breakdown = BudgetBreakdown(
            total_budget=total_budget,
            total_estimated=total_estimated,
            currency=trip.get("budget_currency", "USD"),
            categories=categories,
            within_budget=total_estimated <= total_budget,
            savings_tips=savings,
        )

        return {
            "breakdown": breakdown.model_dump(),
            "summary": f"Estimated ${total_estimated:,.0f} of ${total_budget:,.0f} budget",
        }
