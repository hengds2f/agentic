"""API routes for HolidayPilot."""
from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse, Response

from app.agents.orchestrator import Orchestrator
from app.agents.registry import create_orchestrator
from app.models.schemas import (
    BudgetBreakdown,
    ChatMessage,
    ChatRequest,
    ChatResponse,
    Itinerary,
    ReasoningStep,
    TripRequest,
    TripSummary,
)
from app.services.flights import FlightService
from app.services.hotels import HotelService
from app.services.activities import ActivityService
from app.services.food import FoodService
from app.services.weather import WeatherService
from app.services.pdf_export import generate_pdf, render_itinerary_html

router = APIRouter()

# In-memory store for MVP (replace with DB in production)
_trips: dict[str, dict[str, Any]] = {}
_chat_history: dict[str, list[ChatMessage]] = {}
_itineraries: dict[str, dict] = {}
_orchestrator: Orchestrator | None = None


def get_orchestrator() -> Orchestrator:
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = create_orchestrator()
    return _orchestrator


# ── Chat ───────────────────────────────────────────────────────────────────────


@router.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest) -> ChatResponse:
    """Main conversational endpoint. Handles intake and triggers planning."""
    orch = get_orchestrator()

    # Get or create trip
    if req.trip_id not in _trips:
        trip_id = req.trip_id or uuid.uuid4().hex[:12]
        _trips[trip_id] = TripRequest(trip_id=trip_id).model_dump()
        _chat_history[trip_id] = []
        req.trip_id = trip_id

    trip = TripRequest(**_trips[req.trip_id])
    history = _chat_history.get(req.trip_id, [])

    # Record user message
    user_msg = ChatMessage(role="user", content=req.message)
    history.append(user_msg)

    # Run orchestrator
    reply, updated_trip, steps, itin_data, budget_data = await orch.handle_chat(trip, req.message, history)

    # Record assistant reply
    assistant_msg = ChatMessage(role="assistant", content=reply)
    history.append(assistant_msg)

    # Persist
    _trips[req.trip_id] = updated_trip.model_dump()
    _chat_history[req.trip_id] = history

    # Store itinerary if planning occurred
    itinerary_obj = None
    budget_obj = None
    if itin_data:
        _itineraries[req.trip_id] = itin_data
        itinerary_obj = Itinerary(**itin_data)
    if budget_data:
        budget_obj = BudgetBreakdown(**budget_data)

    return ChatResponse(
        trip_id=req.trip_id,
        messages=[user_msg, assistant_msg],
        trip_data=updated_trip,
        reasoning_steps=steps,
        itinerary=itinerary_obj,
        budget=budget_obj,
    )


# ── Plan ───────────────────────────────────────────────────────────────────────


@router.post("/plan")
async def plan(trip_req: TripRequest) -> dict:
    """Directly trigger full planning pipeline."""
    orch = get_orchestrator()
    trip_id = trip_req.trip_id or uuid.uuid4().hex[:12]
    trip_req.trip_id = trip_id
    _trips[trip_id] = trip_req.model_dump()

    reply, steps, itinerary_data, budget_data = await orch.run_full_plan(trip_req)

    if itinerary_data:
        _itineraries[trip_id] = itinerary_data

    return {
        "trip_id": trip_id,
        "plan_summary": reply,
        "itinerary": itinerary_data,
        "budget": budget_data,
        "reasoning_steps": [s.model_dump() for s in steps],
    }


# ── Search endpoints ──────────────────────────────────────────────────────────


@router.get("/search/flights")
async def search_flights(origin: str, destination: str, departure: str, return_date: str = ""):
    service = FlightService()
    flights = await service.search(origin, destination, departure, return_date)
    return {"flights": [f.model_dump() for f in flights]}


@router.get("/search/hotels")
async def search_hotels(destination: str, check_in: str, check_out: str, budget: float = 0):
    service = HotelService()
    hotels = await service.search(destination, check_in, check_out, budget or None)
    return {"hotels": [h.model_dump() for h in hotels]}


