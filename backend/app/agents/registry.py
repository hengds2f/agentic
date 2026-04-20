"""Agent registry — creates and wires up all agents with the orchestrator."""
from __future__ import annotations

from app.agents.activities import ActivitiesAgent
from app.agents.budget import BudgetAgent
from app.agents.calendar import CalendarAgent
from app.agents.flights import FlightsAgent
from app.agents.food import FoodAgent
from app.agents.hotels import HotelsAgent
from app.agents.monitoring import MonitoringAgent
from app.agents.orchestrator import Orchestrator
from app.agents.planner import PlannerAgent
from app.agents.route import RouteAgent
from app.agents.weather import WeatherAgent


def create_orchestrator() -> Orchestrator:
    orch = Orchestrator()
    orch.register(PlannerAgent())
    orch.register(FlightsAgent())
    orch.register(HotelsAgent())
    orch.register(ActivitiesAgent())
    orch.register(FoodAgent())
    orch.register(RouteAgent())
    orch.register(WeatherAgent())
    orch.register(BudgetAgent())
    orch.register(CalendarAgent())
    orch.register(MonitoringAgent())
    return orch
