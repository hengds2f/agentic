"""Calendar Agent — builds day-by-day itinerary from gathered data."""
from __future__ import annotations

import uuid
from datetime import date as dt_date, datetime, time as dt_time, timedelta
from math import atan2, cos, radians, sin, sqrt
from typing import Any

from app.agents.base import BaseAgent
from app.models.schemas import AgentRole, DayPlan, Itinerary, ItineraryItem, WeatherForecast


def _haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Distance in km between two lat/lon points."""
    R = 6371.0
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
    return R * 2 * atan2(sqrt(a), sqrt(1 - a))


def _cluster_activities(activities: list[dict], num_groups: int) -> list[list[dict]]:
    """Simple geographic clustering: sort by distance from centroid, split into groups."""
    if not activities:
        return [[] for _ in range(num_groups)]

    # Calculate centroid
    avg_lat = sum(a.get("latitude", 0) for a in activities) / len(activities)
    avg_lon = sum(a.get("longitude", 0) for a in activities) / len(activities)

    # Sort by angle from centroid to group nearby POIs together
    from math import atan2 as _atan2
    for a in activities:
        a["_angle"] = _atan2(a.get("latitude", 0) - avg_lat, a.get("longitude", 0) - avg_lon)
    sorted_acts = sorted(activities, key=lambda a: a["_angle"])

    # Split into roughly equal groups
    groups: list[list[dict]] = [[] for _ in range(num_groups)]
    for i, act in enumerate(sorted_acts):
        groups[i % num_groups].append(act)
    return groups


def _day_theme(activities: list[dict]) -> str:
    """Generate a thematic day title from the activities planned."""
    if not activities:
        return "Free Exploration"
    categories = [a.get("category", "") for a in activities]
    names = [a.get("name", "") for a in activities]

    # Use primary activity name for the title
    primary = names[0] if names else "Exploration"
    if len(names) > 1:
        return f"{primary} & Nearby Sights"

    cat_labels = {
        "museum": "Museum & Culture",
        "historic": "Historic Sites",
        "nature": "Nature & Parks",
        "sightseeing": "Sightseeing",
        "entertainment": "Entertainment",
        "cultural": "Cultural Discovery",
        "sports": "Sports & Recreation",
        "shopping": "Shopping & Markets",
    }
    main_cat = max(set(categories), key=categories.count) if categories else ""
    return cat_labels.get(main_cat, primary)


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

        # Select best-rated hotel (highest rating, not cheapest)
        best_hotel = max(hotels, key=lambda h: h.get("rating", 0)) if hotels else None

        # Build forecast lookup
        forecast_map: dict[str, dict] = {}
        for f in forecasts:
            forecast_map[str(f.get("date", ""))] = f

        # ── Determine flight arrival time for realistic Day 1 scheduling ──
        best_flight = min(flights, key=lambda f: f["price"]) if flights else None
        # Parse the arrival time to know when the traveler lands
        arrival_hour = 12  # default noon if no flight info
        arrival_minute = 0
        if best_flight:
            arr_time_str = best_flight.get("arrival_time", "")
            try:
                if isinstance(arr_time_str, str) and "T" in arr_time_str:
                    arr_dt = datetime.fromisoformat(arr_time_str)
                    arrival_hour = arr_dt.hour
                    arrival_minute = arr_dt.minute
                elif hasattr(arr_time_str, "hour"):
                    arrival_hour = arr_time_str.hour
                    arrival_minute = arr_time_str.minute
            except (ValueError, TypeError):
                pass

        # Add ~1hr for immigration/baggage, round up
        post_arrival_hour = arrival_hour + 1
        post_arrival_minute = arrival_minute
        if post_arrival_hour >= 24:
            post_arrival_hour = 23
            post_arrival_minute = 0

        # ── Cluster activities geographically into day groups ──
        indoor_acts = [a for a in activities if not a.get("weather_sensitive", False)]
        acts_per_day = 3
        num_groups = max(num_days, 1)
        day_groups = _cluster_activities(list(activities), num_groups)

        for i, grp in enumerate(day_groups):
            while len(grp) < acts_per_day and any(len(g) > acts_per_day for g in day_groups):
                donor = max(day_groups, key=len)
                if len(donor) <= acts_per_day:
                    break
                grp.append(donor.pop())
            while len(grp) < acts_per_day and activities:
                grp.append(activities[len(grp) % len(activities)])

        days: list[DayPlan] = []
        restaurant_idx = 0
        total_cost = 0.0

        for day_num in range(num_days):
            current_date = start_date + timedelta(days=day_num)
            weather = forecast_map.get(str(current_date))
            weather_obj = WeatherForecast(**weather) if weather else None

            items: list[ItineraryItem] = []
            day_cost = 0.0
            is_rainy = weather and weather.get("condition") in ("rainy", "stormy")
            is_first_day = day_num == 0
            is_last_day = day_num == num_days - 1

            # ── Day 1: Arrival flights ──
            if is_first_day and best_flight:
                flight_cost = best_flight.get("price", 0) * cost_multiplier
                flight_legs = best_flight.get("legs", [])

                if flight_legs:
                    # Show each leg as a separate itinerary item
                    for leg_idx, leg in enumerate(flight_legs):
                        leg_dep = leg.get("departure_time", "")
                        leg_arr = leg.get("arrival_time", "")
                        leg_airline = leg.get("airline", best_flight.get("airline", "Airline"))

                        # Parse leg times
                        try:
                            if isinstance(leg_dep, str) and "T" in leg_dep:
                                dep_dt = datetime.fromisoformat(leg_dep)
                            else:
                                dep_dt = datetime.combine(current_date, dt_time(8, 0))
                            if isinstance(leg_arr, str) and "T" in leg_arr:
                                arr_dt = datetime.fromisoformat(leg_arr)
                            else:
                                arr_dt = dep_dt + timedelta(hours=3)
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
                            cost=flight_cost if is_last_leg else 0,
                            booking_url=best_flight.get("booking_url", ""),
                            reasoning=(
                                f"{'Direct flight' if len(flight_legs) == 1 else f'{len(flight_legs)}-leg connection'} "
                                f"× {total_pax} travelers"
                            ) if is_last_leg else f"Connection via {leg_to}",
                        ))
                else:
                    # Fallback: single flight item
                    items.append(ItineraryItem(
                        id=uuid.uuid4().hex[:8],
                        day=day_num + 1,
                        start_time=dt_time(8, 0),
                        end_time=dt_time(arrival_hour, arrival_minute),
                        title=f"✈️ {best_flight.get('airline', 'Airline')}: {best_flight.get('departure_airport', '')} → {best_flight.get('arrival_airport', '')}",
                        category="flight",
                        description=f"{best_flight.get('stops', 0)} stop(s) · {best_flight.get('duration_minutes', 0) // 60}h ({total_pax} pax)",
                        cost=flight_cost,
                        booking_url=best_flight.get("booking_url", ""),
                        reasoning=f"Best value flight × {total_pax} travelers",
                    ))
                day_cost += flight_cost

            # ── Hotel — show for every day ──
            if best_hotel:
                hotel_cost_per_night = best_hotel.get("price_per_night", 0)
                if is_first_day:
                    check_in_time = dt_time(max(post_arrival_hour, 14), 0)
                    items.append(ItineraryItem(
                        id=uuid.uuid4().hex[:8],
                        day=day_num + 1,
                        start_time=check_in_time,
                        end_time=dt_time(min(check_in_time.hour + 1, 23), 0),
                        title=f"🏨 Check in: {best_hotel.get('name', 'Hotel')}",
                        category="hotel",
                        description=f"⭐ {best_hotel.get('rating', 4.0)} · {', '.join(best_hotel.get('amenities', [])[:3])}",
                        cost=hotel_cost_per_night,
                        location=best_hotel.get("address", ""),
                        latitude=best_hotel.get("latitude", 0.0),
                        longitude=best_hotel.get("longitude", 0.0),
                        booking_url=best_hotel.get("booking_url", ""),
                        reasoning=f"Best rated hotel — ⭐ {best_hotel.get('rating', 4.0)} on Google Reviews",
                    ))
                elif is_last_day:
                    items.append(ItineraryItem(
                        id=uuid.uuid4().hex[:8],
                        day=day_num + 1,
                        start_time=dt_time(11, 0),
                        end_time=dt_time(12, 0),
                        title=f"🏨 Check out: {best_hotel.get('name', 'Hotel')}",
                        category="hotel",
                        description=f"⭐ {best_hotel.get('rating', 4.0)} · Check-out by noon",
                        cost=hotel_cost_per_night,
                        location=best_hotel.get("address", ""),
                        latitude=best_hotel.get("latitude", 0.0),
                        longitude=best_hotel.get("longitude", 0.0),
                        booking_url=best_hotel.get("booking_url", ""),
                        reasoning="Check out and store luggage if needed",
                    ))
                else:
                    items.append(ItineraryItem(
                        id=uuid.uuid4().hex[:8],
                        day=day_num + 1,
                        start_time=dt_time(7, 0),
                        end_time=dt_time(8, 0),
                        title=f"🏨 {best_hotel.get('name', 'Hotel')}",
                        category="hotel",
                        description=f"⭐ {best_hotel.get('rating', 4.0)} · Night {day_num + 1} of {num_days}",
                        cost=hotel_cost_per_night,
                        location=best_hotel.get("address", ""),
                        latitude=best_hotel.get("latitude", 0.0),
                        longitude=best_hotel.get("longitude", 0.0),
                        booking_url=best_hotel.get("booking_url", ""),
                        reasoning=f"Best rated hotel — ⭐ {best_hotel.get('rating', 4.0)} on Google Reviews",
                    ))
                day_cost += hotel_cost_per_night

            # ── Sightseeing activities (with realistic times based on arrival) ──
            if is_first_day and num_days > 1:
                # After arrival + hotel check-in: 1 nearby activity
                first_activity_hour = max(post_arrival_hour + 2, 15)  # at least 3pm
                if first_activity_hour < 20:
                    day_acts = day_groups[0][:1] if day_groups and day_groups[0] else []
                    self._add_activities(items, day_acts, day_num, is_rainy, indoor_acts, trip,
                                         start_times=[dt_time(first_activity_hour, 0)],
                                         end_times=[dt_time(min(first_activity_hour + 2, 21), 0)],
                                         cost_multiplier=cost_multiplier)
                    day_cost += sum(a.get("price", 0) for a in day_acts) * cost_multiplier
                else:
                    day_acts = []
            elif is_last_day and num_days > 1:
                day_acts = day_groups[day_num][:1] if day_num < len(day_groups) and day_groups[day_num] else []
                self._add_activities(items, day_acts, day_num, is_rainy, indoor_acts, trip,
                                     start_times=[dt_time(9, 0)],
                                     end_times=[dt_time(11, 0)],
                                     cost_multiplier=cost_multiplier)
                day_cost += sum(a.get("price", 0) for a in day_acts) * cost_multiplier
            else:
                # Full sightseeing day: 3 activities
                group_idx = day_num
                day_acts = day_groups[group_idx][:acts_per_day] if group_idx < len(day_groups) else []
                self._add_activities(items, day_acts, day_num, is_rainy, indoor_acts, trip,
                                     start_times=[dt_time(9, 30), dt_time(14, 0), dt_time(16, 0)],
                                     end_times=[dt_time(11, 30), dt_time(15, 30), dt_time(17, 30)],
                                     cost_multiplier=cost_multiplier)
                day_cost += sum(a.get("price", 0) for a in day_acts) * cost_multiplier

            # ── Meals — every day gets lunch and dinner ──
            if restaurants:
                # Lunch
                rest = restaurants[restaurant_idx % len(restaurants)]
                if is_first_day:
                    lunch_hour = max(post_arrival_hour + 1, 13)
                    if lunch_hour > 15:
                        lunch_hour = 13  # Too late for lunch after arrival, skip timing constraint
                else:
                    lunch_hour = 12
                lunch_time = dt_time(min(lunch_hour, 15), 0)
                lunch_cost = 25.0 * cost_multiplier
                items.append(ItineraryItem(
                    id=uuid.uuid4().hex[:8],
                    day=day_num + 1,
                    start_time=lunch_time,
                    end_time=dt_time(lunch_time.hour + 1, 0),
                    title=f"Lunch: {rest.get('name', 'Restaurant')}",
                    category="food",
                    description=f"{rest.get('cuisine', '')} cuisine — ⭐ {rest.get('rating', 4.0)}",
                    cost=lunch_cost,
                    location=rest.get("address", ""),
                    latitude=rest.get("latitude", 0.0),
                    longitude=rest.get("longitude", 0.0),
                    booking_url=rest.get("booking_url", ""),
                    reasoning=f"Highly rated {rest.get('cuisine', 'local')} restaurant — see Google reviews",
                ))
                day_cost += lunch_cost
                restaurant_idx += 1

                # Dinner
                rest = restaurants[restaurant_idx % len(restaurants)]
                dinner_cost = 40.0 * cost_multiplier
                items.append(ItineraryItem(
                    id=uuid.uuid4().hex[:8],
                    day=day_num + 1,
                    start_time=dt_time(19, 0),
                    end_time=dt_time(20, 30),
                    title=f"Dinner: {rest.get('name', 'Restaurant')}",
                    category="food",
                    description=f"{rest.get('cuisine', '')} cuisine — ⭐ {rest.get('rating', 4.0)}",
                    cost=dinner_cost,
                    location=rest.get("address", ""),
                    latitude=rest.get("latitude", 0.0),
                    longitude=rest.get("longitude", 0.0),
                    booking_url=rest.get("booking_url", ""),
                    reasoning="Top-rated dinner spot — check Google Maps for reviews and photos",
                ))
                day_cost += dinner_cost
                restaurant_idx += 1

            # ── Last day: departure flight ──
            if is_last_day and best_flight:
                # Return flight in the evening
                items.append(ItineraryItem(
                    id=uuid.uuid4().hex[:8],
                    day=day_num + 1,
                    start_time=dt_time(16, 0),
                    end_time=dt_time(17, 0),
                    title="🚕 Transfer to airport",
                    category="transport",
                    description="Allow 1-2 hours before departure",
                    cost=0,
                    reasoning="Buffer time for airport transfer and check-in",
                ))
                items.append(ItineraryItem(
                    id=uuid.uuid4().hex[:8],
                    day=day_num + 1,
                    start_time=dt_time(18, 0),
                    end_time=dt_time(22, 0),
                    title=f"✈️ Return flight: {best_flight.get('arrival_airport', '')} → {best_flight.get('departure_airport', '')}",
                    category="flight",
                    description="Return journey",
                    cost=0,
                    booking_url=best_flight.get("booking_url", ""),
                    reasoning="Return flight included in outbound booking",
                ))

            # Sort items by start_time for clean chronological order
            items.sort(key=lambda it: (it.start_time or dt_time(0, 0)))

            # ── Day title ──
            if is_first_day:
                day_title = f"Arrival in {destination}"
            elif is_last_day and num_days > 1:
                day_title = f"Departure from {destination}"
            else:
                planned_acts = day_groups[day_num] if day_num < len(day_groups) else []
                day_title = _day_theme(planned_acts[:acts_per_day])

            total_cost += day_cost
            days.append(DayPlan(
                day=day_num + 1,
                date=current_date,
                title=f"Day {day_num + 1} — {day_title}",
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
            "summary": f"Built {num_days}-day itinerary with {sum(len(g) for g in day_groups)} sightseeing locations, ${total_cost:,.0f} total",
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
    ) -> None:
        """Add activity items to the day, handling weather substitution."""
        used_indoor: set[str] = set()
        for i, act in enumerate(day_acts):
            if i >= len(start_times):
                break
            weather_note = ""
            backup_item = None
            chosen = act

            if is_rainy and act.get("weather_sensitive"):
                # Find an indoor alternative not already used
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
                location=chosen.get("address", ""),
                latitude=chosen.get("latitude", 0.0),
                longitude=chosen.get("longitude", 0.0),
                booking_url=chosen.get("booking_url", ""),
                reasoning=f"Top-rated {chosen.get('category', 'attraction')} in {trip.get('destination', 'the area')}",
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
