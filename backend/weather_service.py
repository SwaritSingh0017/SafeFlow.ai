"""
Weather Service — fetches real-time data from OpenWeatherMap.
API key loaded from environment variable only — no hardcoding.
Returns rich weather object used by parametric trigger engine.
"""

import os
import logging
import requests
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger("weather_service")

OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY", "")

# Fallback weather data used when API key is missing or call fails (demo safety net)
_FALLBACK_WEATHER = {
    "temperature": 32.0,
    "rainfall":    0.0,
    "wind":        12.0,
    "humidity":    60,
    "description": "Clear sky (demo fallback)",
    "aqi":         120,
}


def get_weather(city: str) -> dict:
    """
    Fetch current weather for a city.
    Returns dict with: temperature, rainfall, wind, humidity, description, aqi
    Falls back to safe defaults if API unavailable.
    """
    if not OPENWEATHER_API_KEY:
        logger.warning("[Weather] OPENWEATHER_API_KEY not set — using fallback data")
        return {**_FALLBACK_WEATHER, "city": city}

    try:
        url = (
            f"https://api.openweathermap.org/data/2.5/weather"
            f"?q={city},IN&appid={OPENWEATHER_API_KEY}&units=metric"
        )
        resp = requests.get(url, timeout=5)
        resp.raise_for_status()
        data = resp.json()

        rainfall    = data.get("rain", {}).get("1h", 0.0)
        temperature = data.get("main", {}).get("temp", 30.0)
        wind_ms     = data.get("wind", {}).get("speed", 0.0)
        humidity    = data.get("main", {}).get("humidity", 60)
        description = data.get("weather", [{}])[0].get("description", "").capitalize()

        lat = data.get("coord", {}).get("lat")
        lon = data.get("coord", {}).get("lon")
        aqi_val = _FALLBACK_WEATHER["aqi"]
        
        if lat is not None and lon is not None:
            try:
                aqi_url = f"https://api.openweathermap.org/data/2.5/air_pollution?lat={lat}&lon={lon}&appid={OPENWEATHER_API_KEY}"
                aqi_resp = requests.get(aqi_url, timeout=5)
                if aqi_resp.ok:
                    pm25 = aqi_resp.json().get("list", [{}])[0].get("components", {}).get("pm2_5")
                    if pm25 is not None:
                        # Rough mapping of PM2.5 to Indian AQI scale for parametric matching
                        aqi_val = min(500, int(pm25 * 3.5 + 30))
            except Exception as e:
                logger.warning(f"[Weather] AQI fetch failed for {city}: {e}")

        return {
            "city":        city,
            "temperature": round(temperature, 1),
            "rainfall":    round(rainfall, 2),
            "wind":        round(wind_ms * 3.6, 1),   # m/s → km/h
            "humidity":    humidity,
            "description": description,
            "aqi":         aqi_val,
        }

    except Exception as e:
        logger.error(f"[Weather] API error for {city}: {e}")
        return {**_FALLBACK_WEATHER, "city": city}
