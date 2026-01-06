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
            "location": {
                "latitude": PREWARM_LAT,
                "longitude": PREWARM_LON
            },
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

        cache_key = f"{PREWARM_LAT:.4f}:{PREWARM_LON:.4f}"
        WEATHER_CACHE[cache_key] = (time.time(), result)

    except Exception:
        pass

# -----------------------------
# Health
# -----------------------------

@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "version": "2.0"
    }

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
            raise ValueError("Missing current_weather")

        weathercode = current.get("weathercode")
        condition = WEATHER_CODE_MAP.get(weathercode, "Unknown")

        result = {
            "status": "ok",
            "location": {
                "latitude": latitude,
                "longitude": longitude
            },
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

        WEATHER_CACHE[cache_key] = (now, result)
        return result

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# -----------------------------
# API 9: Geocoding (Cache + Retry)
# -----------------------------

@app.get("/v1/geocode")
async def geocode_location(city: str = Query(...)):
    key = city.strip().lower()
    now = time.time()

    # Cache hit
    if key in GEOCODE_CACHE:
        cached_time, cached_data = GEOCODE_CACHE[key]
        if now - cached_time < GEOCODE_TTL_SECONDS:
            return cached_data

    async def fetch_geocode():
        url = "https://geocoding-api.open-meteo.com/v1/search"
        params = {
            "name": city,
            "count": 1,
            "language": "en",
            "format": "json"
        }
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
            return response.json()

    try:
        try:
            data = await fetch_geocode()
        except Exception:
            await asyncio.sleep(GEOCODE_RETRY_DELAY)
            data = await fetch_geocode()

        if not data.get("results"):
            raise HTTPException(status_code=404, detail="Location not found")

        result = data["results"][0]
        payload = {
            "status": "ok",
            "latitude": result.get("latitude"),
            "longitude": result.get("longitude"),
            "name": result.get("name"),
            "country": result.get("country"),
            "timezone": result.get("timezone"),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

        GEOCODE_CACHE[key] = (now, payload)
        return payload

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# -----------------------------
# API 8: Earth Image
# -----------------------------

@app.get("/v1/earth-image")
async def get_earth_image():
    return JSONResponse(
        content={
            "status": "ok",
            "source": "NOAA GOES-16",
            "description": "Near-real-time full-disk Earth image",
            "image_url": GOES16_LATEST_IMAGE,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "update_frequency": "10-15 minutes"
        },
        headers={"Cache-Control": "public, max-age=600"}
    )

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
