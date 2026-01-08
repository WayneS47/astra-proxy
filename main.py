"""
Astra Backend - Main Application
FastAPI server providing astronomy-related APIs
"""

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from datetime import datetime, timezone
from typing import Optional, Dict, Tuple
import httpx
import os
import time

# -----------------------------
# App Initialization
# -----------------------------

app = FastAPI(
    title="Astra Astronomy API",
    version="2.0",
    description="Backend API for Astra astronomy companion"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -----------------------------
# Environment / Constants
# -----------------------------

NASA_API_KEY = os.getenv("NASA_API_KEY", "DEMO_KEY")

GOES16_LATEST_IMAGE = (
    "https://cdn.star.nesdis.noaa.gov/GOES16/ABI/FD/GEOCOLOR/latest.jpg"
)

# -----------------------------
# Weather Configuration
# -----------------------------

WEATHER_CACHE: Dict[str, Tuple[float, dict]] = {}
WEATHER_TTL_SECONDS = 300  # 5 minutes

WEATHER_CODE_MAP = {
    0: "Clear",
    1: "Mostly clear",
    2: "Partly cloudy",
    3: "Overcast",
    45: "Fog",
    48: "Depositing rime fog",
    51: "Light drizzle",
    53: "Moderate drizzle",
    55: "Dense drizzle",
    61: "Light rain",
    63: "Rain",
    65: "Heavy rain",
    71: "Light snow",
    73: "Snow",
    75: "Heavy snow",
    80: "Rain showers",
    81: "Heavy rain showers",
    95: "Thunderstorm"
}

# Default pre-warm location: Brentwood, TN
PREWARM_LAT = 36.0331
PREWARM_LON = -86.7828

# -----------------------------
# Startup: Weather Pre-Warm
# -----------------------------

@app.on_event("startup")
async def startup_event():
    await prewarm_weather_cache()


async def prewarm_weather_cache():
    """Pre-warm weather cache for Brentwood, TN"""
    try:
        await fetch_and_cache_weather(PREWARM_LAT, PREWARM_LON)
    except Exception:
        pass

# -----------------------------
# Utility
# -----------------------------

def get_cardinal_direction(degree):
    if degree is None:
        return None
    directions = ['N', 'NE', 'E', 'SE', 'S', 'SW', 'W', 'NW']
    idx = int((degree + 22.5) / 45.0) % 8
    return directions[idx]

async def fetch_and_cache_weather(latitude: float, longitude: float):
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": latitude,
        "longitude": longitude,
        "current_weather": True,
        "temperature_unit": "fahrenheit",
        "windspeed_unit": "mph"
    }

    async with httpx.AsyncClient(timeout=5.0) as client:
        response = await client.get(url, params=params)
        response.raise_for_status()
        data = response.json()

    current = data.get("current_weather")
    if not current:
        raise ValueError("Missing current_weather from Open-Meteo")

    weathercode = current.get("weathercode")
    condition = WEATHER_CODE_MAP.get(weathercode, "Unknown")

    result = {
        "status": "ok",
        "location": {
            "latitude": latitude,
            "longitude": longitude
        },
        "weather": {
            "temperature_fahrenheit": round(current.get("temperature")),
            "temperature_celsius": round((current.get("temperature") - 32) * 5 / 9, 1),
            "wind_speed_mph": round(current.get("windspeed", 0)),
            "wind_direction": current.get("winddirection"),
            "wind_direction_cardinal": get_cardinal_direction(current.get("winddirection")),
            "cloud_cover_percent": None,
            "visibility_miles": None,
            "conditions": condition,
            "is_day": bool(current.get("is_day"))
        },
        "observed_at": current.get("time"),
        "timestamp": datetime.now(timezone.utc).isoformat()
    }

    cache_key = f"{latitude:.4f}:{longitude:.4f}"
    WEATHER_CACHE[cache_key] = (time.time(), result)
    return result

# -----------------------------
# API 1: Weather
# -----------------------------

@app.get("/v1/weather")
async def get_weather(
    latitude: float = Query(..., ge=-90, le=90),
    longitude: float = Query(..., ge=-180, le=180)
):
    cache_key = f"{latitude:.4f}:{longitude:.4f}"
    now = time.time()

    if cache_key in WEATHER_CACHE:
        cached_time, cached_data = WEATHER_CACHE[cache_key]
        if now - cached_time < WEATHER_TTL_SECONDS:
            return cached_data

    try:
        return await fetch_and_cache_weather(latitude, longitude)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
