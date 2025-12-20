from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import httpx
import uvicorn
from datetime import datetime, timezone
import math
import os

app = FastAPI()

# CORS (safe for Actions)
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
        geo_resp = httpx.get(
            geocode_url,
            params=geocode_params,
            headers=geocode_headers,
            timeout=10
        )
        geo_resp.raise_for_status()
        geo_data = geo_resp.json()
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Geocoding failed: {str(e)}")

    if not geo_data:
        raise HTTPException(status_code=404, detail="Location not found")

    lat = float(geo_data[0]["lat"])
    lon = float(geo_data[0]["lon"])

    weather_url = "https://api.open-meteo.com/v1/forecast"
    weather_params = {
        "latitude": lat,
        "longitude": lon,
        "current_weather": "true"
    }

    try:
        weather_resp = httpx.get(
            weather_url,
            params=weather_params,
            timeout=10
        )
        weather_resp.raise_for_status()
        weather_data = weather_resp.json()
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Weather service failed: {str(e)}")

    return {
        "location": f"{city}, {state}",
        "latitude": lat,
        "longitude": lon,
        "current_weather": weather_data.get("current_weather")
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

    return phase, round(age, 2), round(
