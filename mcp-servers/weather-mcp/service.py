"""Business logic for the weather service, shared by REST (app.py) and MCP
(mcp_server.py). Pure functions over the mock data in data.py: no state, no
network, no randomness.
"""

from __future__ import annotations

from data import CITIES, FORECAST_PATTERN, MAX_FORECAST_DAYS


class ServiceError(Exception):
    code = "SERVICE_ERROR"
    status = 400


class UnknownCity(ServiceError):
    code, status = "UNKNOWN_CITY", 404


class InvalidDays(ServiceError):
    code, status = "INVALID_DAYS", 400


def _lookup(city: str) -> dict:
    """Finds a city case-insensitively, ignoring extra spaces.
    On a miss, the error lists the supported cities so the caller can recover."""
    key = " ".join(city.strip().lower().split())
    if key in CITIES:
        return CITIES[key]
    raise UnknownCity(
        f"'{city}' is not a supported city. Try one of: {', '.join(list_supported_cities())}."
    )


def list_supported_cities() -> list[str]:
    return [c["name"] for c in CITIES.values()]


def get_current_weather(city: str) -> dict:
    c = _lookup(city)
    return {
        "city": c["name"],
        "country": c["country"],
        "temp_c": c["temp_c"],
        "condition": c["condition"],
        "humidity": c["humidity"],
        "wind_kph": c["wind_kph"],
    }


def get_forecast(city: str, days: int = 3) -> dict:
    """`days` forecast entries, day 1 = tomorrow. Derived from today's reading
    plus a fixed pattern, so every call returns the same numbers."""
    if not isinstance(days, int) or not 1 <= days <= MAX_FORECAST_DAYS:
        raise InvalidDays(f"days must be a whole number from 1 to {MAX_FORECAST_DAYS}.")
    c = _lookup(city)
    forecast = []
    for i in range(days):
        delta_t, condition, delta_h = FORECAST_PATTERN[i]
        forecast.append({
            "day": i + 1,
            "temp_c": c["temp_c"] + delta_t,
            "condition": condition,
            "humidity": max(0, min(100, c["humidity"] + delta_h)),   # keep it a percentage
        })
    return {"city": c["name"], "country": c["country"], "days": days, "forecast": forecast}
