"""Mock weather for ten cities. Deterministic: same input, same output, forever.

Each city has a "today" reading. Forecasts are derived from it in service.py
by applying the fixed day-by-day pattern below, so the numbers look like
weather but never need a network call or a random generator.
"""

# Keys are lowercase; service.py lowercases the user's input before lookup.
CITIES = {
    "kochi":     {"name": "Kochi",     "country": "IN", "temp_c": 29, "condition": "Humid and cloudy", "humidity": 84, "wind_kph": 14},
    "bengaluru": {"name": "Bengaluru", "country": "IN", "temp_c": 24, "condition": "Partly cloudy",    "humidity": 65, "wind_kph": 11},
    "mumbai":    {"name": "Mumbai",    "country": "IN", "temp_c": 31, "condition": "Sunny",            "humidity": 70, "wind_kph": 18},
    "delhi":     {"name": "Delhi",     "country": "IN", "temp_c": 34, "condition": "Hazy sunshine",    "humidity": 40, "wind_kph": 9},
    "dubai":     {"name": "Dubai",     "country": "AE", "temp_c": 38, "condition": "Clear",            "humidity": 45, "wind_kph": 20},
    "london":    {"name": "London",    "country": "GB", "temp_c": 14, "condition": "Light rain",       "humidity": 78, "wind_kph": 22},
    "berlin":    {"name": "Berlin",    "country": "DE", "temp_c": 16, "condition": "Overcast",         "humidity": 60, "wind_kph": 15},
    "new york":  {"name": "New York",  "country": "US", "temp_c": 21, "condition": "Sunny",            "humidity": 55, "wind_kph": 17},
    "singapore": {"name": "Singapore", "country": "SG", "temp_c": 30, "condition": "Thunderstorms",    "humidity": 88, "wind_kph": 12},
    "sydney":    {"name": "Sydney",    "country": "AU", "temp_c": 19, "condition": "Windy",            "humidity": 58, "wind_kph": 30},
}

# How each forecast day differs from today. Index 0 = tomorrow.
# (temperature change in °C, condition to report, humidity change in %)
FORECAST_PATTERN = [
    (+1, "Partly cloudy", -3),
    (-2, "Light rain", +8),
    (+0, "Cloudy", +2),
    (+3, "Sunny", -10),
    (+2, "Sunny", -6),
    (-1, "Showers", +9),
    (+0, "Partly cloudy", 0),
]
MAX_FORECAST_DAYS = len(FORECAST_PATTERN)   # 7
