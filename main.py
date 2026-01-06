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
        # Pre-warm failures must never block startup
        pass

# -----------------------------
# Health Check
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
    """Get current weather conditions (fast, cached)"""

    cache_key = f"{latitude:.4f}:{longitude:.4f}"
    now = time.time()

    # Cache hit
    if cache_key in WEATHER_CACHE:
        cached_time, cached_data = WEATHER_CACHE[cache_key]
        if now - cached_time < WEATHER_TTL_SECONDS:
            return cached_data

    # Cache miss → fetch Open-Meteo
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
# API 2: Moon Phase (Placeholder)
# -----------------------------

@app.get("/v1/moon")
async def get_moon_phase(
    date: Optional[str] = None,
    latitude: Optional[float] = None,
    longitude: Optional[float] = None
):
    return {
        "status": "ok",
        "phase": "WAXING_CRESCENT",
        "illumination": 15.3,
        "age_days": 3.2,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }

# -----------------------------
# API 3: ISS Position
# -----------------------------

@app.get("/v1/iss")
async def get_iss_position():
    try:
        url = "http://api.open-notify.org/iss-now.json"
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(url)
            response.raise_for_status()
            data = response.json()

        return {
            "status": "ok",
            "iss_position": data.get("iss_position"),
            "timestamp": data.get("timestamp"),
            "message": data.get("message")
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# -----------------------------
# API 4: APOD
# -----------------------------

@app.get("/v1/apod")
async def get_apod(date: Optional[str] = None):
    try:
        url = "https://api.nasa.gov/planetary/apod"
        params = {"api_key": NASA_API_KEY}
        if date:
            params["date"] = date

        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
            data = response.json()

        return {
            "status": "ok",
            "title": data.get("title"),
            "date": data.get("date"),
            "explanation": data.get("explanation"),
            "url": data.get("url"),
            "hdurl": data.get("hdurl"),
            "media_type": data.get("media_type"),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# -----------------------------
# API 5: Near-Earth Asteroids
# -----------------------------

@app.get("/v1/asteroids")
async def get_asteroids(
    days_ahead: int = Query(30, ge=1, le=90)
):
    try:
        today = datetime.now().strftime("%Y-%m-%d")
        url = "https://api.nasa.gov/neo/rest/v1/feed"
        params = {
            "start_date": today,
            "api_key": NASA_API_KEY
        }

        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
            data = response.json()

        return {
            "status": "ok",
            "element_count": data.get("element_count", 0),
            "near_earth_objects": data.get("near_earth_objects", {}),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# -----------------------------
# API 6: Planetary Position (Placeholder)
# -----------------------------

@app.get("/v1/planetary-position")
async def get_planetary_position(
    planet: str = Query(...),
    date: Optional[str] = None,
    time: Optional[str] = None,
    latitude: Optional[float] = None,
    longitude: Optional[float] = None
):
    return {
        "status": "ok",
        "planet": planet,
        "right_ascension": 123.45,
        "declination": 23.45,
        "distance_au": 5.2,
        "magnitude": -2.5,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }

# -----------------------------
# API 7: Visible Constellations (Placeholder)
# -----------------------------

@app.get("/v1/constellations")
async def get_constellations(
    latitude: float = Query(..., ge=-90, le=90),
    longitude: float = Query(..., ge=-180, le=180),
    date: Optional[str] = None,
    time: Optional[str] = None,
    min_altitude: float = Query(20.0, ge=0, le=90)
):
    return {
        "status": "ok",
        "location": {"latitude": latitude, "longitude": longitude},
        "constellations": [],
        "timestamp": datetime.now(timezone.utc).isoformat()
    }

# -----------------------------
# API 8: Earth Image (GOES-16)
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
# API 9: Geocoding
# -----------------------------

@app.get("/v1/geocode")
async def geocode_location(city: str = Query(...)):
    try:
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
            data = response.json()

        if not data.get("results"):
            raise HTTPException(status_code=404, detail="Location not found")

        result = data["results"][0]
        return {
            "status": "ok",
            "latitude": result.get("latitude"),
            "longitude": result.get("longitude"),
            "name": result.get("name"),
            "country": result.get("country"),
            "timezone": result.get("timezone"),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

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
