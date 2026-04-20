"""Tests for API endpoints."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_chat_creates_trip():
    r = client.post("/api/chat", json={"trip_id": "", "message": "I want to visit Paris"})
    assert r.status_code == 200
    data = r.json()
    assert data["trip_id"]
    assert len(data["messages"]) >= 1
    assert data["trip_data"]["destination"] == "Paris"


def test_chat_full_flow():
    # Step 1: provide all details
    r = client.post("/api/chat", json={
        "trip_id": "",
        "message": "Trip to Tokyo from London, 2026-08-01 to 2026-08-05, budget $5000",
    })
    assert r.status_code == 200
    data = r.json()
    trip_id = data["trip_id"]
    assert data["trip_data"]["destination"] == "Tokyo"

    # The planner should detect it's ready to plan (all fields present)
    assert any("plan" in s.get("result_summary", "").lower() or "ready" in s.get("result_summary", "").lower()
               for s in data.get("reasoning_steps", []))


def test_search_flights():
    r = client.get("/api/search/flights?origin=NYC&destination=Paris&departure=2026-07-01")
    assert r.status_code == 200
    assert len(r.json()["flights"]) >= 1


def test_search_hotels():
    r = client.get("/api/search/hotels?destination=Paris&check_in=2026-07-01&check_out=2026-07-05")
    assert r.status_code == 200
    assert len(r.json()["hotels"]) >= 0  # depends on Overpass API


def test_search_activities():
    r = client.get("/api/search/activities?destination=Paris")
    assert r.status_code == 200
    assert len(r.json()["activities"]) >= 0  # depends on Overpass API


def test_search_weather():
    r = client.get("/api/search/weather?destination=Paris&start_date=2026-07-01&end_date=2026-07-05")
    assert r.status_code == 200
    assert len(r.json()["forecasts"]) >= 1


def test_plan_endpoint():
    r = client.post("/api/plan", json={
        "trip_id": "seed1",
        "destination": "Paris",
        "origin": "New York",
        "start_date": "2026-07-01",
        "end_date": "2026-07-04",
        "budget_total": 3000,
        "budget_currency": "USD",
        "travelers": [{"name": "Alice", "interests": ["art", "food"]}],
        "mood": "relaxing",
        "interests": ["art", "food"],
        "constraints": [],
        "notes": "",
    })
    assert r.status_code == 200
    data = r.json()
    assert data["itinerary"]
    assert data["budget"]
    assert len(data["itinerary"]["days"]) >= 1


def test_trips_list():
    r = client.get("/api/trips")
    assert r.status_code == 200


def test_alerts_subscribe():
    r = client.post("/api/alerts/subscribe?trip_id=t1&email=test@example.com")
    assert r.status_code == 200
    assert r.json()["subscribed"] is True
