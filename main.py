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

def log(msg: str):
    ts = datetime.now(timezone.utc).isoformat()
    print(f"[{ts}] {msg}", flush=True)

# =================================================
# Request ID Middleware
# =================================================

@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    rid = str(uuid.uuid4())
    request.state.request_id = rid
    start = time()

    log(f"[{rid}] START {request.method} {request.url.path}")

    response = await call_next(request)

    elapsed = int((time() - start) * 1000)
    response.headers["X-Request-ID"] = rid
    log(f"[{rid}] END {request.url.path} ({elapsed} ms)")

    return response

# =================================================
# Cache (TTL)
# =================================================

CACHE = {}

def get_cache(key):
    entry = CACHE.get(key)
    if not entry:
        return None
    val, exp = entry
    if time() > exp:
        del CACHE[key]
        return None
    return val

def set_cache(key, val, ttl):
    CACHE[key] = (val, time() + ttl)

# =================================================
# Rate Limiting (Per Endpoint)
# =================================================

RATE_LIMITS = {
    "/weather": (60, 60),
    "/moon":    (120, 60),
    "/iss":     (60, 60),
    "/apod":    (15, 60),
}

RATE_STATE = {}

def rate_limit(request: Request):
    path = request.url.path
    limit, window = RATE_LIMITS.get(path, (30, 60))

    ip = request.client.host if request.client else "unknown"
    key = f"{ip}:{path}"
    now = time()

    hits = RATE_STATE.get(key, [])
    hits = [t for t in hits if now - t < window]

    remaining = limit - len(hits)
    reset = int(window - (now - hits[0])) if hits else window

    if remaining <= 0:
        rid = request.state.request_id
        log(f"[{rid}] RATE LIMIT HIT {path} from {ip}")
        raise HTTPException(
            status_code=429,
            detail="Too many requests. Please slow down.",
            headers={
                "X-RateLimit-Limit": str(limit),
                "X-RateLimit-Remaining": "0",
                "X-RateLimit-Reset": str(reset),
            },
        )

    hits.append(now)
    RATE_STATE[key] = hits

    request.state.rate_headers = {
        "X-RateLimit-Limit": str(limit),
        "X-RateLimit-Remaining": str(remaining - 1),
        "X-RateLimit-Reset": str(reset),
    }

# =================================================
# Helpers
# =================================================

def c_to_f(c): return round((c * 9 / 5) + 32, 1)
def kmh_to_mph(k): return round(k * 0.621371, 1)
def km_to_miles(k): return round(k * 0.621371, 1)

def deg_to_compass(d):
    dirs = ["N","NNE","NE","ENE","E","ESE","SE","SSE",
            "S","SSW","SW","WSW","W","WNW","NW","NNW"]
    return dirs[int((d % 360 + 11.25) // 22.5) % 16]

# =================================================
# WEATHER
# =================================================

@app.get("/weather")
def weather(
    request: Request,
    city: str = Query(...),
    state: str = Query(...),
    _: None = Depends(rate_limit)
):
    rid = request.state.request_id
    key = f"weather:{city}:{state}"

    cached = get_cache(key)
    if cached:
        log(f"[{rid}] WEATHER cache hit")
        return cached

    geo = httpx.get(
        "https://nominatim.openstreetmap.org/search",
        params={"q": f"{city}, {state}", "format": "json", "limit": 1},
        headers={"User-Agent": "astra-proxy/1.0"},
        timeout=10
    ).json()

    if not geo:
        raise HTTPException(404, "Location not found")

    lat, lon = float(geo[0]["lat"]), float(geo[0]["lon"])

    data = httpx.get(
        "https://api.open-meteo.com/v1/forecast",
        params={"latitude": lat, "longitude": lon, "current_weather": "true"},
        timeout=10
    ).json()

    cw = data["current_weather"]

    resp = {
        "temperature_f": c_to_f(cw["temperature"]),
        "temperature_c": cw["temperature"],
        "wind_mph": kmh_to_mph(cw["windspeed"]),
        "wind_kmh": cw["windspeed"],
        "wind_direction": deg_to_compass(cw["winddirection"]),
        "sky": cw["weathercode"],
        "daylight": bool(cw["is_day"]),
    }

    set_cache(key, resp, 60)
    return resp

# =================================================
# MOON
# =================================================

@app.get("/moon")
def moon(
    request: Request,
    date_str: str | None = None,
    _: None = Depends(rate_limit)
):
    target = date.today() if not date_str else datetime.strptime(date_str, "%Y-%m-%d").date()
    ref = datetime(2000,1,6,18,14,tzinfo=timezone.utc)
    tgt = datetime(target.year,target.month,target.day,tzinfo=timezone.utc)

    syn = 29.53058867
    age = ((tgt - ref).total_seconds()/86400)%syn
    illum = (1 - math.cos(2*math.pi*age/syn))/2

    return {
        "date": target.isoformat(),
        "age_days": round(age,1),
        "illumination_percent": round(illum*100,1)
    }

# =================================================
# APOD
# =================================================

@app.get("/apod")
def apod(
    request: Request,
    date_str: str | None = None,
    _: None = Depends(rate_limit)
):
    api_key = os.getenv("NASA_API_KEY")
    if not api_key:
        raise HTTPException(500, "NASA API key not configured")

    params = {"api_key": api_key}
    if date_str:
        params["date"] = date_str

    return httpx.get(
        "https://api.nasa.gov/planetary/apod",
        params=params,
        timeout=10
    ).json()

# =================================================
# ISS
# =================================================

@app.get("/iss")
def iss(
    request: Request,
    _: None = Depends(rate_limit)
):
    data = httpx.get(
        "https://api.wheretheiss.at/v1/satellites/25544",
        timeout=10
    ).json()

    return {
        "timestamp": data["timestamp"],
        "latitude": round(data["latitude"],4),
        "longitude": round(data["longitude"],4),
        "altitude_km": round(data["altitude"],1),
        "altitude_miles": km_to_miles(data["altitude"]),
        "velocity_kmh": round(data["velocity"],1),
        "velocity_mph": km_to_miles(data["velocity"]),
        "visibility": data.get("visibility"),
    }

# =================================================
# Local Run
# =================================================

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
