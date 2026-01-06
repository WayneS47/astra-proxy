"""
Astra Backend - Main Application
FastAPI server providing astronomy-related APIs
"""

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from datetime import datetime, timezone
from typing import Dict, Tuple, Optional
import httpx
import os
import time
import asyncio
import re

# -------------------------------------------------
# App Initialization
# -------------------------------------------------

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

NASA_API_KEY = os.getenv("NASA_API_KEY", "DEMO_KEY")

GOES16_LATEST_IMAGE = (
    "https://cdn.star.nesdis.noaa.gov/GOES16/ABI/FD/GEOCOLOR/latest.jpg"
)

# -------------------------------------------------
# Weather Configuration
# -------------------------------------------------

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

# -------------------------------------------------
# Geocoding Configuration
# -------------------------------------------------

GEOCODE_CACHE: Dict[str, Tuple[float, dict]] = {}
GEOCODE_TTL_SECONDS = 86400  # 24 hours
GEOCODE_RETRY_DELAY = 0.15   # seconds (short; do not add noticeable lag)

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

# Static fallback coordinates for rare geocoding edge cases (last resort, instant, no network)
# Keep this intentionally small.
STATIC_LOCATION_FALLBACKS = {
    "fairbanks, alaska": (64.8378, -147.7164),
    "fairbanks alaska": (64.8378, -147.7164),
    "anchorage, alaska": (61.2181, -149.9003),
    "juneau, alaska": (58.3019, -134.4197),
}

# -------------------------------------------------
# Utilities
# -------------------------------------------------

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

def normalize_location_query(city: str) -> str:
    """
    Normalize inputs like:
    - 'Huntsville, AL' -> 'Huntsville Alabama US'
    Leaves non-US patterns alone.
    """
    match = re.match(r"^(.*?),\s*([A-Z]{2})$", city.strip())
    if match:
        city_name = match.group(1).strip()
        state_abbr = match.group(2)
        state_full = US_STATE_MAP.get(state_abbr)
        if state_full:
            return f"{city_name} {state_full} US"
    return city.strip()

def _static_fallback_payload(city: str, lat: float, lon: float) -> dict:
    return {
        "status": "ok",
        "source": "static_fallback",
        "latitude": lat,
        "longitude": lon,
        "name": city,
        "country": "US",
        "timezone": None,
        "timestamp": _now_iso()
    }

# -------------------------------------------------
# Startup: Weather Pre-Warm
# -------------------------------------------------

@app.on_event("startup")
async def startup_event():
    await prewarm_weather_cache()

async def prewarm_weather_cache():
    """Pre-warm weather cache for Brentwood, TN. Must never block startup."""
    try:
        async with httpx.AsyncClient(timeout=4.0) as client:
            resp = await client.get(
                "https://api.open-meteo.com/v1/forecast",
                params={
                    "latitude": PREWARM_LAT,
                    "longitude": PREWARM_LON,
                    "current_weather": True,
                    "temperature_unit": "fahrenheit",
                    "windspeed_unit": "mph"
                }
            )
            resp.raise_for_status()
            data = resp.json()

        current = data.get("current_weather")
        if not current:
            return

        weathercode = current.get("weathercode")
        payload = {
            "status": "ok",
            "source": "open_meteo",
            "location": {"latitude": PREWARM_LAT, "longitude": PREWARM_LON},
            "weather": {
                "temperature_f": round(current.get("temperature")),
                "windspeed_mph": round(current.get("windspeed", 0)),
                "condition": WEATHER_CODE_MAP.get(weathercode, "Unknown"),
                "weathercode": weathercode,
                "is_day": bool(current.get("is_day"))
            },
            "observed_at": current.get("time"),
            "timestamp": _now_iso()
        }

        WEATHER_CACHE[f"{PREWARM_LAT:.4f}:{PREWARM_LON:.4f}"] = (time.time(), payload)
    except Exception:
        pass

# -------------------------------------------------
# Health
# -------------------------------------------------

@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "timestamp": _now_iso(),
        "version": "2.0"
    }

