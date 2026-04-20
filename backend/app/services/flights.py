"""Flight search with real airport data, distance-based pricing, and booking links."""
from __future__ import annotations

import math
import random
from datetime import datetime, timedelta

from app.core.logging import get_logger
from app.models.schemas import FlightLeg, FlightOption
from app.services.geocoding import geocode

logger = get_logger(__name__)

# Major airports worldwide: (IATA, city, country, lat, lng)
_AIRPORTS: list[tuple[str, str, str, float, float]] = [
    # North America
    ("JFK", "New York", "US", 40.6413, -73.7781),
    ("EWR", "Newark", "US", 40.6895, -74.1745),
    ("LAX", "Los Angeles", "US", 33.9425, -118.4081),
    ("SFO", "San Francisco", "US", 37.6213, -122.3790),
    ("ORD", "Chicago", "US", 41.9742, -87.9073),
    ("ATL", "Atlanta", "US", 33.6407, -84.4277),
    ("MIA", "Miami", "US", 25.7959, -80.2870),
    ("BOS", "Boston", "US", 42.3656, -71.0096),
    ("DFW", "Dallas", "US", 32.8998, -97.0403),
    ("SEA", "Seattle", "US", 47.4502, -122.3088),
    ("DEN", "Denver", "US", 39.8561, -104.6737),
    ("IAD", "Washington", "US", 38.9531, -77.4565),
    ("YYZ", "Toronto", "CA", 43.6777, -79.6248),
    ("YVR", "Vancouver", "CA", 49.1967, -123.1815),
    ("MEX", "Mexico City", "MX", 19.4363, -99.0721),
    ("GRU", "São Paulo", "BR", -23.4356, -46.4731),
    ("EZE", "Buenos Aires", "AR", -34.8222, -58.5358),
    ("BOG", "Bogotá", "CO", 4.7016, -74.1469),
    ("SCL", "Santiago", "CL", -33.3930, -70.7858),
    ("LIM", "Lima", "PE", -12.0219, -77.1143),
    # Europe
    ("LHR", "London", "GB", 51.4700, -0.4543),
    ("CDG", "Paris", "FR", 49.0097, 2.5479),
    ("AMS", "Amsterdam", "NL", 52.3105, 4.7683),
    ("FRA", "Frankfurt", "DE", 50.0379, 8.5622),
    ("MAD", "Madrid", "ES", 40.4983, -3.5676),
    ("BCN", "Barcelona", "ES", 41.2971, 2.0785),
    ("FCO", "Rome", "IT", 41.8003, 12.2389),
    ("MXP", "Milan", "IT", 45.6306, 8.7281),
    ("MUC", "Munich", "DE", 48.3537, 11.7750),
    ("ZRH", "Zurich", "CH", 47.4647, 8.5492),
    ("LIS", "Lisbon", "PT", 38.7742, -9.1342),
    ("CPH", "Copenhagen", "DK", 55.6180, 12.6508),
    ("DUB", "Dublin", "IE", 53.4264, -6.2499),
    ("IST", "Istanbul", "TR", 41.2753, 28.7519),
    ("ATH", "Athens", "GR", 37.9364, 23.9445),
    ("VIE", "Vienna", "AT", 48.1103, 16.5697),
    ("PRG", "Prague", "CZ", 50.1008, 14.2600),
    ("WAW", "Warsaw", "PL", 52.1657, 20.9671),
    ("OSL", "Oslo", "NO", 60.1939, 11.1004),
    ("ARN", "Stockholm", "SE", 59.6519, 17.9186),
    ("HEL", "Helsinki", "FI", 60.3172, 24.9633),
    # Asia
    ("NRT", "Tokyo", "JP", 35.7647, 140.3864),
    ("HND", "Tokyo Haneda", "JP", 35.5494, 139.7798),
    ("ICN", "Seoul", "KR", 37.4602, 126.4407),
    ("PEK", "Beijing", "CN", 40.0799, 116.6031),
    ("PVG", "Shanghai", "CN", 31.1443, 121.8083),
    ("HKG", "Hong Kong", "HK", 22.3080, 113.9185),
    ("SIN", "Singapore", "SG", 1.3644, 103.9915),
    ("BKK", "Bangkok", "TH", 13.6900, 100.7501),
    ("KUL", "Kuala Lumpur", "MY", 2.7456, 101.7099),
    ("DEL", "New Delhi", "IN", 28.5562, 77.1000),
    ("BOM", "Mumbai", "IN", 19.0896, 72.8656),
    ("TPE", "Taipei", "TW", 25.0797, 121.2342),
    ("MNL", "Manila", "PH", 14.5086, 121.0198),
    ("SGN", "Ho Chi Minh City", "VN", 10.8188, 106.6520),
    ("CGK", "Jakarta", "ID", -6.1256, 106.6559),
    # Middle East
    ("DXB", "Dubai", "AE", 25.2532, 55.3657),
    ("DOH", "Doha", "QA", 25.2731, 51.6081),
    ("AUH", "Abu Dhabi", "AE", 24.4330, 54.6511),
    ("TLV", "Tel Aviv", "IL", 32.0055, 34.8854),
    # Oceania
    ("SYD", "Sydney", "AU", -33.9461, 151.1772),
    ("MEL", "Melbourne", "AU", -37.6690, 144.8410),
    ("AKL", "Auckland", "NZ", -37.0082, 174.7850),
    ("DPS", "Bali", "ID", -8.7482, 115.1672),
    # Africa
    ("JNB", "Johannesburg", "ZA", -26.1392, 28.2460),
    ("CAI", "Cairo", "EG", 30.1219, 31.4056),
    ("NBO", "Nairobi", "KE", -1.3192, 36.9278),
    ("CMN", "Casablanca", "MA", 33.3675, -7.5898),
    ("CPT", "Cape Town", "ZA", -33.9648, 18.6017),
    # Islands
    ("MLE", "Maldives", "MV", 4.1918, 73.5290),
    ("HNL", "Honolulu", "US", 21.3187, -157.9224),
    ("KEF", "Reykjavik", "IS", 63.9850, -22.6056),
    ("MRU", "Mauritius", "MU", -20.4302, 57.6836),
]

