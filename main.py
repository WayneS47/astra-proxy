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
import asyncio
import re

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

PREWARM_LAT = 36.0331
PREWARM_LON = -86.7828

# -----------------------------
# Geocoding Configuration
# -----------------------------

GEOCODE_CACHE: Dict[str, Tuple[float, dict]] = {}
GEOCODE_TTL_SECONDS = 86400  # 24 hours
GEOCODE_RETRY_DELAY = 0.25  # seconds

US_STATE_MAP = {
    "AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas",
    "CA": "California", "CO": "Colorado", "CT": "Connecticut", "DE": "Delaware",
    "FL": "Florida", "GA": "Georgia", "HI": "Hawaii", "ID": "Idaho",
    "IL": "Illinois", "IN": "Indiana", "IA": "Iowa", "KS": "Kansas",
    "KY": "Kentucky", "LA": "Louisiana", "ME": "Maine", "MD": "Maryland",
    "MA": "Massachusetts", "MI": "Michigan", "MN": "Minnesota", "MS": "Mississippi",
    "MO": "Missouri", "MT": "Montana", "NE": "Nebraska", "NV": "Nevada",
    "NH": "New Hampshire", "NJ": "New Jersey", "NM": "New Mexico", "NY": "New York",
    "NC": "North Carolina", "ND": "North Dakota", "OH": "Ohio", "OK": "Oklahoma",
    "OR": "Oregon", "PA": "Pennsylvania", "RI": "Rhode Island",
    "SC": "South Carolina", "SD": "South Dakota", "TN": "Tennessee",
    "TX": "Texas", "UT": "Utah", "VT": "Vermont", "VA": "Virginia",
    "WA": "Washington", "WV": "West Virginia", "WI": "Wisconsin", "WY": "Wyoming"
}

# -----------------------------
# Utility: Normalize US City/State
# -----------------------------

def normalize_location_query(city: str) -> str:
    """
    Normalize inputs like:
    - 'Huntsville, AL' -> 'Huntsville Alabama US'
    """
    match = re.match(r"^(.*?),\s*([A-Z]{2})$", city.strip())
    if match:
        city_name = match.group(1).strip()
        state_abbr = match.group(2)
        state_full = US_STATE_MAP.get(state_abbr)
        if state_full:
            return f"{city_name} {state_full} US"
    return city.strip()

# -----------------------------
# Startup: Weather Pre-Warm
# -----------------------------

@app.on_event("startup")
async def startup_event():
    await prewarm_weather_cache()

async def prewarm_weather_cache():
    try:
        url = "https://api.open-meteo.com/v1/forecast"
        params = {
            "latitude": PREWARM_LAT,
            "longitude": PREWARM_LON,
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
            return

        weathercode = current.get("weathercode")
        condition = WEATHER_CODE_MAP.get(weathercode, "Unknown")

        result = {
            "status": "ok",
            "location": {"latitude": PREWARM_LAT, "longitude": PREWARM_LON},
            "weather": {
                "temperature_f": round(current.get("temperature")),
                "windspeed_mph": round(current.get("windspeed", 0)),
                "condition": condition,
                "weathercode": weathercode,
                "is_day": bool(current.get("is_day"))
            },
            "observed_at": current.get("time"),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

        WEATHER_CACHE[f"{PREWARM_LAT:.4f}:{PREWARM_LON:.4f}"] = (time.time(), result)

    except Exception:
        pass

# -----------------------------
# API: Weather
# -----------------------------

@app.get("/v1/weather")
async def get_weather(
    latitude: float = Query(..., ge=-90, le=90),
    longitude: float = Query(..., ge=-180, le=180)
):
    key = f"{latitude:.4f}:{longitude:.4f}"
    now = time.time()

    if key in WEATHER_CACHE:
        ts, cached = WEATHER_CACHE[key]
        if now - ts < WEATHER_TTL_SECONDS:
            return cached

    try:
        url = "https://api.open-meteo.com/v1/forecast"
        params = {
            "latitude": latitude,
            "longitude": longitude,
            "current_weather": True,
            "temperature_unit": "fahrenheit",
            "windspeed_unit": "mph"
        }

        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()

        current = data.get("current_weather")
        if not current:
            raise ValueError("Missing current_weather")

        weathercode = current.get("weathercode")
        condition = WEATHER_CODE_MAP.get(weathercode, "Unknown")

        result = {
            "status": "ok",
            "location": {"latitude": latitude, "longitude": longitude},
            "weather": {
                "temperature_f": round(current.get("temperature")),
                "windspeed_mph": round(current.get("windspeed", 0)),
                "condition": condition,
                "weathercode": weathercode,
                "is_day": bool(current.get("is_day"))
            },
            "observed_at": current.get("time"),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

        WEATHER_CACHE[key] = (now, result)
        return result

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# -----------------------------
# API: Geocoding (Normalize + Retry + Fallback)
# -----------------------------

@app.get("/v1/geocode")
async def geocode_location(city: str = Query(...)):
    cache_key = city.strip().lower()
    now = time.time()

    if cache_key in GEOCODE_CACHE:
        ts, cached = GEOCODE_CACHE[cache_key]
        if now - ts < GEOCODE_TTL_SECONDS:
            return cached

    async def fetch(query: str):
        url = "https://geocoding-api.open-meteo.com/v1/search"
        params = {"name": query, "count": 1, "language": "en", "format": "json"}
        async with httpx.AsyncClient(timeout=5.0) as client:
            r = await client.get(url, params=params)
            r.raise_for_status()
            return r.json()

    try:
        normalized = normalize_location_query(city)

        try:
            data = await fetch(normalized)
        except Exception:
            await asyncio.sleep(GEOCODE_RETRY_DELAY)
            data = await fetch(normalized)

        if not data.get("results"):
            # Fallback: city name only
            simple_city = city.split(",")[0].strip()
            data = await fetch(f"{simple_city} US")

        if not data.get("results"):
            raise HTTPException(status_code=404, detail="Location not found")

        r = data["results"][0]
        payload = {
            "status": "ok",
            "latitude": r.get("latitude"),
            "longitude": r.get("longitude"),
            "name": r.get("name"),
            "country": r.get("country"),
            "timezone": r.get("timezone"),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

        GEOCODE_CACHE[cache_key] = (now, payload)
        return payload

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# -----------------------------
# Root
# -----------------------------

@app.get("/")
async def root():
    return {
        "name": "Astra Astronomy API",
        "version": "2.0",
        "status": "operational",
        "documentation": "/docs"
    }

# -----------------------------
# Local Run
# -----------------------------

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
