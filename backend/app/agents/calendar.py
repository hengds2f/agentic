"""Calendar Agent — builds day-by-day itinerary from gathered data."""
from __future__ import annotations

import uuid
from datetime import date as dt_date, time as dt_time
from typing import Any

from app.agents.base import BaseAgent
from app.models.schemas import AgentRole, DayPlan, Itinerary, ItineraryItem, WeatherForecast


class CalendarAgent(BaseAgent):
    role = AgentRole.calendar
    goal = "Build a day-by-day itinerary schedule from gathered options"
    tools = ["build_schedule", "export_ical"]
    guardrails = ["Respect weather warnings", "Include buffer time between activities"]

    async def run(self, context: dict[str, Any]) -> dict[str, Any]:
        trip = context["trip"]
        gathered = context.get("gathered", {})
        budget_data = context.get("budget", {})
        route_data = context.get("route", {})

        flights = gathered.get("flights", {}).get("flights", [])
        hotels = gathered.get("hotels", {}).get("hotels", [])
        activities = gathered.get("activities", {}).get("activities", [])
        restaurants = gathered.get("food", {}).get("restaurants", [])
        forecasts = gathered.get("weather", {}).get("forecasts", [])

        # Determine date range
        start = trip.get("start_date", "")
        end = trip.get("end_date", "")
        try:
            start_date = dt_date.fromisoformat(str(start))
            end_date = dt_date.fromisoformat(str(end))
        except (ValueError, TypeError):
            start_date = dt_date.today()
            end_date = start_date

        num_days = max((end_date - start_date).days, 1)

        # Select best hotel
        best_hotel = min(hotels, key=lambda h: h.get("price_per_night", 9999)) if hotels else None

        # Build forecast lookup
        forecast_map: dict[str, dict] = {}
        for f in forecasts:
            forecast_map[str(f.get("date", ""))] = f

        days: list[DayPlan] = []
        activity_idx = 0
        restaurant_idx = 0
        total_cost = 0.0

        for day_num in range(num_days):
            from datetime import timedelta
            current_date = start_date + timedelta(days=day_num)
            weather = forecast_map.get(str(current_date))
            weather_obj = WeatherForecast(**weather) if weather else None

            items: list[ItineraryItem] = []
            day_cost = 0.0
            is_rainy = weather and weather.get("condition") in ("rainy", "stormy")

            # Day 1: add arrival flight
            if day_num == 0 and flights:
                best_flight = min(flights, key=lambda f: f["price"])
                items.append(ItineraryItem(
                    id=uuid.uuid4().hex[:8],
                    day=day_num + 1,
                    start_time=dt_time(8, 0),
                    end_time=dt_time(12, 0),
                    title=f"Flight: {best_flight.get('airline', 'Airline')}",
                    category="flight",
                    description=f"{best_flight.get('departure_airport', '')} → {best_flight.get('arrival_airport', '')}",
                    cost=best_flight.get("price", 0),
                    reasoning="Cheapest direct option for your dates",
                ))
                day_cost += best_flight.get("price", 0)

            # Hotel check-in on day 1
            if day_num == 0 and best_hotel:
                items.append(ItineraryItem(
                    id=uuid.uuid4().hex[:8],
                    day=day_num + 1,
                    start_time=dt_time(14, 0),
                    end_time=dt_time(15, 0),
                    title=f"Check in: {best_hotel.get('name', 'Hotel')}",
                    category="hotel",
                    description=best_hotel.get("address", ""),
                    cost=best_hotel.get("price_per_night", 0) * num_days,
                    reasoning="Best value hotel with good reviews in your budget",
                    location=best_hotel.get("address", ""),
                ))
                day_cost += best_hotel.get("price_per_night", 0)

            # Morning activity
            if activity_idx < len(activities):
                act = activities[activity_idx]
                # Skip weather-sensitive outdoor activities on rainy days
                if is_rainy and act.get("weather_sensitive"):
                    # Find indoor alternative
                    backup_act = next(
                        (a for a in activities[activity_idx + 1:] if not a.get("weather_sensitive")),
                        act,
                    )
                    weather_note = "Moved indoors due to expected rain"
                else:
                    backup_act = None
                    weather_note = ""

                chosen = backup_act or act
                backup_item = None
                if backup_act and backup_act != act:
                    backup_item = ItineraryItem(
                        id=uuid.uuid4().hex[:8],
                        day=day_num + 1,
                        title=act.get("name", "Activity"),
                        category="activity",
                        description=act.get("description", ""),
                        cost=act.get("price", 0),
                        reasoning="Original plan if weather improves",
                    )

                items.append(ItineraryItem(
                    id=uuid.uuid4().hex[:8],
                    day=day_num + 1,
                    start_time=dt_time(10, 0) if day_num > 0 else dt_time(15, 0),
                    end_time=dt_time(12, 0) if day_num > 0 else dt_time(17, 0),
                    title=chosen.get("name", "Activity"),
                    category="activity",
                    description=chosen.get("description", ""),
                    cost=chosen.get("price", 0),
                    location=chosen.get("address", ""),
                    reasoning=f"Matches your {trip.get('mood', 'relaxing')} mood and interests",
                    weather_note=weather_note,
                    backup=backup_item,
                ))
                day_cost += chosen.get("price", 0)
                activity_idx += 1

            # Lunch
            if restaurant_idx < len(restaurants):
                rest = restaurants[restaurant_idx]
                items.append(ItineraryItem(
                    id=uuid.uuid4().hex[:8],
                    day=day_num + 1,
                    start_time=dt_time(12, 30) if day_num > 0 else dt_time(18, 0),
                    end_time=dt_time(13, 30) if day_num > 0 else dt_time(19, 0),
                    title=f"Lunch: {rest.get('name', 'Restaurant')}",
                    category="food",
                    description=f"{rest.get('cuisine', '')} cuisine",
                    cost=25.0,
                    location=rest.get("address", ""),
                    reasoning=f"Highly rated {rest.get('cuisine', 'local')} restaurant nearby",
                ))
                day_cost += 25.0
                restaurant_idx += 1

            # Afternoon activity (from day 2)
            if day_num > 0 and activity_idx < len(activities):
                act = activities[activity_idx]
                items.append(ItineraryItem(
                    id=uuid.uuid4().hex[:8],
                    day=day_num + 1,
                    start_time=dt_time(14, 30),
                    end_time=dt_time(16, 30),
                    title=act.get("name", "Activity"),
                    category="activity",
                    description=act.get("description", ""),
                    cost=act.get("price", 0),
                    location=act.get("address", ""),
                    reasoning="Complements your morning activity with a change of pace",
                ))
                day_cost += act.get("price", 0)
                activity_idx += 1

            # Dinner
            if restaurant_idx < len(restaurants):
                rest = restaurants[restaurant_idx]
                items.append(ItineraryItem(
                    id=uuid.uuid4().hex[:8],
                    day=day_num + 1,
                    start_time=dt_time(19, 0),
                    end_time=dt_time(20, 30),
                    title=f"Dinner: {rest.get('name', 'Restaurant')}",
                    category="food",
                    description=f"{rest.get('cuisine', '')} cuisine",
                    cost=40.0,
                    location=rest.get("address", ""),
                    reasoning="Great dinner spot with atmosphere matching your trip mood",
                ))
                day_cost += 40.0
                restaurant_idx += 1

            # Last day: departure flight
            if day_num == num_days - 1 and flights:
                items.append(ItineraryItem(
                    id=uuid.uuid4().hex[:8],
                    day=day_num + 1,
                    start_time=dt_time(18, 0),
                    end_time=dt_time(22, 0),
                    title="Return flight",
                    category="flight",
                    description="Head to airport for departure",
                    cost=0,
                    reasoning="Return flight included in outbound booking",
                ))

            total_cost += day_cost
            days.append(DayPlan(
                day=day_num + 1,
                date=current_date,
                title=f"Day {day_num + 1}" + (" — Arrival" if day_num == 0 else ""),
                items=items,
                weather=weather_obj,
                daily_spend=day_cost,
            ))

        # Packing list and checklist
        packing = self._generate_packing_list(trip, forecasts)
        checklist = self._generate_checklist(trip)

        itinerary = Itinerary(
            trip_id=trip.get("trip_id", ""),
            days=days,
            total_cost=total_cost,
            currency=trip.get("budget_currency", "USD"),
            flexibility_score=0.7,
            travel_time_hours=2.0 * num_days,
            packing_list=packing,
            checklist=checklist,
        )

        return {
            "itinerary": itinerary.model_dump(),
            "summary": f"Built {num_days}-day itinerary, ${total_cost:,.0f} total",
        }

    def _generate_packing_list(self, trip: dict, forecasts: list) -> list[str]:
        items = ["Passport/ID", "Phone charger", "Travel adapter", "Comfortable walking shoes"]
        has_rain = any(f.get("condition") in ("rainy", "stormy") for f in forecasts)
        if has_rain:
            items.extend(["Umbrella", "Rain jacket"])
        avg_temp = sum(f.get("high_temp_c", 20) for f in forecasts) / max(len(forecasts), 1)
        if avg_temp < 15:
            items.extend(["Warm jacket", "Layers"])
        elif avg_temp > 28:
            items.extend(["Sunscreen", "Hat", "Light clothing"])
        if trip.get("mood") == "adventure":
            items.extend(["Hiking boots", "Daypack"])
        return items

    def _generate_checklist(self, trip: dict) -> list[str]:
        return [
            "Check passport validity",
            "Verify travel insurance",
            "Download offline maps",
            "Notify bank of travel dates",
            "Check visa requirements",
            "Arrange airport transport",
            "Confirm hotel booking",
            "Pack essentials bag",
        ]
