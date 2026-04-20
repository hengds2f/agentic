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

        num_adults = trip.get("num_adults", 1) or 1
        num_children = trip.get("num_children", 0) or 0
        num_travelers = num_adults + num_children

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

        # Cost multiplier: adults full price, children half price
        cost_multiplier = num_adults + num_children * 0.5

        flight_total = cheapest_flight * cost_multiplier
        hotel_total = cheapest_hotel * num_nights
        activity_total = sum(a.get("price", 0) for a in activities[:num_nights * 2]) * cost_multiplier
        food_daily = 60  # estimate per person per day
        food_total = food_daily * num_nights * cost_multiplier
        transport_est = 30 * num_nights

        total_estimated = flight_total + hotel_total + activity_total + food_total + transport_est
        cost_per_person = total_estimated / max(num_travelers, 1)

        categories = [
            BudgetCategory(category="Flights", allocated=flight_total, spent=0, items=["Round trip"]),
            BudgetCategory(category="Accommodation", allocated=hotel_total, spent=0, items=[f"{num_nights} nights"]),
            BudgetCategory(category="Activities", allocated=activity_total, spent=0),
            BudgetCategory(category="Food", allocated=food_total, spent=0),
            BudgetCategory(category="Transport", allocated=transport_est, spent=0),
        ]

        savings = [
            "Consider free walking tours and parks",
            "Look for accommodation with kitchen facilities",
            "Use public transport instead of taxis",
        ]

        breakdown = BudgetBreakdown(
            total_estimated=total_estimated,
            cost_per_person=cost_per_person,
            num_travelers=num_travelers,
            currency=trip.get("budget_currency", "USD"),
            categories=categories,
            savings_tips=savings,
        )

        return {
            "breakdown": breakdown.model_dump(),
            "summary": f"Estimated ${total_estimated:,.0f} total (${cost_per_person:,.0f}/person)",
        }
