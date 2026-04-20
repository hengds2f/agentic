from __future__ import annotations

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "HolidayPilot"
    debug: bool = False
    database_url: str = "sqlite+aiosqlite:///./holidaypilot.db"

    openai_api_key: str = ""
    openai_model: str = "gpt-4o"

    # External API keys (empty = use mock)
    flights_api_key: str = ""
    hotels_api_key: str = ""
    maps_api_key: str = ""
    weather_api_key: str = ""
    events_api_key: str = ""

    cors_origins: list[str] = ["http://localhost:5173", "http://localhost:7860", "https://*.hf.space"]

    model_config = {"env_prefix": "HP_", "env_file": ".env"}


settings = Settings()
