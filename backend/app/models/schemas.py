"""Domain schemas for HolidayPilot."""
from __future__ import annotations

from datetime import date, datetime, time
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


# ── Enums ──────────────────────────────────────────────────────────────────────


class TripMood(str, Enum):
    relaxing = "relaxing"
    romantic = "romantic"
    adventure = "adventure"
    family = "family"
    workation = "workation"
    cultural = "cultural"


class AgentRole(str, Enum):
    planner = "planner"
    flights = "flights"
    hotels = "hotels"
    activities = "activities"
    food = "food"
    route = "route"
    weather = "weather"
    budget = "budget"
    calendar = "calendar"
    monitoring = "monitoring"


class AlertSeverity(str, Enum):
    info = "info"
    warning = "warning"
    critical = "critical"


# ── Traveler / Trip ───────────────────────────────────────────────────────────


class TravelerProfile(BaseModel):
    name: str
    age: int | None = None
    dietary_restrictions: list[str] = []
    accessibility_needs: list[str] = []
    interests: list[str] = []


class TripRequest(BaseModel):
    trip_id: str = ""
    destination: str = ""
    origin: str = ""
    start_date: date | None = None
    end_date: date | None = None
    budget_total: float | None = None
    budget_currency: str = "USD"
    num_adults: int | None = None
    num_children: int = 0
    travelers: list[TravelerProfile] = []
    mood: TripMood = TripMood.relaxing
    interests: list[str] = []
    constraints: list[str] = []
    notes: str = ""


# ── Search results ─────────────────────────────────────────────────────────────


class FlightOption(BaseModel):
    id: str
    airline: str
    departure_airport: str
    arrival_airport: str
    departure_time: datetime
    arrival_time: datetime
    price: float
    currency: str = "USD"
    stops: int = 0
    duration_minutes: int = 0
    booking_url: str = ""


class HotelOption(BaseModel):
    id: str
    name: str
    address: str
    rating: float = 0.0
    price_per_night: float = 0.0
    currency: str = "USD"
    amenities: list[str] = []
    booking_url: str = ""
    latitude: float = 0.0
    longitude: float = 0.0


class ActivityOption(BaseModel):
    id: str
    name: str
    category: str = ""
    description: str = ""
    price: float = 0.0
    currency: str = "USD"
    duration_minutes: int = 60
    rating: float = 0.0
    address: str = ""
    latitude: float = 0.0
    longitude: float = 0.0
    booking_url: str = ""
    weather_sensitive: bool = False


class RestaurantOption(BaseModel):
    id: str
    name: str
    cuisine: str = ""
    price_level: int = 2  # 1-4
    rating: float = 0.0
    address: str = ""
    latitude: float = 0.0
    longitude: float = 0.0
    booking_url: str = ""


class WeatherForecast(BaseModel):
    date: date
    high_temp_c: float
    low_temp_c: float
    condition: str  # sunny, cloudy, rainy, stormy
    precipitation_pct: int = 0
    uv_index: int = 0
    wind_kph: float = 0.0
    recommendation: str = ""


class RouteSegment(BaseModel):
    origin: str
    destination: str
    mode: str = "driving"  # driving, walking, transit
    distance_km: float = 0.0
    duration_minutes: int = 0


# ── Itinerary ──────────────────────────────────────────────────────────────────


class ItineraryItem(BaseModel):
    id: str
    day: int
    start_time: time | None = None
    end_time: time | None = None
    title: str
    category: str  # flight, hotel, activity, food, transport
    description: str = ""
    location: str = ""
    latitude: float = 0.0
    longitude: float = 0.0
    cost: float = 0.0
    currency: str = "USD"
    booking_url: str = ""
    backup: ItineraryItem | None = None
    reasoning: str = ""  # "Why this plan" explanation
    weather_note: str = ""
    confirmed: bool = False


class DayPlan(BaseModel):
    day: int
    date: date
    title: str = ""
    items: list[ItineraryItem] = []
    weather: WeatherForecast | None = None
    daily_spend: float = 0.0


class Itinerary(BaseModel):
    trip_id: str
    days: list[DayPlan] = []
    total_cost: float = 0.0
    currency: str = "USD"
    flexibility_score: float = 0.0  # 0-1 how flexible this plan is
    travel_time_hours: float = 0.0
    packing_list: list[str] = []
    checklist: list[str] = []


# ── Budget ─────────────────────────────────────────────────────────────────────


class BudgetCategory(BaseModel):
    category: str
    allocated: float
    spent: float = 0.0
    items: list[str] = []


class BudgetBreakdown(BaseModel):
    total_budget: float = 0.0
    total_estimated: float
    cost_per_person: float = 0.0
    num_travelers: int = 1
    currency: str = "USD"
    categories: list[BudgetCategory] = []
    within_budget: bool = True
    savings_tips: list[str] = []


# ── Recommendations ───────────────────────────────────────────────────────────


class Recommendation(BaseModel):
    id: str
    category: str
    title: str
    description: str
    reasoning: str  # "Why this" explanation
    score: float = 0.0  # 0-1 fit score
    cost: float = 0.0
    currency: str = "USD"
    alternatives: list[str] = []


# ── Chat ───────────────────────────────────────────────────────────────────────


class ChatMessage(BaseModel):
    role: str  # user, assistant, agent
    content: str
    agent: AgentRole | None = None
    metadata: dict[str, Any] = {}
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class ChatRequest(BaseModel):
    trip_id: str
    message: str
    context: dict[str, Any] = {}


class ChatResponse(BaseModel):
    trip_id: str
    messages: list[ChatMessage]
    trip_data: TripRequest | None = None
    reasoning_steps: list[ReasoningStep] = []
    itinerary: Itinerary | None = None
    budget: BudgetBreakdown | None = None


class ReasoningStep(BaseModel):
    agent: AgentRole
    action: str
    result_summary: str
    duration_ms: int = 0


# ── Alerts ─────────────────────────────────────────────────────────────────────


class AlertEvent(BaseModel):
    id: str
    trip_id: str
    severity: AlertSeverity
    title: str
    description: str
    agent: AgentRole
    suggested_action: str = ""
    created_at: datetime = Field(default_factory=datetime.utcnow)


# ── Trip Summary Card ─────────────────────────────────────────────────────────


class TripSummary(BaseModel):
    trip_id: str
    destination: str
    dates: str
    total_estimated_spend: float
    currency: str = "USD"
    total_travel_time_hours: float
    flexibility_score: float
    mood: TripMood
    traveler_count: int
    highlights: list[str] = []
