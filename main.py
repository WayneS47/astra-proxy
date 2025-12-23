from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import httpx
import uvicorn
from datetime import datetime, date, timezone
import math
import os
from time import time

app = FastAPI()

# =================================================
# CORS (safe for GPT Actions)
# =================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# =================================================
# Simple In-Memory Cache (TTL-based)
# =================================================

CACHE = {}

def get_cache(key: str):
    entry = CACHE.get(key)
    if not entry:
        return None
    value, expires_at = entry
    if time() > expires_at:
        del CACHE[key]
        return None
    return value

def set_cache(key: str, value, ttl_seconds: int):
    CACHE[key] = (value, time() + ttl_seconds)

# =================================================
# Helper Functions
# =================================================

def km_to_miles(km: float) -> float:
    return km * 0.621371

def c_to_f(c: float) -> float:
    return (c * 9.0 / 5.0) + 32.0

def kmh_to_mph(kmh: float) -> float:
    return kmh * 0.621371

def deg_to_compass_16(deg: float) -> str:
    directions = [
        "N", "NNE", "NE", "ENE",
        "E", "ESE", "SE", "SSE",
        "S", "SSW", "SW", "WSW",
        "W", "WNW", "NW", "NNW"
    ]
    deg = deg % 360.0
    idx = int((deg + 11.25) // 22.5) % 16
    return directions[idx]

def weathercode_to_sky(code: int) -> str:
    if code == 0:
        return "Clear"
    if code in (1, 2):
        return "Partly Cloudy"
    if code == 3:
        return "Cloudy"
    if code in (45, 48):
        return "Fog"
    if code in (61, 63, 65):
        return "Rain"
    if code in (71, 73, 75):
        return "Snow"
    if code in (95, 96, 99):
        return "Thunderstorm"
    return "Unknown"

# =================================================
# WEATHER
# =================================================

@app.get("/weather")
def get_weather(
    city: str = Query(..., description="City name"),
    state: str = Query(..., description="State name or abbreviation")
):
    cache_key = f"weather:{city.lower()}:{state.lower()}"
    cached = get_cache(cache_key)
    if cached:
        return cached

    geocode_url = "https://nominatim.openstreetmap.org/search"
    geocode_params = {
        "q": f"{city}, {state}, USA",
        "format": "json",
        "limit": 1
    }
    headers = {"User-Agent": "astra-proxy/1.0"}

    try:
        geo_resp = httpx.get(geocode_url, params=geocode_params, headers=headers, timeout=10)
        geo_resp.raise_for_status()
        geo = geo_resp.json()
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Geocoding failed: {str(e)}")

    if not geo:
        raise HTTPException(status_code=404, detail="Location not found")

    lat = float(geo[0]["lat"])
    lon = float(geo[0]["lon"])

    weather_url = "https://api.open-meteo.com/v1/forecast"
    weather_params = {
        "latitude": lat,
        "longitude": lon,
        "current_weather": "true"
    }

    try:
        w_resp = httpx.get(weather_url, params=weather_params, timeout=10)
        w_resp.raise_for_status()
        data = w_resp.json()
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Weather service failed: {str(e)}")

    cw = data.get("current_weather")
    if not cw:
        raise HTTPException(status_code=502, detail="Weather data unavailable")

    response = {
        "location": f"{city}, {state}",
        "latitude": lat,
        "longitude": lon,
        "temperature_c": cw["temperature"],
        "temperature_f": round(c_to_f(cw["temperature"]), 1),
        "wind_kmh": cw["windspeed"],
        "wind_mph": round(kmh_to_mph(cw["windspeed"]), 1),
        "wind_degrees": cw["winddirection"],
        "wind_direction": deg_to_compass_16(cw["winddirection"]),
        "sky": weathercode_to_sky(cw.get("weathercode", -1)),
        "daylight": bool(cw.get("is_day", 0))
    }

    set_cache(cache_key, response, ttl_seconds=90)
    return response

# =================================================
# MOON
# =================================================

def moon_info(target: date):
    known_new_moon = datetime(2000, 1, 6, 18, 14, tzinfo=timezone.utc)
    target_dt = datetime(target.year, target.month, target.day, tzinfo=timezone.utc)

    synodic = 29.53058867
    age = ((target_dt - known_new_moon).total_seconds() / 86400.0) % synodic
    illumination = (1 - math.cos(2 * math.pi * age / synodic)) / 2 * 100

    if age < 1.85:
        phase = "New Moon"
    elif age < 5.54:
        phase = "Waxing Crescent"
    elif age < 9.23:
        phase = "First Quarter"
    elif age < 12.92:
        phase = "Waxing Gibbous"
    elif age < 16.61:
        phase = "Full Moon"
    elif age < 20.30:
        phase = "Waning Gibbous"
    elif age < 23.99:
        phase = "Last Quarter"
    else:
        phase = "Waning Crescent"

    return phase, round(illumination, 1), round(age, 1)

@app.get("/moon")
def get_moon(moon_date: str | None = Query(None, description="YYYY-MM-DD (optional)")):
    target = date.today()
    if moon_date:
        try:
            target = datetime.strptime(moon_date, "%Y-%m-%d").date()
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid date format")

    cache_key = f"moon:{target.isoformat()}"
    cached = get_cache(cache_key)
    if cached:
        return cached

    phase, illumination, age = moon_info(target)

    response = {
        "date": target.isoformat(),
        "phase": phase,
        "illumination_percent": illumination,
        "age_days": age
    }

    set_cache(cache_key, response, ttl_seconds=86400)
    return response

# =================================================
# APOD
# =================================================

@app.get("/apod")
def get_apod(apod_date: str | None = Query(None, description="YYYY-MM-DD (optional)")):
    cache_key = f"apod:{apod_date or 'today'}"
    cached = get_cache(cache_key)
    if cached:
        return cached

    api_key = os.getenv("NASA_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="NASA API key not configured")

    params = {"api_key": api_key}
    if apod_date:
        params["date"] = apod_date

    try:
        resp = httpx.get("https://api.nasa.gov/planetary/apod", params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"NASA APOD failed: {str(e)}")

    response = {
        "date": data.get("date"),
        "title": data.get("title"),
        "explanation": data.get("explanation"),
        "media_type": data.get("media_type"),
        "url": data.get("url"),
        "hdurl": data.get("hdurl")
    }

    ttl = 3600 if not apod_date else 86400
    set_cache(cache_key, response, ttl)
    return response

# =================================================
# ISS (No API key required)
# =================================================

@app.get("/iss")
def get_iss():
    try:
        resp = httpx.get("https://api.wheretheiss.at/v1/satellites/25544", timeout=10)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"ISS service failed: {str(e)}")

    return {
        "timestamp": data["timestamp"],
        "latitude": round(data["latitude"], 4),
        "longitude": round(data["longitude"], 4),
        "altitude_km": round(data["altitude"], 1),
        "altitude_miles": round(km_to_miles(data["altitude"]), 1),
        "velocity_kmh": round(data["velocity"], 1),
        "velocity_mph": round(kmh_to_mph(data["velocity"]), 1),
        "visibility": data.get("visibility")
    }

# =================================================
# Local Run
# =================================================

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