# -------------------------------------------------
# API: Weather (Connector-safe: always 200)
# -------------------------------------------------

@app.get("/v1/weather")
async def get_weather(
    latitude: float = Query(..., ge=-90, le=90),
    longitude: float = Query(..., ge=-180, le=180)
):
    key = f"{latitude:.4f}:{longitude:.4f}"
    now = time.time()

    # Cache hit
    if key in WEATHER_CACHE:
        ts, cached = WEATHER_CACHE[key]
        if now - ts < WEATHER_TTL_SECONDS:
            return cached

    # Cache miss -> fetch
    try:
        async with httpx.AsyncClient(timeout=4.0) as client:
            resp = await client.get(
                "https://api.open-meteo.com/v1/forecast",
                params={
                    "latitude": latitude,
                    "longitude": longitude,
                    "current_weather": True,
                    "temperature_unit": "fahrenheit",
                    "windspeed_unit": "mph"
                }
            )
            resp.raise_for_status()
            data = resp.json()

        current = data.get("current_weather")
        if not current:
            # Connector-safe error payload
            return {
                "status": "error",
                "error": "missing_current_weather",
                "location": {"latitude": latitude, "longitude": longitude},
                "timestamp": _now_iso()
            }

        weathercode = current.get("weathercode")
        payload = {
            "status": "ok",
            "source": "open_meteo",
            "location": {"latitude": latitude, "longitude": longitude},
            "weather": {
                "temperature_f": round(current.get("temperature")),
                "windspeed_mph": round(current.get("windspeed", 0)),
                "condition": WEATHER_CODE_MAP.get(weathercode, "Unknown"),
                "weathercode": weathercode,
                "is_day": bool(current.get("is_day"))
            },
            "observed_at": current.get("time"),
            "timestamp": _now_iso()
        }

        WEATHER_CACHE[key] = (now, payload)
        return payload

    except Exception as e:
        # Never raise -> prevents "Error talking to connector"
        return {
            "status": "error",
            "error": "weather_fetch_failed",
            "detail": str(e),
            "location": {"latitude": latitude, "longitude": longitude},
            "timestamp": _now_iso()
        }

# -------------------------------------------------
# API: Geocoding (Normalize + Cache + Retry + Fallback + Connector-safe)
# -------------------------------------------------

@app.get("/v1/geocode")
async def geocode_location(city: str = Query(...)):
    city_raw = city.strip()
    cache_key = city_raw.lower()
    now = time.time()

    # Cache hit
    if cache_key in GEOCODE_CACHE:
        ts, cached = GEOCODE_CACHE[cache_key]
        if now - ts < GEOCODE_TTL_SECONDS:
            return cached

    # 1) STATIC FALLBACK SHORT-CIRCUIT (instant, no network)
    # This is the critical change for Fairbanks-class reliability.
    if cache_key in STATIC_LOCATION_FALLBACKS:
        lat, lon = STATIC_LOCATION_FALLBACKS[cache_key]
        payload = _static_fallback_payload(city_raw, lat, lon)
        GEOCODE_CACHE[cache_key] = (now, payload)
        return payload

    # Helper to fetch geocoding
    async def fetch(query: str):
        async with httpx.AsyncClient(timeout=4.0) as client:
            r = await client.get(
                "https://geocoding-api.open-meteo.com/v1/search",
                params={"name": query, "count": 1, "language": "en", "format": "json"}
            )
            r.raise_for_status()
            return r.json()

    try:
        normalized = normalize_location_query(city_raw)

        # 2) Primary attempt (+ one quick retry)
        try:
            data = await fetch(normalized)
        except Exception:
            await asyncio.sleep(GEOCODE_RETRY_DELAY)
            data = await fetch(normalized)

        # 3) Fallback attempt: simpler query
        if not data.get("results"):
            simple_city = city_raw.split(",")[0].strip()
            data = await fetch(f"{simple_city} US")

        # 4) No results -> connector-safe "not_found" payload (no 404)
        if not data.get("results"):
            return {
                "status": "not_found",
                "error": "geocode_no_results",
                "query": city_raw,
                "timestamp": _now_iso()
            }

        r = data["results"][0]
        payload = {
            "status": "ok",
            "source": "open_meteo_geocode",
            "latitude": r.get("latitude"),
            "longitude": r.get("longitude"),
            "name": r.get("name"),
            "country": r.get("country"),
            "timezone": r.get("timezone"),
            "timestamp": _now_iso()
        }

        GEOCODE_CACHE[cache_key] = (now, payload)
        return payload

    except Exception as e:
        # Never raise -> prevents "Error talking to connector"
        return {
            "status": "error",
            "error": "geocode_failed",
            "detail": str(e),
            "query": city_raw,
            "timestamp": _now_iso()
        }