@router.get("/search/activities")
async def search_activities(destination: str, mood: str = "relaxing"):
    service = ActivityService()
    activities = await service.search(destination, mood=mood)
    return {"activities": [a.model_dump() for a in activities]}


@router.get("/search/weather")
async def search_weather(destination: str, start_date: str, end_date: str):
    service = WeatherService()
    forecasts = await service.get_forecast(destination, start_date, end_date)
    return {"forecasts": [f.model_dump() for f in forecasts]}


# ── Optimize ───────────────────────────────────────────────────────────────────


@router.post("/optimize")
async def optimize(trip_id: str, day: int | None = None) -> dict:
    """Re-optimize the plan. If day is specified, regenerate only that day."""
    if trip_id not in _trips:
        raise HTTPException(404, "Trip not found")

    trip = TripRequest(**_trips[trip_id])
    orch = get_orchestrator()

    if day and trip_id in _itineraries:
        itinerary = Itinerary(**_itineraries[trip_id])
        new_itin, steps = await orch.regenerate_day(trip, itinerary, day)
        _itineraries[trip_id] = new_itin.model_dump()
        return {"itinerary": new_itin.model_dump(), "steps": [s.model_dump() for s in steps]}

    # Full re-plan
    reply, steps, itin_data, budget_data = await orch.run_full_plan(trip)
    if itin_data:
        _itineraries[trip_id] = itin_data
    return {"plan_summary": reply, "itinerary": itin_data, "budget": budget_data, "steps": [s.model_dump() for s in steps]}


# ── Calendar sync ──────────────────────────────────────────────────────────────


@router.post("/calendar/sync")
async def calendar_sync(trip_id: str) -> dict:
    """Generate iCal data for the trip."""
    if trip_id not in _itineraries:
        raise HTTPException(404, "Itinerary not found")

    itinerary = _itineraries[trip_id]
    # Generate simple iCal representation
    events = []
    for day in itinerary.get("days", []):
        for item in day.get("items", []):
            events.append({
                "summary": item["title"],
                "date": day["date"],
                "start_time": item.get("start_time"),
                "end_time": item.get("end_time"),
                "location": item.get("location", ""),
                "description": item.get("description", ""),
            })
    return {"trip_id": trip_id, "events": events, "event_count": len(events)}


# ── Export ─────────────────────────────────────────────────────────────────────


@router.get("/itinerary/export")
async def export_itinerary(trip_id: str, format: str = "html") -> Response:
    """Export itinerary as PDF or HTML."""
    if trip_id not in _itineraries:
        raise HTTPException(404, "Itinerary not found")

    itinerary = _itineraries[trip_id]
    trip = _trips.get(trip_id, {})

    if format == "pdf":
        pdf_bytes = await generate_pdf(itinerary, trip)
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": f"attachment; filename=itinerary_{trip_id}.pdf"},
        )

    html = render_itinerary_html(itinerary, trip)
    return HTMLResponse(content=html)


# ── Alerts ─────────────────────────────────────────────────────────────────────


@router.post("/alerts/subscribe")
async def subscribe_alerts(trip_id: str, email: str = "") -> dict:
    """Subscribe to trip alerts."""
    return {
        "trip_id": trip_id,
        "subscribed": True,
        "email": email,
        "message": "You will receive alerts for flight changes, weather updates, and price drops.",
    }


# ── Trip data ──────────────────────────────────────────────────────────────────


@router.get("/trip/{trip_id}")
async def get_trip(trip_id: str) -> dict:
    if trip_id not in _trips:
        raise HTTPException(404, "Trip not found")
    return {
        "trip": _trips[trip_id],
        "itinerary": _itineraries.get(trip_id),
        "chat_history": [m.model_dump() for m in _chat_history.get(trip_id, [])],
    }


@router.get("/trips")
async def list_trips() -> dict:
    return {
        "trips": [
            {"trip_id": tid, "destination": t.get("destination", ""), "start_date": t.get("start_date", "")}
            for tid, t in _trips.items()
        ]
    }
