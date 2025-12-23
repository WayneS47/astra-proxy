from fastapi import FastAPI, Query, HTTPException, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
import httpx
import uvicorn
from datetime import datetime, date, timezone
import math
import os
import uuid
from time import time

app = FastAPI()

# =================================================
# CORS
# =================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# =================================================
# Logging
# =================================================

def log(message: str):
    ts = datetime.now(timezone.utc).isoformat()
    print(f"[{ts}] {message}", flush=True)

# =================================================
# Request ID Middleware
# =================================================

@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    request_id = str(uuid.uuid4())
    request.state.request_id = request_id

    start = time()
    log(f"[{request_id}] START {request.method} {request.url.path}")

    try:
        response = await call_next(request)
    except Exception as e:
        log(f"[{request_id}] UNHANDLED ERROR: {str(e)}")
        raise

    elapsed_ms = int((time() - start) * 1000)
    response.headers["X-Request-ID"] = request_id

    log(f"[{request_id}] END {request.url.path} ({elapsed_ms} ms)")
    return response

# =================================================
# Simple Cache (TTL)
# =================================================

CACHE = {}

def get_cache(key: str):
    entry = CACHE.get(key)
    if not entry:
        return None
    value, expires = entry
    if time() > expires:
        del CACHE[key]
        return None
    return value

def set_cache(key: str, value, ttl: int):
    CACHE[key] = (value, time() + ttl)

# =================================================
# Rate Limiting (Per IP, Request-ID aware)
# =================================================

RATE_LIMIT = {}
RATE_LIMIT_WINDOW = 60      # seconds
RATE_LIMIT_MAX = 60         # requests per window

def rate_limit(request: Request):
    ip = request.client.host if request.client else "unknown"
    rid = request.state.request_id
    now = time()

    window = RATE_LIMIT.get(ip, [])
    window = [ts for ts in window if now - ts < RATE_LIMIT_WINDOW]

    if len(window) >= RATE_LIMIT_MAX:
        log(f"[{rid}] RATE LIMIT exceeded for IP {ip}")
        raise HTTPException(
            status_code=429,
            detail="Too many requests. Please slow down."
        )

    window.append(now)
    RATE_LIMIT[ip] = window

# =================================================
# Helpers
# =================================================

def c_to_f(c): return (c * 9 / 5) + 32
def kmh_to_mph(k): return k * 0.621371
def km_to_miles(k): return k * 0.621371

def deg_to_compass_16(deg):
    dirs = ["N","NNE","NE","ENE","E","ESE","SE","SSE",
            "S","SSW","SW","WSW","W","WNW","NW","NNW"]
    return dirs[int((deg % 360 + 11.25) // 22.5) % 16]

def weathercode_to_sky(code):
    return {
        0: "Clear",
        1: "Partly Cloudy",
        2: "Partly Cloudy",
        3: "Cloudy",
        45: "Fog",
        48: "Fog",
        61: "Rain",
        63: "Rain",
        65: "Rain",
        71: "Snow",
        73: "Snow",
        75: "Snow",
        80: "Rain Showers",
        81: "Rain Showers",
        82: "Rain Showers",
        95: "Thunderstorm",
        96: "Thunderstorm",
        99: "Thunderstorm"
    }.get(code, "Unknown")

# =================================================
# WEATHER
# =================================================

@app.get("/weather")
def get_weather(
    request: Request,
    city: str = Query(...),
    state: str = Query(...),
    _: None = Depends(rate_limit)
):
    rid = request.state.request_id
    cache_key = f"weather:{city}:{state}"

    cached = get_cache(cache_key)
    if cached:
        log(f"[{rid}] WEATHER cache hit")
        return cached

    log(f"[{rid}] WEATHER fetch")

    geo = httpx.get(
        "https://nominatim.openstreetmap.org/search",
        params={"q": f"{city}, {state}", "format": "json", "limit": 1},
        headers={"User-Agent": "astra-proxy/1.0"},
        timeout=10
    ).json()

    if not geo:
        raise HTTPException(status_code=404, detail="Location not found")

    lat, lon = float(geo[0]["lat"]), float(geo[0]["lon"])

    data = httpx.get(
        "https://api.open-meteo.com/v1/forecast",
        params={"latitude": lat, "longitude": lon, "current_weather": "true"},
        timeout=10
    ).json()

    cw = data["current_weather"]

    response = {
        "temperature_f": round(c_to_f(cw["temperature"]), 1),
        "temperature_c": cw["temperature"],
        "wind_mph": round(kmh_to_mph(cw["windspeed"]), 1),
        "wind_kmh": cw["windspeed"],
        "wind_direction": deg_to_compass_16(cw["winddirection"]),
        "sky": weathercode_to_sky(cw["weathercode"]),
        "daylight": bool(cw["is_day"])
    }

    set_cache(cache_key, response, ttl=60)
    return response

# =================================================
# MOON
# =================================================

@app.get("/moon")
def get_moon(
    request: Request,
    date_str: str | None = None,
    _: None = Depends(rate_limit)
):
    rid = request.state.request_id
    target = date.today() if not date_str else datetime.strptime(date_str, "%Y-%m-%d").date()

    ref = datetime(2000, 1, 6, 18, 14, tzinfo=timezone.utc)
    tgt = datetime(target.year, target.month, target.day, tzinfo=timezone.utc)
    syn = 29.53058867
    age = ((tgt - ref).total_seconds() / 86400) % syn
    illum = (1 - math.cos(2 * math.pi * age / syn)) / 2

    log(f"[{rid}] MOON computed")

    return {
        "date": target.isoformat(),
        "age_days": round(age, 1),
        "illumination_percent": round(illum * 100, 1)
    }

# =================================================
# APOD
# =================================================

@app.get("/apod")
def get_apod(
    request: Request,
    date_str: str | None = None,
    _: None = Depends(rate_limit)
):
    rid = request.state.request_id
    api_key = os.getenv("NASA_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="NASA API key not configured")

    params = {"api_key": api_key}
    if date_str:
        params["date"] = date_str

    log(f"[{rid}] APOD fetch")

    data = httpx.get(
        "https://api.nasa.gov/planetary/apod",
        params=params,
        timeout=10
    ).json()

    return data

# =================================================
# ISS
# =================================================

@app.get("/iss")
def get_iss(
    request: Request,
    _: None = Depends(rate_limit)
):
    rid = request.state.request_id
    log(f"[{rid}] ISS fetch")

    data = httpx.get(
        "https://api.wheretheiss.at/v1/satellites/25544",
        timeout=10
    ).json()

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