# -------------------------------------------------
# Other APIs (kept minimal; placeholders preserved)
# -------------------------------------------------

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
        "timestamp": _now_iso()
    }

@app.get("/v1/iss")
async def get_iss_position():
    try:
        async with httpx.AsyncClient(timeout=6.0) as client:
            response = await client.get("http://api.open-notify.org/iss-now.json")
            response.raise_for_status()
            data = response.json()
        return {
            "status": "ok",
            "iss_position": data.get("iss_position"),
            "timestamp": data.get("timestamp"),
            "message": data.get("message")
        }
    except Exception as e:
        return {"status": "error", "error": "iss_fetch_failed", "detail": str(e), "timestamp": _now_iso()}

@app.get("/v1/apod")
async def get_apod(date: Optional[str] = None):
    try:
        url = "https://api.nasa.gov/planetary/apod"
        params = {"api_key": NASA_API_KEY}
        if date:
            params["date"] = date
        async with httpx.AsyncClient(timeout=8.0) as client:
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
            "timestamp": _now_iso()
        }
    except Exception as e:
        return {"status": "error", "error": "apod_fetch_failed", "detail": str(e), "timestamp": _now_iso()}

@app.get("/v1/asteroids")
async def get_asteroids(days_ahead: int = Query(30, ge=1, le=90)):
    try:
        today = datetime.now().strftime("%Y-%m-%d")
        url = "https://api.nasa.gov/neo/rest/v1/feed"
        params = {"start_date": today, "api_key": NASA_API_KEY}
        async with httpx.AsyncClient(timeout=12.0) as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
            data = response.json()
        return {
            "status": "ok",
            "element_count": data.get("element_count", 0),
            "near_earth_objects": data.get("near_earth_objects", {}),
            "timestamp": _now_iso()
        }
    except Exception as e:
        return {"status": "error", "error": "asteroids_fetch_failed", "detail": str(e), "timestamp": _now_iso()}

@app.get("/v1/planetary-position")
async def get_planetary_position(
    planet: str = Query(...),
    date: Optional[str] = None,
    time_str: Optional[str] = Query(None, alias="time"),
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
        "timestamp": _now_iso()
    }

@app.get("/v1/constellations")
async def get_constellations(
    latitude: float = Query(..., ge=-90, le=90),
    longitude: float = Query(..., ge=-180, le=180),
    date: Optional[str] = None,
    time_str: Optional[str] = Query(None, alias="time"),
    min_altitude: float = Query(20.0, ge=0, le=90)
):
    return {
        "status": "ok",
        "location": {"latitude": latitude, "longitude": longitude},
        "constellations": [],
        "timestamp": _now_iso()
    }

@app.get("/v1/earth-image")
async def get_earth_image():
    return JSONResponse(
        content={
            "status": "ok",
            "source": "NOAA GOES-16",
            "description": "Near-real-time full-disk Earth image",
            "image_url": GOES16_LATEST_IMAGE,
            "timestamp": _now_iso(),
            "update_frequency": "10-15 minutes"
        },
        headers={"Cache-Control": "public, max-age=600"}
    )

@app.get("/")
async def root():
    return {
        "name": "Astra Astronomy API",
        "version": "2.0",
        "status": "operational",
        "documentation": "/docs"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
