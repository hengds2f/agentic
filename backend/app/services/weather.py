"""Weather forecast service using Open-Meteo API. Free, no API key needed."""
from __future__ import annotations

from datetime import date as dt_date, timedelta

import httpx

from app.core.logging import get_logger
from app.models.schemas import WeatherForecast
from app.services.geocoding import geocode

logger = get_logger(__name__)

OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"

# WMO weather code → human-readable condition
_WMO_CONDITIONS: dict[int, str] = {
    0: "sunny", 1: "partly_cloudy", 2: "partly_cloudy", 3: "cloudy",
    45: "foggy", 48: "foggy",
    51: "drizzle", 53: "drizzle", 55: "drizzle",
    56: "freezing_drizzle", 57: "freezing_drizzle",
    61: "rainy", 63: "rainy", 65: "rainy",
    66: "freezing_rain", 67: "freezing_rain",
    71: "snowy", 73: "snowy", 75: "snowy", 77: "snowy",
    80: "rainy", 81: "rainy", 82: "rainy",
    85: "snowy", 86: "snowy",
    95: "stormy", 96: "stormy", 99: "stormy",
}


def _recommend(condition: str, high_c: float, precip_pct: int) -> str:
    if condition in ("stormy",):
        return "Stay indoors. Severe weather expected."
    if condition in ("rainy", "freezing_rain"):
        return "Bring an umbrella. Consider indoor activities."
    if condition in ("snowy", "freezing_drizzle"):
        return "Cold and snowy — dress warmly, enjoy winter activities."
    if condition == "foggy":
        return "Reduced visibility. Stick to indoor plans or short walks."
    if condition == "drizzle":
        return "Light drizzle possible. A light raincoat should suffice."
    if high_c > 33:
        return "Very hot — stay hydrated, seek shade during midday."
    if high_c > 28:
        return "Warm day. Sunscreen and a hat recommended."
    if high_c < 5:
        return "Very cold — layer up and keep warm."
    if precip_pct > 50:
        return "Rain possible later. Have a backup indoor plan."
    return "Great day for outdoor activities!"


class WeatherService:
    async def get_forecast(
        self,
        destination: str,
        start_date: str,
        end_date: str,
    ) -> list[WeatherForecast]:
        geo = await geocode(destination)
        if not geo:
            logger.warning("weather.no_geocode", destination=destination)
            return []

        try:
            start = dt_date.fromisoformat(str(start_date))
            end = dt_date.fromisoformat(str(end_date))
        except (ValueError, TypeError):
            start = dt_date.today()
            end = start + timedelta(days=3)

        # Open-Meteo only forecasts up to 16 days ahead; clamp if needed
        today = dt_date.today()
        max_end = today + timedelta(days=15)
        api_start = max(start, today)
        api_end = min(end, max_end)

        if api_start > api_end:
            # Dates are too far in the future for forecast — use climate averages
            return self._climate_estimate(start, end, geo.lat, geo.lng)

        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(OPEN_METEO_URL, params={
                    "latitude": geo.lat,
                    "longitude": geo.lng,
                    "daily": "temperature_2m_max,temperature_2m_min,precipitation_probability_max,weather_code,uv_index_max,wind_speed_10m_max",
                    "timezone": "auto",
                    "start_date": str(api_start),
                    "end_date": str(api_end),
                })
                resp.raise_for_status()
                data = resp.json()
        except Exception as exc:
            logger.error("weather.api_error", error=str(exc))
            return self._climate_estimate(start, end, geo.lat, geo.lng)

        daily = data.get("daily", {})
        dates = daily.get("time", [])
        highs = daily.get("temperature_2m_max", [])
        lows = daily.get("temperature_2m_min", [])
        precip = daily.get("precipitation_probability_max", [])
        codes = daily.get("weather_code", [])
        uv = daily.get("uv_index_max", [])
        wind = daily.get("wind_speed_10m_max", [])

        forecasts: list[WeatherForecast] = []
        for i, d in enumerate(dates):
            high_c = highs[i] if i < len(highs) else 20.0
            low_c = lows[i] if i < len(lows) else 12.0
            prec = int(precip[i]) if i < len(precip) and precip[i] is not None else 0
            code = codes[i] if i < len(codes) else 0
            condition = _WMO_CONDITIONS.get(code, "partly_cloudy")

            forecasts.append(WeatherForecast(
                date=dt_date.fromisoformat(d),
                high_temp_c=round(high_c, 1),
                low_temp_c=round(low_c, 1),
                condition=condition,
                precipitation_pct=prec,
                uv_index=int(uv[i]) if i < len(uv) and uv[i] is not None else 5,
                wind_kph=round(wind[i], 1) if i < len(wind) and wind[i] is not None else 10.0,
                recommendation=_recommend(condition, high_c, prec),
            ))

        return forecasts

    def _climate_estimate(
        self, start: dt_date, end: dt_date, lat: float, lng: float
    ) -> list[WeatherForecast]:
        """Rough climate-based estimate for dates too far in the future."""
        import math, random
        num_days = max((end - start).days, 1)
        month = start.month

        # Rough temperature based on latitude and month
        # Northern hemisphere summer (Jun-Aug) is warmer, southern is opposite
        base_temp = 25 - abs(lat) * 0.4
        seasonal = 8 * math.cos(math.radians((month - 7) * 30)) * (1 if lat >= 0 else -1)
        avg_high = base_temp + seasonal

        forecasts = []
        for i in range(num_days):
            current = start + timedelta(days=i)
            high = round(avg_high + random.uniform(-3, 3), 1)
            low = round(high - random.uniform(5, 10), 1)
            precip = random.randint(10, 40)
            condition = "partly_cloudy" if precip < 30 else "cloudy"

            forecasts.append(WeatherForecast(
                date=current,
                high_temp_c=high,
                low_temp_c=low,
                condition=condition,
                precipitation_pct=precip,
                uv_index=random.randint(3, 8),
                wind_kph=round(random.uniform(5, 20), 1),
                recommendation=_recommend(condition, high, precip) + " (Climate estimate — check closer to trip.)",
            ))
        return forecasts
