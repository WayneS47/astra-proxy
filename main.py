from fastapi import FastAPI, Query, HTTPException, Request, Depends
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
# Simple Logging
# =================================================

def log(message: str):
    ts = datetime.now(timezone.utc).isoformat()
    print(f"[{ts}] {message}", flush=True)

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
# Rate Limiting (Per IP)
# =================================================

RATE_LIMIT = {}
RATE_LIMIT_WINDOW = 60      # seconds
RATE_LIMIT_MAX = 60         # requests per window

def check_rate_limit(request: Request):
    ip = request.client.host if request.client else "unknown"
    now = time()

    window = RATE_LIMIT.get(ip, [])
    window = [ts for ts in window if now - ts < RATE_LIMIT_WINDOW]

    if len(window) >= RATE_LIMIT_MAX:
        log(f"RATE LIMIT exceeded for IP {ip}")
        raise HTTPException(
            status_code=429,
            detail="Too many requests. Please slow down."
        )

    window.append(now)
    RATE_LIMIT[ip] = window

# =================================================
# Helpers
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
    if code in (1, 2, 3):
        return "Partly Cloudy" if code in (1, 2) else "Cloudy"
    if code in (45, 48):
        return "Fog"
    if code in (61, 63, 65):
        return "Rain"
    if code in (71, 73, 75):
        return "Snow"
    if code in (80, 81, 82):
        return "Rain Showers"
    if code in (95, 96, 99):
        return "Thunderstorm"
    return "Unknown"

# =================================================
# WEATHER
# =================================================

@app.get("/weather")
def get_weather(
    request: Request,
    city: str = Query(...),
    state: str = Query(...),
    _: None = Depends(check_rate_limit)
):
    cache_key = f"weather:{city}:{state}"
    cached = get_cache(cache_key)
    if cached:
        log("WEATHER cache hit")
        return cached

    log("WEATHER request")

    geocode_url = "https://nominatim.openstreetmap.org/search"
    geocode_params = {"q": f"{city}, {state}", "format": "json", "limit": 1}
    headers = {"User-Agent": "astra-proxy/1.0"}

    try:
        geo = httpx.get(geocode_url, params=geocode_params, headers=headers, timeout=10)
        geo.raise_for_status()
        geo = geo.json()
    except Exception as e:
        log(f"WEATHER geocode error: {e}")
        raise HTTPException(status_code=502, detail="Geocoding failed")

    if not geo:
        raise HTTPException(status_code=404, detail="Location not found")

    lat, lon = float(geo[0]["lat"]), float(geo[0]["lon"])

    try:
        w_resp = httpx.get(
            "https://api.open-meteo.com/v1/forecast",
            params={"latitude": lat, "longitude": lon, "current_weather": "true"},
            timeout=10
        )
        w_resp.raise_for_status()
        data = w_resp.json()
    except Exception as e:
        log(f"WEATHER fetch error: {e}")
        raise HTTPException(status_code=502, detail="Weather service failed")

    cw = data.get("current_weather")
    if not cw:
        raise HTTPException(status_code=502, detail="Weather data unavailable")

    response = {
        "temperature_c": cw["temperature"],
        "temperature_f": round(c_to_f(cw["temperature"]), 1),
        "wind_kmh": cw["windspeed"],
        "wind_mph": round(kmh_to_mph(cw["windspeed"]), 1),
        "wind_direction": deg_to_compass_16(cw["winddirection"]),
        "sky": weathercode_to_sky(cw["weathercode"]),
        "daylight": bool(cw["is_day"]),
    }

    set_cache(cache_key, response, ttl_seconds=60)
    return response

# =================================================
# MOON
# =================================================

@app.get("/moon")
def get_moon(
    request: Request,
    moon_date: str | None = None,
    _: None = Depends(check_rate_limit)
):
    target = date.today() if not moon_date else datetime.strptime(moon_date, "%Y-%m-%d").date()

    known_new_moon = datetime(2000, 1, 6, 18, 14, tzinfo=timezone.utc)
    target_dt = datetime(target.year, target.month, target.day, tzinfo=timezone.utc)

    synodic = 29.53058867
    age = ((target_dt - known_new_moon).total_seconds() / 86400) % synodic
    illum = (1 - math.cos(2 * math.pi * age / synodic)) / 2

    return {
        "date": target.isoformat(),
        "phase": round(age, 1),
        "illumination_percent": round(illum * 100, 1),
    }

# =================================================
# APOD
# =================================================

@app.get("/apod")
def get_apod(
    request: Request,
    apod_date: str | None = None,
    _: None = Depends(check_rate_limit)
):
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
        log(f"APOD error: {e}")
        raise HTTPException(status_code=502, detail="APOD service failed")

    return data

# =================================================
# ISS (live, no cache)
# =================================================

@app.get("/iss")
def get_iss(
    request: Request,
    _: None = Depends(check_rate_limit)
):
    log("ISS request")

    try:
        resp = httpx.get("https://api.wheretheiss.at/v1/satellites/25544", timeout=10)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        log(f"ISS error: {e}")
        raise HTTPException(status_code=502, detail="ISS service failed")

    return {
        "timestamp": data["timestamp"],
        "latitude": round(data["latitude"], 4),
        "longitude": round(data["longitude"], 4),
        "altitude_km": round(data["altitude"], 1),
        "altitude_miles": round(km_to_miles(data["altitude"]), 1),
        "velocity_kmh": round(data["velocity"], 1),
        "velocity_mph": round(kmh_to_mph(data["velocity"]), 1),
        "visibility": data.get("visibility"),
    }

# =================================================
# Local Run
# =================================================

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
