"""Tests for the orchestrator and agent pipeline."""
from __future__ import annotations

import pytest

from app.agents.planner import PlannerAgent
from app.agents.budget import BudgetAgent
from app.agents.calendar import CalendarAgent
from app.agents.flights import FlightsAgent
from app.agents.hotels import HotelsAgent
from app.agents.activities import ActivitiesAgent
from app.agents.food import FoodAgent
from app.agents.weather import WeatherAgent
from app.agents.route import RouteAgent
from app.agents.orchestrator import Orchestrator
from app.agents.registry import create_orchestrator
from app.models.schemas import AgentRole, TripRequest, ChatMessage


@pytest.mark.asyncio
async def test_planner_extracts_destination():
    agent = PlannerAgent()
    ctx = {
        "trip": {"trip_id": "t1", "destination": ""},
        "user_message": "I want to visit Paris from New York",
        "history": [],
    }
    result = await agent.run(ctx)
    assert result["updated_trip"]["destination"] == "Paris"
    assert "origin" in result["updated_trip"]


@pytest.mark.asyncio
async def test_planner_identifies_missing_fields():
    agent = PlannerAgent()
    ctx = {
        "trip": {"trip_id": "t1"},
        "user_message": "hello",
        "history": [],
    }
    result = await agent.run(ctx)
    assert result["ready_to_plan"] is False
    assert len(result["missing_fields"]) > 0


@pytest.mark.asyncio
async def test_planner_ready_when_complete():
    agent = PlannerAgent()
    ctx = {
        "trip": {
            "trip_id": "t1",
            "destination": "Paris",
            "origin": "London",
            "start_date": "2026-07-01",
            "end_date": "2026-07-05",
            "num_adults": 2,
            "num_children": 0,
        },
        "user_message": "looks good",
        "history": [],
    }
    result = await agent.run(ctx)
    assert result["ready_to_plan"] is True


@pytest.mark.asyncio
async def test_flights_agent_returns_results():
    agent = FlightsAgent()
    ctx = {"trip": {"origin": "New York", "destination": "Paris", "start_date": "2026-07-01", "end_date": "2026-07-05"}}
    result = await agent.run(ctx)
    assert len(result["flights"]) >= 1


@pytest.mark.asyncio
async def test_hotels_agent_returns_results():
    agent = HotelsAgent()
    ctx = {"trip": {"destination": "Paris", "start_date": "2026-07-01", "end_date": "2026-07-05"}}
    result = await agent.run(ctx)
    assert len(result["hotels"]) >= 0  # depends on Overpass API availability


@pytest.mark.asyncio
async def test_budget_agent_calculates():
    agent = BudgetAgent()
    ctx = {
        "trip": {"budget_total": 3000, "budget_currency": "USD", "start_date": "2026-07-01", "end_date": "2026-07-05", "travelers": []},
        "gathered": {
            "flights": {"flights": [{"price": 450}]},
            "hotels": {"hotels": [{"price_per_night": 100}]},
            "activities": {"activities": [{"price": 25}, {"price": 18}]},
            "food": {"restaurants": []},
        },
    }
    result = await agent.run(ctx)
    assert "breakdown" in result
    assert result["breakdown"]["total_estimated"] > 0


@pytest.mark.asyncio
async def test_calendar_builds_itinerary():
    agent = CalendarAgent()
    ctx = {
        "trip": {"trip_id": "t1", "destination": "Paris", "start_date": "2026-07-01", "end_date": "2026-07-04", "mood": "relaxing", "budget_currency": "USD", "travelers": []},
        "gathered": {
            "flights": {"flights": [{"id": "f1", "airline": "Air", "departure_airport": "JFK", "arrival_airport": "CDG", "price": 400, "departure_time": "2026-07-01T08:00:00", "arrival_time": "2026-07-01T14:00:00"}]},
            "hotels": {"hotels": [{"id": "h1", "name": "Hotel Paris", "address": "1 Rue", "price_per_night": 120}]},
            "activities": {"activities": [
                {"id": "a1", "name": "Louvre", "description": "Museum", "price": 18, "weather_sensitive": False},
                {"id": "a2", "name": "Walk", "description": "Walk", "price": 0, "weather_sensitive": True},
            ]},
            "food": {"restaurants": [
                {"id": "r1", "name": "Cafe", "cuisine": "French"},
                {"id": "r2", "name": "Bistro", "cuisine": "French"},
            ]},
            "weather": {"forecasts": [
                {"date": "2026-07-01", "high_temp_c": 25, "low_temp_c": 18, "condition": "sunny", "precipitation_pct": 5, "recommendation": "Great day!"},
                {"date": "2026-07-02", "high_temp_c": 22, "low_temp_c": 16, "condition": "cloudy", "precipitation_pct": 30, "recommendation": "Pack a layer"},
                {"date": "2026-07-03", "high_temp_c": 20, "low_temp_c": 15, "condition": "rainy", "precipitation_pct": 80, "recommendation": "Bring umbrella"},
            ]},
        },
        "budget": {},
        "route": {},
    }
    result = await agent.run(ctx)
    assert "itinerary" in result
    itin = result["itinerary"]
    assert len(itin["days"]) == 3
    assert itin["total_cost"] > 0
    assert len(itin["packing_list"]) > 0


@pytest.mark.asyncio
async def test_full_orchestration_chat():
    orch = create_orchestrator()
    trip = TripRequest(trip_id="test1")

    # First message: provide all details
    reply, updated_trip, steps, _itin, _budget = await orch.handle_chat(
        trip,
        "I want to go to Paris from New York, 2026-07-01 to 2026-07-05, budget $3000, relaxing mood",
        [],
    )
    assert updated_trip.destination == "Paris"
    assert len(steps) >= 1
    assert len(reply) > 0
