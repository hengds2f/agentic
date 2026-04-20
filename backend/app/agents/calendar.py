"""Calendar Agent — builds day-by-day itinerary from gathered data."""
from __future__ import annotations

import uuid
from datetime import date as dt_date, datetime, time as dt_time, timedelta
from math import atan2, cos, radians, sin, sqrt
from typing import Any
from urllib.parse import quote

from app.agents.base import BaseAgent
from app.models.schemas import AgentRole, DayPlan, Itinerary, ItineraryItem, WeatherForecast


def _haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Distance in km between two lat/lon points."""
    R = 6371.0
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
    return R * 2 * atan2(sqrt(a), sqrt(1 - a))


def _order_cities_nearest(cities: list[dict]) -> list[dict]:
    """Order cities using nearest-neighbor for a touring route."""
    if len(cities) <= 1:
        return list(cities)
    ordered = [cities[0]]
    remaining = list(cities[1:])
    while remaining:
        last = ordered[-1]
        nearest = min(remaining, key=lambda c: _haversine(
            last.get("lat", 0), last.get("lon", 0),
            c.get("lat", 0), c.get("lon", 0),
        ))
        ordered.append(nearest)
        remaining.remove(nearest)
    return ordered


def _allocate_days(num_days: int, num_cities: int) -> list[int]:
    """Distribute trip days across cities."""
    if num_cities <= 0:
        return []
    if num_cities == 1:
        return [num_days]
    base = max(num_days // num_cities, 1)
    allocation = [base] * num_cities
    remainder = num_days - sum(allocation)
    for i in range(max(remainder, 0)):
        allocation[i % num_cities] += 1
    return allocation


def _build_city_schedule(num_days: int, cities: list[dict]) -> list[dict]:
    """Return a list of length num_days, each element being the city dict for that day."""
    if not cities:
        return [{"name": "the destination", "lat": 0, "lon": 0}] * num_days
    ordered = _order_cities_nearest(cities)
    alloc = _allocate_days(num_days, len(ordered))
    schedule: list[dict] = []
    for city, days in zip(ordered, alloc):
        schedule.extend([city] * days)
    # Pad if needed
    while len(schedule) < num_days:
        schedule.append(ordered[-1])
    return schedule[:num_days]


def _build_maps_url(cities: list[dict], destination: str) -> str:
    """Build a Google Maps directions URL through all cities."""
    if not cities or len(cities) < 2:
        return f"https://www.google.com/maps/search/{quote(destination)}"
    parts = "/".join(quote(f"{c['name']}, {destination}") for c in cities)
    return f"https://www.google.com/maps/dir/{parts}/"


def _cluster_activities(activities: list[dict], num_groups: int) -> list[list[dict]]:
    """Simple geographic clustering: sort by distance from centroid, split into groups."""
    if not activities:
        return [[] for _ in range(num_groups)]

    avg_lat = sum(a.get("latitude", 0) for a in activities) / len(activities)
    avg_lon = sum(a.get("longitude", 0) for a in activities) / len(activities)

    from math import atan2 as _atan2
    for a in activities:
        a["_angle"] = _atan2(a.get("latitude", 0) - avg_lat, a.get("longitude", 0) - avg_lon)
    sorted_acts = sorted(activities, key=lambda a: a["_angle"])

    groups: list[list[dict]] = [[] for _ in range(num_groups)]
    for i, act in enumerate(sorted_acts):
        groups[i % num_groups].append(act)
    return groups


class CalendarAgent(BaseAgent):
    role = AgentRole.calendar
    goal = "Build a day-by-day itinerary schedule from gathered options"
    tools = ["build_schedule", "export_ical"]
    guardrails = ["Respect weather warnings", "Include buffer time between activities"]

    async def run(self, context: dict[str, Any]) -> dict[str, Any]:
        trip = context["trip"]

        # ── Single-day regeneration ──
        regen_day = context.get("regenerate_day")
        if regen_day and context.get("itinerary"):
            return await self._regenerate_single_day(context, regen_day)

        gathered = context.get("gathered", {})
        cities = context.get("cities", [])

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
        destination = trip.get("destination", "the destination")
        num_adults = trip.get("num_adults", 1) or 1
        num_children = trip.get("num_children", 0) or 0
        total_pax = num_adults + num_children
        cost_multiplier = num_adults + num_children * 0.5

        # ── Build city schedule: assign a city to each day ──
        city_schedule = _build_city_schedule(num_days, cities)

        # ── Group activities, restaurants, hotels by city ──
        def _group_by_city(items: list[dict]) -> dict[str, list[dict]]:
            groups: dict[str, list[dict]] = {}
            for item in items:
                city = item.get("_city", destination)
                groups.setdefault(city, []).append(item)
            return groups

        acts_by_city = _group_by_city(activities)
        rests_by_city = _group_by_city(restaurants)
        hotels_by_city = _group_by_city(hotels)

        # For each city, pick the best hotel (highest rating)
        best_hotel_per_city: dict[str, dict] = {}
        for city_name, city_hotels in hotels_by_city.items():
            if city_hotels:
                best_hotel_per_city[city_name] = max(city_hotels, key=lambda h: h.get("rating", 0))
        # Global fallback hotel
        fallback_hotel = max(hotels, key=lambda h: h.get("rating", 0)) if hotels else None

        # Per-city activity index trackers
        city_act_idx: dict[str, int] = {}
        city_rest_idx: dict[str, int] = {}

        # Build forecast lookup
        forecast_map: dict[str, dict] = {}
        for f in forecasts:
            forecast_map[str(f.get("date", ""))] = f

        # ── Flight arrival time for Day 1 scheduling ──
        best_flight = min(flights, key=lambda f: f["price"]) if flights else None
        arrival_hour, arrival_minute = 12, 0
        if best_flight:
            arr_time_str = best_flight.get("arrival_time", "")
            try:
                if isinstance(arr_time_str, str) and "T" in arr_time_str:
                    arr_dt = datetime.fromisoformat(arr_time_str)
                    arrival_hour, arrival_minute = arr_dt.hour, arr_dt.minute
                elif hasattr(arr_time_str, "hour"):
                    arrival_hour, arrival_minute = arr_time_str.hour, arr_time_str.minute
            except (ValueError, TypeError):
                pass

        post_arrival_hour = min(arrival_hour + 1, 23)
        post_arrival_minute = arrival_minute

        # ── Build day-by-day itinerary ──
        indoor_acts = [a for a in activities if not a.get("weather_sensitive", False)]
        days: list[DayPlan] = []
        total_cost = 0.0
        ordered_cities = _order_cities_nearest(cities) if cities else []

        for day_num in range(num_days):
            current_date = start_date + timedelta(days=day_num)
            weather = forecast_map.get(str(current_date))
            weather_obj = WeatherForecast(**weather) if weather else None

            items: list[ItineraryItem] = []
            day_cost = 0.0
            is_rainy = weather and weather.get("condition") in ("rainy", "stormy")
            is_first_day = day_num == 0
            is_last_day = day_num == num_days - 1

            # Current city for this day
            day_city = city_schedule[day_num]
            day_city_name = day_city.get("name", destination)
            prev_city = city_schedule[day_num - 1] if day_num > 0 else None
            city_changed = prev_city and prev_city.get("name") != day_city_name

            # Get activities/restaurants for this city
            city_acts = acts_by_city.get(day_city_name, activities)
            city_rests = rests_by_city.get(day_city_name, restaurants)
            best_hotel = best_hotel_per_city.get(day_city_name, fallback_hotel)

            act_idx = city_act_idx.get(day_city_name, 0)
            rest_idx = city_rest_idx.get(day_city_name, 0)

            # ── Day 1: Arrival flights ──
            if is_first_day and best_flight:
                flight_cost = best_flight.get("price", 0) * cost_multiplier
                flight_legs = best_flight.get("legs", [])

                if flight_legs:
                    for leg_idx, leg in enumerate(flight_legs):
                        leg_dep = leg.get("departure_time", "")
                        leg_arr = leg.get("arrival_time", "")
                        leg_airline = leg.get("airline", best_flight.get("airline", "Airline"))
                        try:
                            dep_dt = datetime.fromisoformat(leg_dep) if isinstance(leg_dep, str) and "T" in leg_dep else datetime.combine(current_date, dt_time(8, 0))
                            arr_dt = datetime.fromisoformat(leg_arr) if isinstance(leg_arr, str) and "T" in leg_arr else dep_dt + timedelta(hours=3)
                        except (ValueError, TypeError):
                            dep_dt = datetime.combine(current_date, dt_time(8, 0))
                            arr_dt = dep_dt + timedelta(hours=3)

                        leg_from = leg.get("departure_airport", "")
                        leg_to = leg.get("arrival_airport", "")
                        is_last_leg = leg_idx == len(flight_legs) - 1

                        items.append(ItineraryItem(
                            id=uuid.uuid4().hex[:8],
                            day=day_num + 1,
                            start_time=dep_dt.time(),
                            end_time=arr_dt.time(),
                            title=f"✈️ {leg_airline}: {leg_from} → {leg_to}",
                            category="flight",
                            description=(
                                f"Leg {leg_idx + 1} of {len(flight_legs)} · "
                                f"{leg.get('duration_minutes', 0) // 60}h{leg.get('duration_minutes', 0) % 60:02d}m"
                                + (f" ({total_pax} pax)" if is_last_leg else "")
                            ),
                            location=leg_to,
                            cost=flight_cost if is_last_leg else 0,
                            booking_url=best_flight.get("booking_url", ""),
                            reasoning=(
                                f"{'Direct flight' if len(flight_legs) == 1 else f'{len(flight_legs)}-leg connection'} "
                                f"× {total_pax} travelers"
                            ) if is_last_leg else f"Connection via {leg_to}",
                        ))
                else:
                    items.append(ItineraryItem(
                        id=uuid.uuid4().hex[:8],
                        day=day_num + 1,
                        start_time=dt_time(8, 0),
                        end_time=dt_time(arrival_hour, arrival_minute),
                        title=f"✈️ {best_flight.get('airline', 'Airline')}: {best_flight.get('departure_airport', '')} → {best_flight.get('arrival_airport', '')}",
                        category="flight",
                        description=f"{best_flight.get('stops', 0)} stop(s) · {best_flight.get('duration_minutes', 0) // 60}h ({total_pax} pax)",
                        location=day_city_name,
                        cost=best_flight.get("price", 0) * cost_multiplier,
                        booking_url=best_flight.get("booking_url", ""),
                        reasoning=f"Best value flight × {total_pax} travelers",
                    ))
                day_cost += best_flight.get("price", 0) * cost_multiplier

            # ── Travel between cities ──
            if city_changed and not is_first_day:
                prev_name = prev_city.get("name", "")
                dist = _haversine(
                    prev_city.get("lat", 0), prev_city.get("lon", 0),
                    day_city.get("lat", 0), day_city.get("lon", 0),
                )
                travel_hours = max(dist / 200, 1)  # rough estimate: 200 km/h average
                items.append(ItineraryItem(
                    id=uuid.uuid4().hex[:8],
                    day=day_num + 1,
                    start_time=dt_time(8, 0),
                    end_time=dt_time(min(8 + int(travel_hours) + 1, 12), 0),
                    title=f"🚅 Travel: {prev_name} → {day_city_name}",
                    category="transport",
                    description=f"~{dist:.0f} km · {travel_hours:.1f}h estimated travel time",
                    location=day_city_name,
                    latitude=day_city.get("lat", 0.0),
                    longitude=day_city.get("lon", 0.0),
                    cost=0,
                    reasoning=f"Moving to {day_city_name} for the next leg of the trip",
                ))

            # ── Hotel ──
            if best_hotel:
                hotel_cost_per_night = best_hotel.get("price_per_night", 0)
                hotel_loc = f"{best_hotel.get('name', 'Hotel')}, {day_city_name}"
                if is_first_day:
                    check_in_time = dt_time(max(post_arrival_hour, 14), 0)
                    items.append(ItineraryItem(
                        id=uuid.uuid4().hex[:8], day=day_num + 1,
                        start_time=check_in_time,
                        end_time=dt_time(min(check_in_time.hour + 1, 23), 0),
                        title=f"🏨 Check in: {best_hotel.get('name', 'Hotel')}",
                        category="hotel",
                        description=f"⭐ {best_hotel.get('rating', 4.0)} · {', '.join(best_hotel.get('amenities', [])[:3])}",
                        cost=hotel_cost_per_night,
                        location=day_city_name,
                        latitude=best_hotel.get("latitude", 0.0),
                        longitude=best_hotel.get("longitude", 0.0),
                        booking_url=best_hotel.get("booking_url", ""),
                        reasoning=f"Best rated hotel in {day_city_name} — ⭐ {best_hotel.get('rating', 4.0)}",
                    ))
                elif is_last_day:
                    items.append(ItineraryItem(
                        id=uuid.uuid4().hex[:8], day=day_num + 1,
                        start_time=dt_time(11, 0), end_time=dt_time(12, 0),
                        title=f"🏨 Check out: {best_hotel.get('name', 'Hotel')}",
                        category="hotel",
                        description=f"⭐ {best_hotel.get('rating', 4.0)} · Check-out by noon",
                        cost=hotel_cost_per_night,
                        location=day_city_name,
                        latitude=best_hotel.get("latitude", 0.0),
                        longitude=best_hotel.get("longitude", 0.0),
                        booking_url=best_hotel.get("booking_url", ""),
                        reasoning="Check out and store luggage if needed",
                    ))
                elif city_changed:
                    # New city check-in
                    items.append(ItineraryItem(
                        id=uuid.uuid4().hex[:8], day=day_num + 1,
                        start_time=dt_time(13, 0), end_time=dt_time(14, 0),
                        title=f"🏨 Check in: {best_hotel.get('name', 'Hotel')}",
                        category="hotel",
                        description=f"⭐ {best_hotel.get('rating', 4.0)} · {', '.join(best_hotel.get('amenities', [])[:3])}",
                        cost=hotel_cost_per_night,
                        location=day_city_name,
                        latitude=best_hotel.get("latitude", 0.0),
                        longitude=best_hotel.get("longitude", 0.0),
                        booking_url=best_hotel.get("booking_url", ""),
                        reasoning=f"Best rated hotel in {day_city_name}",
                    ))
                else:
                    items.append(ItineraryItem(
                        id=uuid.uuid4().hex[:8], day=day_num + 1,
                        start_time=dt_time(7, 0), end_time=dt_time(8, 0),
                        title=f"🏨 {best_hotel.get('name', 'Hotel')}",
                        category="hotel",
                        description=f"⭐ {best_hotel.get('rating', 4.0)} · Night {day_num + 1} of {num_days}",
                        cost=hotel_cost_per_night,
                        location=day_city_name,
                        latitude=best_hotel.get("latitude", 0.0),
                        longitude=best_hotel.get("longitude", 0.0),
                        booking_url=best_hotel.get("booking_url", ""),
                        reasoning=f"Best rated hotel in {day_city_name}",
                    ))
                day_cost += hotel_cost_per_night

            # ── Sightseeing activities ──
            acts_per_day = 3
            if is_first_day and num_days > 1:
                first_activity_hour = max(post_arrival_hour + 2, 15)
                if first_activity_hour < 20 and city_acts:
                    chosen = city_acts[act_idx % len(city_acts)] if city_acts else None
                    if chosen:
                        self._add_activities(items, [chosen], day_num, is_rainy, indoor_acts, trip,
                                             start_times=[dt_time(first_activity_hour, 0)],
                                             end_times=[dt_time(min(first_activity_hour + 2, 21), 0)],
                                             cost_multiplier=cost_multiplier, city_name=day_city_name)
                        day_cost += chosen.get("price", 0) * cost_multiplier
                        act_idx += 1
            elif is_last_day and num_days > 1:
                if city_acts:
                    chosen = city_acts[act_idx % len(city_acts)]
                    self._add_activities(items, [chosen], day_num, is_rainy, indoor_acts, trip,
                                         start_times=[dt_time(9, 0)],
                                         end_times=[dt_time(11, 0)],
                                         cost_multiplier=cost_multiplier, city_name=day_city_name)
                    day_cost += chosen.get("price", 0) * cost_multiplier
                    act_idx += 1
            else:
                # Full day: up to 3 activities
                day_acts_list: list[dict] = []
                for _ in range(acts_per_day):
                    if city_acts:
                        day_acts_list.append(city_acts[act_idx % len(city_acts)])
                        act_idx += 1
                start_hour = 14 if city_changed else 9
                s_times = [dt_time(start_hour, 30), dt_time(max(start_hour + 2, 14), 0), dt_time(16, 0)]
                e_times = [dt_time(start_hour + 2, 0), dt_time(max(start_hour + 4, 15), 30), dt_time(17, 30)]
                if city_changed:
                    # After travel + check-in, only 2 activities
                    day_acts_list = day_acts_list[:2]
                    s_times = [dt_time(14, 30), dt_time(16, 30)]
                    e_times = [dt_time(16, 0), dt_time(18, 0)]
                self._add_activities(items, day_acts_list, day_num, is_rainy, indoor_acts, trip,
                                     start_times=s_times, end_times=e_times,
                                     cost_multiplier=cost_multiplier, city_name=day_city_name)
                day_cost += sum(a.get("price", 0) for a in day_acts_list) * cost_multiplier

            city_act_idx[day_city_name] = act_idx

            # ── Meals ──
            if city_rests:
                rest = city_rests[rest_idx % len(city_rests)]
                if is_first_day:
                    lunch_hour = max(post_arrival_hour + 1, 13)
                    if lunch_hour > 15:
                        lunch_hour = 13
                else:
                    lunch_hour = 12
                lunch_time = dt_time(min(lunch_hour, 15), 0)
                lunch_cost = 25.0 * cost_multiplier
                items.append(ItineraryItem(
                    id=uuid.uuid4().hex[:8], day=day_num + 1,
                    start_time=lunch_time,
                    end_time=dt_time(lunch_time.hour + 1, 0),
                    title=f"🍽️ Lunch: {rest.get('name', 'Restaurant')}",
                    category="food",
                    description=f"{rest.get('cuisine', '')} cuisine — ⭐ {rest.get('rating', 4.0)}",
                    cost=lunch_cost,
                    location=day_city_name,
                    latitude=rest.get("latitude", 0.0),
                    longitude=rest.get("longitude", 0.0),
                    booking_url=rest.get("booking_url", ""),
                    reasoning=f"Highly rated {rest.get('cuisine', 'local')} restaurant in {day_city_name}",
                ))
                day_cost += lunch_cost
                rest_idx += 1

                rest = city_rests[rest_idx % len(city_rests)]
                dinner_cost = 40.0 * cost_multiplier
                items.append(ItineraryItem(
                    id=uuid.uuid4().hex[:8], day=day_num + 1,
                    start_time=dt_time(19, 0), end_time=dt_time(20, 30),
                    title=f"🍽️ Dinner: {rest.get('name', 'Restaurant')}",
                    category="food",
                    description=f"{rest.get('cuisine', '')} cuisine — ⭐ {rest.get('rating', 4.0)}",
                    cost=dinner_cost,
                    location=day_city_name,
                    latitude=rest.get("latitude", 0.0),
                    longitude=rest.get("longitude", 0.0),
                    booking_url=rest.get("booking_url", ""),
                    reasoning=f"Top-rated dinner spot in {day_city_name}",
                ))
                day_cost += dinner_cost
                rest_idx += 1

            city_rest_idx[day_city_name] = rest_idx

            # ── Last day: departure ──
            if is_last_day and best_flight:
                items.append(ItineraryItem(
                    id=uuid.uuid4().hex[:8], day=day_num + 1,
                    start_time=dt_time(16, 0), end_time=dt_time(17, 0),
                    title="🚕 Transfer to airport",
                    category="transport",
                    description="Allow 1-2 hours before departure",
                    location=day_city_name,
                    cost=0,
                    reasoning="Buffer time for airport transfer and check-in",
                ))
                items.append(ItineraryItem(
                    id=uuid.uuid4().hex[:8], day=day_num + 1,
                    start_time=dt_time(18, 0), end_time=dt_time(22, 0),
                    title=f"✈️ Return flight: {best_flight.get('arrival_airport', '')} → {best_flight.get('departure_airport', '')}",
                    category="flight",
                    description="Return journey",
                    location=best_flight.get("arrival_airport", ""),
                    cost=0,
                    booking_url=best_flight.get("booking_url", ""),
                    reasoning="Return flight included in outbound booking",
                ))

            items.sort(key=lambda it: (it.start_time or dt_time(0, 0)))

            # ── Day title with city name ──
            if is_first_day:
                day_title = f"Arrival in {day_city_name}"
            elif is_last_day and num_days > 1:
                day_title = f"Departure from {day_city_name}"
            elif city_changed:
                day_title = f"Travel to {day_city_name}"
            else:
                day_title = f"Exploring {day_city_name}"

            total_cost += day_cost
            days.append(DayPlan(
                day=day_num + 1,
                date=current_date,
                title=f"Day {day_num + 1} — {day_title}",
                items=items,
                weather=weather_obj,
                daily_spend=day_cost,
            ))

        # Build Google Maps route URL + city list for frontend map
        map_url = _build_maps_url(ordered_cities, destination)
        city_data = [{"name": c["name"], "lat": c.get("lat", 0), "lon": c.get("lon", 0)}
                     for c in ordered_cities] if ordered_cities else []

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
            map_url=map_url,
            cities=city_data,
        )

        city_names = list(dict.fromkeys(cs.get("name", "") for cs in city_schedule))
        return {
            "itinerary": itinerary.model_dump(),
            "summary": f"Built {num_days}-day itinerary visiting {', '.join(city_names)} — ${total_cost:,.0f} total",
        }

    async def _regenerate_single_day(self, context: dict[str, Any], day_num: int) -> dict[str, Any]:
        """Rebuild only a single day, keeping all other days from the existing itinerary."""
        trip = context["trip"]
        existing = context["itinerary"]
        existing_days = existing.get("days", [])

        # Fresh data from the regeneration pipeline (top-level context keys)
        activities = context.get("activities", {}).get("activities", [])
        restaurants = context.get("food", {}).get("restaurants", [])

        num_adults = trip.get("num_adults", 1) or 1
        num_children = trip.get("num_children", 0) or 0
        total_pax = num_adults + num_children
        cost_multiplier = num_adults + num_children * 0.5
        destination = trip.get("destination", "the destination")

        # Find the existing day to replace
        new_days = []
        for day_data in existing_days:
            if day_data.get("day") != day_num:
                new_days.append(day_data)
                continue

            # Rebuild this day
            current_date = day_data.get("date", "")
            weather_data = day_data.get("weather")
            weather_obj = WeatherForecast(**weather_data) if weather_data else None
            is_rainy = weather_data and weather_data.get("condition") in ("rainy", "stormy") if weather_data else False
            indoor_acts = [a for a in activities if not a.get("weather_sensitive", False)]

            items: list[ItineraryItem] = []
            day_cost = 0.0

            # Keep flights and hotel items from the existing day
            for item in day_data.get("items", []):
                if item.get("category") in ("flight", "hotel"):
                    items.append(ItineraryItem(**item))
                    day_cost += item.get("cost", 0)

            # Add fresh activities (up to 3)
            day_acts = activities[:3] if activities else []
            self._add_activities(items, day_acts, day_num - 1, is_rainy, indoor_acts, trip,
                                 start_times=[dt_time(9, 30), dt_time(14, 0), dt_time(16, 0)],
                                 end_times=[dt_time(11, 30), dt_time(15, 30), dt_time(17, 30)],
                                 cost_multiplier=cost_multiplier)
            day_cost += sum(a.get("price", 0) for a in day_acts) * cost_multiplier

            # Add fresh restaurants (lunch + dinner)
            if restaurants:
                lunch_cost = 25.0 * cost_multiplier
                rest = restaurants[0]
                items.append(ItineraryItem(
                    id=uuid.uuid4().hex[:8], day=day_num,
                    start_time=dt_time(12, 0), end_time=dt_time(13, 0),
                    title=f"Lunch: {rest.get('name', 'Restaurant')}",
                    category="food",
                    description=f"{rest.get('cuisine', '')} cuisine — ⭐ {rest.get('rating', 4.0)}",
                    cost=lunch_cost,
                    location=rest.get("address", ""),
                    latitude=rest.get("latitude", 0.0),
                    longitude=rest.get("longitude", 0.0),
                    booking_url=rest.get("booking_url", ""),
                    reasoning=f"Highly rated {rest.get('cuisine', 'local')} restaurant",
                ))
                day_cost += lunch_cost

                rest2 = restaurants[1 % len(restaurants)]
                dinner_cost = 40.0 * cost_multiplier
                items.append(ItineraryItem(
                    id=uuid.uuid4().hex[:8], day=day_num,
                    start_time=dt_time(19, 0), end_time=dt_time(20, 30),
                    title=f"Dinner: {rest2.get('name', 'Restaurant')}",
                    category="food",
                    description=f"{rest2.get('cuisine', '')} cuisine — ⭐ {rest2.get('rating', 4.0)}",
                    cost=dinner_cost,
                    location=rest2.get("address", ""),
                    latitude=rest2.get("latitude", 0.0),
                    longitude=rest2.get("longitude", 0.0),
                    booking_url=rest2.get("booking_url", ""),
                    reasoning="Top-rated dinner spot — check Google Maps for reviews",
                ))
                day_cost += dinner_cost

            items.sort(key=lambda it: (it.start_time or dt_time(0, 0)))

            day_title = _day_theme(day_acts[:3])
            new_days.append(DayPlan(
                day=day_num,
                date=dt_date.fromisoformat(str(current_date)) if current_date else dt_date.today(),
                title=f"Day {day_num} — {day_title}",
                items=items,
                weather=weather_obj,
                daily_spend=day_cost,
            ).model_dump())

        total_cost = sum(d.get("daily_spend", 0) if isinstance(d, dict) else d.daily_spend for d in new_days)

        result_itin = dict(existing)
        result_itin["days"] = new_days
        result_itin["total_cost"] = total_cost

        return {
            "itinerary": result_itin,
            "summary": f"Regenerated Day {day_num} with {len(activities)} new activities",
        }

    def _add_activities(
        self,
        items: list[ItineraryItem],
        day_acts: list[dict],
        day_num: int,
        is_rainy: bool,
        indoor_acts: list[dict],
        trip: dict,
        start_times: list[dt_time],
        end_times: list[dt_time],
        cost_multiplier: float = 1.0,
        city_name: str = "",
    ) -> None:
        """Add activity items to the day, handling weather substitution."""
        used_indoor: set[str] = set()
        loc_label = city_name or trip.get("destination", "the area")
        for i, act in enumerate(day_acts):
            if i >= len(start_times):
                break
            weather_note = ""
            backup_item = None
            chosen = act

            if is_rainy and act.get("weather_sensitive"):
                alt = next(
                    (a for a in indoor_acts
                     if a.get("id") not in used_indoor and a.get("id") != act.get("id")),
                    None,
                )
                if alt:
                    used_indoor.add(alt["id"])
                    weather_note = "Moved indoors due to expected rain"
                    backup_item = ItineraryItem(
                        id=uuid.uuid4().hex[:8],
                        day=day_num + 1,
                        title=act.get("name", "Activity"),
                        category="activity",
                        description=act.get("description", ""),
                        cost=act.get("price", 0),
                        reasoning="Original plan if weather improves",
                    )
                    chosen = alt

            items.append(ItineraryItem(
                id=uuid.uuid4().hex[:8],
                day=day_num + 1,
                start_time=start_times[i],
                end_time=end_times[i],
                title=chosen.get("name", "Sightseeing"),
                category="activity",
                description=chosen.get("description", ""),
                cost=chosen.get("price", 0) * cost_multiplier,
                location=city_name or chosen.get("address", ""),
                latitude=chosen.get("latitude", 0.0),
                longitude=chosen.get("longitude", 0.0),
                booking_url=chosen.get("booking_url", ""),
                reasoning=f"Top-rated {chosen.get('category', 'attraction')} in {loc_label}",
                weather_note=weather_note,
                backup=backup_item,
            ))

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
