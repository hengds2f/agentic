"""Orchestrator — coordinates all agents and manages the planning workflow."""
from __future__ import annotations

import asyncio
from typing import Any

from app.agents.base import BaseAgent
from app.core.logging import get_logger, new_trace_id
from app.models.schemas import (
    AgentRole,
    ChatMessage,
    Itinerary,
    ReasoningStep,
    TripRequest,
)

logger = get_logger(__name__)


class Orchestrator:
    """Central coordinator that delegates to specialized agents."""

    def __init__(self) -> None:
        self._agents: dict[AgentRole, BaseAgent] = {}

    def register(self, agent: BaseAgent) -> None:
        self._agents[agent.role] = agent

    def get_agent(self, role: AgentRole) -> BaseAgent:
        return self._agents[role]

    # ── Main planning flow ─────────────────────────────────────────────────

    async def handle_chat(
        self, trip: TripRequest, user_message: str, history: list[ChatMessage]
    ) -> tuple[str, TripRequest, list[ReasoningStep], dict | None, dict | None]:
        """Process a user chat message: extract intent, maybe run planning.

        Returns (reply, updated_trip, steps, itinerary_data, budget_data).
        """
        trace_id = new_trace_id()
        logger.info("orchestrator.chat", trip_id=trip.trip_id, trace_id=trace_id)

        planner = self.get_agent(AgentRole.planner)
        context = {
            "trip": trip.model_dump(),
            "user_message": user_message,
            "history": [m.model_dump() for m in history[-20:]],
        }
        result, step = await planner.execute(context, trace_id)
        steps = [step]

        reply = result.get("reply", "")
        updated_trip_data = result.get("updated_trip", {})
        if updated_trip_data:
            trip = TripRequest(**{**trip.model_dump(), **updated_trip_data})

        itinerary_data = None
        budget_data = None

        needs_planning = result.get("ready_to_plan", False)
        if needs_planning:
            plan_reply, plan_steps, itinerary_data, budget_data = await self.run_full_plan(trip, trace_id)
            reply += "\n\n" + plan_reply
            steps.extend(plan_steps)

        return reply, trip, steps, itinerary_data, budget_data

    async def run_full_plan(
        self, trip: TripRequest, trace_id: str = ""
    ) -> tuple[str, list[ReasoningStep], dict | None, dict | None]:
        """Run the full multi-agent planning pipeline.

        Returns (summary_text, steps, itinerary_data, budget_data).
        """
        trace_id = trace_id or new_trace_id()
        logger.info("orchestrator.plan", trip_id=trip.trip_id, trace_id=trace_id)

        ctx = {"trip": trip.model_dump()}
        steps: list[ReasoningStep] = []

        # Phase 0: Discover cities within the destination
        from app.services.cities import find_cities

        try:
            start_d = trip.start_date
            end_d = trip.end_date
            num_days = max((end_d - start_d).days, 1) if start_d and end_d else 3
        except (ValueError, TypeError):
            num_days = 3
        num_cities = max(min(num_days // 2, 6), 2)
        cities = await find_cities(trip.destination, num_cities)
        ctx["cities"] = cities
        logger.info("orchestrator.cities", count=len(cities),
                     names=[c["name"] for c in cities], trace_id=trace_id)

        # Phase 1: parallel data gathering
        gather_roles = [
            AgentRole.flights,
            AgentRole.hotels,
            AgentRole.activities,
            AgentRole.food,
            AgentRole.weather,
        ]
        gather_tasks = []
        for role in gather_roles:
            agent = self._agents.get(role)
            if agent:
                gather_tasks.append(agent.execute(ctx, trace_id))

        results = await asyncio.gather(*gather_tasks, return_exceptions=True)
        gathered: dict[str, Any] = {}
        for role, res in zip(gather_roles, results):
            if isinstance(res, Exception):
                logger.error("gather.error", agent=role.value, error=str(res), trace_id=trace_id)
                continue
            data, step = res
            gathered[role.value] = data
            steps.append(step)

        ctx["gathered"] = gathered

        # Phase 2: sequential optimization
        for role in [AgentRole.budget, AgentRole.route, AgentRole.calendar]:
            agent = self._agents.get(role)
            if agent:
                result, step = await agent.execute(ctx, trace_id)
                ctx[role.value] = result
                steps.append(step)

        # Phase 3: extract structured data
        itinerary_data = ctx.get("calendar", {}).get("itinerary")
        budget_data = ctx.get("budget", {}).get("breakdown")

        # Phase 4: build itinerary summary
        summary_parts = ["Here's your trip plan!\n"]
        if itinerary_data:
            for day in itinerary_data.get("days", []):
                summary_parts.append(f"**Day {day['day']} — {day.get('title', day['date'])}**")
                for item in day.get("items", []):
                    cost_str = f" (${item['cost']:.0f})" if item.get("cost") else ""
                    summary_parts.append(f"  • {item.get('start_time', '')} {item['title']}{cost_str}")
                    if item.get("reasoning"):
                        summary_parts.append(f"    _Why: {item['reasoning']}_")
                summary_parts.append("")

        if budget_data:
            summary_parts.append(f"**Estimated total: ${budget_data.get('total_estimated', 0):,.0f} {budget_data.get('currency', 'USD')}**")
            per_person = budget_data.get('cost_per_person', 0)
            if per_person:
                summary_parts.append(f"That's about **${per_person:,.0f} per person**.")

        return "\n".join(summary_parts), steps, itinerary_data, budget_data

    async def regenerate_day(
        self, trip: TripRequest, itinerary: Itinerary, day_num: int
    ) -> tuple[Itinerary, list[ReasoningStep]]:
        """Re-plan a specific day only."""
        trace_id = new_trace_id()
        ctx = {
            "trip": trip.model_dump(),
            "itinerary": itinerary.model_dump(),
            "regenerate_day": day_num,
        }
        steps: list[ReasoningStep] = []

        for role in [AgentRole.activities, AgentRole.food, AgentRole.route, AgentRole.calendar]:
            agent = self._agents.get(role)
            if agent:
                result, step = await agent.execute(ctx, trace_id)
                ctx[role.value] = result
                steps.append(step)

        new_itinerary_data = ctx.get("calendar", {}).get("itinerary", itinerary.model_dump())
        return Itinerary(**new_itinerary_data), steps