_AIRLINES = [
    "American Airlines", "United Airlines", "Delta Air Lines", "Southwest",
    "British Airways", "Lufthansa", "Air France", "KLM", "Ryanair", "easyJet",
    "Emirates", "Qatar Airways", "Etihad Airways", "Turkish Airlines",
    "Singapore Airlines", "Cathay Pacific", "ANA", "Japan Airlines",
    "Korean Air", "Thai Airways", "Air Canada", "LATAM Airlines",
    "Qantas", "Virgin Atlantic", "Iberia", "SAS", "Swiss", "Austrian",
    "TAP Portugal", "Aer Lingus", "Norwegian", "Air New Zealand",
]


def _haversine(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    R = 6371
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlng / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _find_nearest_airport(lat: float, lng: float) -> tuple[str, str, float, float]:
    """Find nearest airport to given coordinates. Returns (code, city, lat, lng)."""
    best = _AIRPORTS[0]
    best_dist = float("inf")
    for code, city, country, alat, alng in _AIRPORTS:
        d = _haversine(lat, lng, alat, alng)
        if d < best_dist:
            best_dist = d
            best = (code, city, country, alat, alng)
    return best[0], best[1], best[3], best[4]


def _find_airport_by_city(city_name: str) -> tuple[str, str, float, float] | None:
    """Find airport by city name (case-insensitive partial match)."""
    city_lower = city_name.lower().strip()
    for code, city, country, lat, lng in _AIRPORTS:
        if city_lower in city.lower() or city.lower() in city_lower or city_lower == code.lower():
            return code, city, lat, lng
    return None


def _estimate_price(distance_km: float, is_direct: bool = True) -> float:
    """Realistic economy price estimation based on route distance."""
    if distance_km < 500:
        rate = 0.28
    elif distance_km < 1500:
        rate = 0.18
    elif distance_km < 5000:
        rate = 0.11
    elif distance_km < 10000:
        rate = 0.075
    else:
        rate = 0.055

    base = distance_km * rate
    base = max(base, 45)

    if not is_direct:
        base *= 0.72

    variation = random.uniform(0.85, 1.20)
    return round(base * variation, 2)


def _pick_airlines(origin_code: str, dest_code: str, n: int = 3) -> list[str]:
    """Pick plausible airlines for a route."""
    random.seed(hash(f"{origin_code}-{dest_code}"))
    picked = random.sample(_AIRLINES, min(n, len(_AIRLINES)))
    random.seed()  # re-seed
    return picked


# Major hub airports for connection routing
_HUB_AIRPORTS = [
    ("DXB", 25.2532, 55.3657), ("LHR", 51.4700, -0.4543),
    ("CDG", 49.0097, 2.5479), ("FRA", 50.0379, 8.5622),
    ("IST", 41.2753, 28.7519), ("SIN", 1.3644, 103.9915),
    ("DOH", 25.2731, 51.6081), ("AMS", 52.3105, 4.7683),
    ("ICN", 37.4602, 126.4407), ("ATL", 33.6407, -84.4277),
    ("ORD", 41.9742, -87.9073), ("HKG", 22.3080, 113.9185),
]


def _find_stopover_hubs(
    orig_lat: float, orig_lng: float,
    dest_lat: float, dest_lng: float,
    orig_code: str, dest_code: str,
    num_stops: int,
) -> list[tuple[str, float, float]]:
    """Find plausible stopover hub airports between origin and dest."""
    direct_dist = _haversine(orig_lat, orig_lng, dest_lat, dest_lng)
    candidates = []
    for code, lat, lng in _HUB_AIRPORTS:
        if code == orig_code or code == dest_code:
            continue
        d1 = _haversine(orig_lat, orig_lng, lat, lng)
        d2 = _haversine(lat, lng, dest_lat, dest_lng)
        detour = (d1 + d2) / max(direct_dist, 1)
        # Good stopovers add < 60% detour and are between origin/dest
        if detour < 1.6 and d1 > 500 and d2 > 500:
            candidates.append((code, lat, lng, detour))
    candidates.sort(key=lambda x: x[3])
    result = [(c[0], c[1], c[2]) for c in candidates[:num_stops]]
    # If we can't find good hubs, pick the closest major hubs
    if len(result) < num_stops:
        mid_lat = (orig_lat + dest_lat) / 2
        mid_lng = (orig_lng + dest_lng) / 2
        fallbacks = sorted(
            [(c, lat, lng) for c, lat, lng in _HUB_AIRPORTS
             if c != orig_code and c != dest_code and c not in [r[0] for r in result]],
            key=lambda x: _haversine(mid_lat, mid_lng, x[1], x[2]),
        )
        result.extend(fallbacks[:num_stops - len(result)])
    return result[:num_stops]


def _build_legs(
    airline: str,
    orig_code: str, orig_lat: float, orig_lng: float,
    dest_code: str, dest_lat: float, dest_lng: float,
    dep_time: datetime,
    hubs: list[tuple[str, float, float]],
) -> tuple[list[FlightLeg], datetime]:
    """Build flight leg segments through hub airports. Returns (legs, final_arrival)."""
    legs: list[FlightLeg] = []
    waypoints = [(orig_code, orig_lat, orig_lng)] + [(h[0], h[1], h[2]) for h in hubs] + [(dest_code, dest_lat, dest_lng)]

    current_time = dep_time
    for i in range(len(waypoints) - 1):
        from_code, from_lat, from_lng = waypoints[i]
        to_code, to_lat, to_lng = waypoints[i + 1]
        seg_dist = _haversine(from_lat, from_lng, to_lat, to_lng)
        seg_hours = seg_dist / 800
        seg_minutes = int(seg_hours * 60)
        arr_time = current_time + timedelta(hours=seg_hours)

        legs.append(FlightLeg(
            departure_airport=from_code,
            arrival_airport=to_code,
            departure_time=current_time,
            arrival_time=arr_time,
            airline=airline,
            duration_minutes=seg_minutes,
        ))
        # Add layover time (1-3 hours)
        layover = timedelta(hours=random.uniform(1.0, 3.0))
        current_time = arr_time + layover

    final_arrival = legs[-1].arrival_time if legs else dep_time
    return legs, final_arrival


class FlightService:
    async def search(
        self,
        origin: str,
        destination: str,
        departure_date: str,
        return_date: str = "",
    ) -> list[FlightOption]:
        # Resolve origin airport
        orig_airport = _find_airport_by_city(origin)
        if not orig_airport:
            geo = await geocode(origin)
            if geo:
                code, city, lat, lng = _find_nearest_airport(geo.lat, geo.lng)
                orig_airport = (code, city, lat, lng)
            else:
                orig_airport = ("JFK", "New York", 40.6413, -73.7781)

        # Resolve destination airport
        dest_airport = _find_airport_by_city(destination)
        if not dest_airport:
            geo = await geocode(destination)
            if geo:
                code, city, lat, lng = _find_nearest_airport(geo.lat, geo.lng)
                dest_airport = (code, city, lat, lng)
            else:
                dest_airport = ("LHR", "London", 51.4700, -0.4543)

        orig_code, orig_city, orig_lat, orig_lng = orig_airport
        dest_code, dest_city, dest_lat, dest_lng = dest_airport

        distance = _haversine(orig_lat, orig_lng, dest_lat, dest_lng)
        flight_hours = distance / 800  # ~800 km/h average speed
        airlines = _pick_airlines(orig_code, dest_code, 3)

        dep = departure_date or "2026-07-01"
        try:
            dep_date = datetime.fromisoformat(str(dep))
        except ValueError:
            dep_date = datetime(2026, 7, 1)

        flights: list[FlightOption] = []

        # Determine stop counts based on distance
        # Short (<2000km): all direct
        # Medium (2000-8000km): 2 direct + 1 with 1 stop
        # Long (8000-14000km): 1 direct + 1 with 1 stop + 1 with 2 stops
        # Very long (>14000km): 1 direct + 2 connecting
        if distance < 2000:
            stop_configs = [0, 0, 0]
        elif distance < 8000:
            stop_configs = [0, 0, 1]
        elif distance < 14000:
            stop_configs = [0, 1, 2]
        else:
            stop_configs = [0, 1, 2]

        for i, airline in enumerate(airlines):
            num_stops = stop_configs[i] if i < len(stop_configs) else 0
            is_direct = num_stops == 0
            price = _estimate_price(distance, is_direct)

            dep_hour = [8, 12, 18][i % 3]
            dep_time = dep_date.replace(hour=dep_hour, minute=0)

            # Build Google Flights booking URL
            booking_url = (
                f"https://www.google.com/travel/flights?q=Flights+from+{orig_city.replace(' ', '+')}+"
                f"to+{dest_city.replace(' ', '+')}+on+{dep}"
            )

            if is_direct:
                hours = flight_hours
                arr_time = dep_time + timedelta(hours=hours)
                duration = int(hours * 60)
                legs = [FlightLeg(
                    departure_airport=orig_code,
                    arrival_airport=dest_code,
                    departure_time=dep_time,
                    arrival_time=arr_time,
                    airline=airline,
                    duration_minutes=duration,
                )]
            else:
                hubs = _find_stopover_hubs(
                    orig_lat, orig_lng, dest_lat, dest_lng,
                    orig_code, dest_code, num_stops,
                )
                legs, arr_time = _build_legs(
                    airline, orig_code, orig_lat, orig_lng,
                    dest_code, dest_lat, dest_lng, dep_time, hubs,
                )
                duration = int((arr_time - dep_time).total_seconds() / 60)

            flights.append(FlightOption(
                id=f"FL-{orig_code}{dest_code}-{i+1}",
                airline=airline,
                departure_airport=orig_code,
                arrival_airport=dest_code,
                departure_time=dep_time,
                arrival_time=arr_time,
                price=price,
                stops=num_stops,
                duration_minutes=duration,
                booking_url=booking_url,
                legs=legs,
            ))

        flights.sort(key=lambda f: f.price)
        logger.info("flights.generated", origin=orig_code, dest=dest_code, distance_km=round(distance), count=len(flights))
        return flights
