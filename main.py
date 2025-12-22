from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import httpx
import uvicorn
from datetime import datetime, timezone
import math
import os

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# =================================================
# WEATHER
# =================================================

@app.get("/weather")
def get_weather(city: str = Query(...), state: str = Query(...)):
    geocode_url = "https://nominatim.openstreetmap.org/search"
    geocode_params = {
        "q": f"{city}, {state}, USA",
        "format": "json",
        "limit": 1
    }
    geocode_headers = {"User-Agent": "astra-proxy-weather/1.0"}

    try:
        geo = httpx.get(geocode_url, params=geocode_params, headers=geocode_headers, timeout=10).json()
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))

    if not geo:
        raise HTTPException(status_code=404, detail="Location not found")

    lat, lon = float(geo[0]["lat"]), float(geo[0]["lon"])

    weather_url = "https://api.open-meteo.com/v1/forecast"
    weather_params = {"latitude": lat, "longitude": lon, "current_weather": "true"}

    try:
        weather = httpx.get(weather_url, params=weather_params, timeout=10).json()
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))

    return {
        "location": f"{city}, {state}",
        "latitude": lat,
        "longitude": lon,
        "current_weather": weather["current_weather"]
    }

# =================================================
# MOON
# =================================================

def _moon_phase(dt: datetime):
    ref = datetime(2000, 1, 6, 18, 14, tzinfo=timezone.utc)
    synodic = 29.530588853
    days = (dt - ref).total_seconds() / 86400
    age = days % synodic
    illum = (1 - math.cos(2 * math.pi * age / synodic)) / 2

    if age < 1:
        phase = "New Moon"
    elif age < 6.38:
        phase = "Waxing Crescent"
    elif age < 8.38:
        phase = "First Quarter"
    elif age < 13.76:
        phase = "Waxing Gibbous"
    elif age < 15.76:
        phase = "Full Moon"
    elif age < 21.15:
        phase = "Waning Gibbous"
    elif age < 23.15:
        phase = "Last Quarter"
    else:
        phase = "Waning Crescent"

    return phase, round(age, 2), round(illum, 3)

@app.get("/moon")
def get_moon(date: str | None = None):
    if date:
        try:
            dt = datetime.strptime(date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid date format")
    else:
        dt = datetime.now(timezone.utc)

    phase, age, illum = _moon_phase(dt)

    return {
        "date_utc": dt.strftime("%Y-%m-%d"),
        "phase": phase,
        "age_days": age,
        "illumination": illum
    }

# =================================================
# APOD
# =================================================

@app.get("/apod")
def get_apod(date: str | None = Query(None, description="Optional date YYYY-MM-DD")):
    api_key = os.getenv("MfNS9IUkzNquJBD7wAf4ReKJXcMOZdnfvAEnUXKI
", "DEMO_KEY")

    params = {"api_key": api_key}
    if date:
        params["date"] = date

    try:
        resp = httpx.get(
            "https://api.nasa.gov/planetary/apod",
            params=params,
            timeout=10
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))

    return {
        "date": data.get("date"),
        "title": data.get("title"),
        "explanation": data.get("explanation"),
        "media_type": data.get("media_type"),
        "url": data.get("url")
    }

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
