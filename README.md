---
title: HolidayPilot
emoji: 🌍
colorFrom: blue
colorTo: green
sdk: docker
app_port: 7860
---

# 🌍 HolidayPilot — AI Multi-Agent Trip Planner

A production-ready agentic holiday planner that helps users plan trips end-to-end through a conversational interface and multi-agent workflow.

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                     Frontend (React)                     │
│  Chat Panel │ Trip Sidebar │ Itinerary/Budget/Weather    │
└──────────────────────┬──────────────────────────────────┘
                       │ REST API
┌──────────────────────┴──────────────────────────────────┐
│                   FastAPI Backend                         │
│  ┌─────────────────────────────────────────────────┐    │
│  │              Orchestrator                        │    │
│  │  ┌─────────┐ ┌────────┐ ┌──────────┐           │    │
│  │  │ Planner │ │Flights │ │  Hotels  │           │    │
│  │  └─────────┘ └────────┘ └──────────┘           │    │
│  │  ┌──────────┐ ┌──────┐ ┌───────┐              │    │
│  │  │Activities│ │ Food │ │Route  │              │    │
│  │  └──────────┘ └──────┘ └───────┘              │    │
│  │  ┌────────┐ ┌───────┐ ┌─────────┐ ┌────────┐ │    │
│  │  │Weather │ │Budget │ │Calendar │ │Monitor │ │    │
│  │  └────────┘ └───────┘ └─────────┘ └────────┘ │    │
│  └─────────────────────────────────────────────────┘    │
│                    Services Layer                         │
│  Flights │ Hotels │ Activities │ Food │ Weather │ Maps   │
└──────────────────────────────────────────────────────────┘
```

### Agent Roles

| Agent | Role | Tools |
|-------|------|-------|
| **Planner** | Conversational intake, field extraction, readiness check | extract_trip_info, ask_clarification |
| **Flights** | Search and compare flights | search_flights |
| **Hotels** | Search accommodations | search_hotels |
| **Activities** | Find attractions, tours, events | search_activities, search_events |
| **Food** | Restaurant recommendations | search_restaurants |
| **Route/Maps** | Geographic clustering, route optimization | get_route, get_distance_matrix |
| **Weather** | Forecasts, weather-aware timing | get_forecast |
| **Budget** | Budget scoring, trade-off analysis | calculate_budget, suggest_savings |
| **Calendar** | Day-by-day itinerary construction | build_schedule, export_ical |
| **Monitoring** | Disruption detection, re-planning alerts | check_flight_status, check_weather_alerts |

### Planning Pipeline

1. **Intake** — Planner Agent extracts trip details from chat
2. **Parallel Gather** — Flights, Hotels, Activities, Food, Weather run concurrently
3. **Sequential Optimize** — Budget → Route → Calendar build the itinerary
4. **Present** — Results shown with "Why this plan" explanations
5. **Approve** — User reviews and confirms before any booking

## Quick Start

### Backend

```bash
cd backend
pip install -e ".[dev]"
uvicorn app.main:app --reload
```

Server runs at http://localhost:8000. API docs at http://localhost:8000/docs.

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Opens at http://localhost:5173 with API proxy to backend.

### Run Tests

```bash
cd backend
pytest tests/ -v
```

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/chat` | Conversational trip planning |
| POST | `/api/plan` | Direct full planning pipeline |
| GET | `/api/search/flights` | Search flights |
| GET | `/api/search/hotels` | Search hotels |
| GET | `/api/search/activities` | Search activities |
| GET | `/api/search/weather` | Weather forecast |
| POST | `/api/optimize` | Re-optimize plan (full or single day) |
| POST | `/api/calendar/sync` | Export to calendar events |
| GET | `/api/itinerary/export` | Download itinerary (HTML/PDF) |
| POST | `/api/alerts/subscribe` | Subscribe to trip alerts |

## Features

- **Multi-agent coordination** with visible reasoning steps in UI
- **"Why this plan"** explanations for every recommendation
- **Backup activities** for weather-sensitive time blocks
- **Mood-based planning** (relaxing, romantic, adventure, family, workation)
- **Auto-generated packing list** and pre-trip checklist
- **Budget breakdown** with trade-off visualization
- **One-click day regeneration**
- **Trip summary card** with total spend, travel time, flexibility score
- **PDF/HTML itinerary export**
- **Weather-aware scheduling** — swaps outdoor activities on rainy days

## Extension Points

- **Add new agents**: Inherit from `BaseAgent`, implement `run()`, register in `registry.py`
- **Real API integrations**: Replace mock services in `app/services/` with real API calls
- **LLM integration**: Set `HP_OPENAI_API_KEY` env var; update Planner Agent to use LLM for extraction
- **Database**: Switch from in-memory to SQLite/PostgreSQL using the ORM models in `app/models/orm.py`
- **Group consensus mode**: Add voting logic in Planner Agent for multi-traveler trips
- **MCP tool protocol**: Wrap agents as MCP tools for broader agentic interop

## Project Structure

```
holidaypilot/
├── backend/
│   ├── app/
│   │   ├── agents/          # 10 specialized agents + orchestrator
│   │   ├── api/             # FastAPI route handlers
│   │   ├── core/            # Config, database, logging
│   │   ├── models/          # Pydantic schemas + ORM models
│   │   └── services/        # External service abstractions (mock)
│   ├── tests/               # Agent + API tests
│   └── pyproject.toml
└── frontend/
    ├── src/
    │   ├── components/      # React UI components
    │   ├── api.ts           # API client
    │   ├── types.ts         # TypeScript types
    │   └── App.tsx          # Main app layout
    └── package.json
```

## Sample Seed Trip

Use the `/api/plan` endpoint:

```bash
curl -X POST http://localhost:8000/api/plan \
  -H "Content-Type: application/json" \
  -d '{
    "destination": "Paris",
    "origin": "New York",
    "start_date": "2026-07-01",
    "end_date": "2026-07-04",
    "budget_total": 3000,
    "mood": "relaxing",
    "travelers": [{"name": "Alice", "interests": ["art", "food"]}],
    "interests": ["art", "food", "history"]
  }'
```
