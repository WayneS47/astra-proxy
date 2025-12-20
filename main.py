from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import httpx
import uvicorn
import os
from datetime import datetime, date
import math

app = FastAPI()

# =================================================
# CORS (safe for Actions)
# =================================================
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# =================================================
# GET /weather
# Accepts: city, state
# Performs: geocoding + weather lookup internally
# =================================================

@app.get("/weather")
def get_weather(
    city: str = Query(..., description="City name"),
    state: str = Query(..., description="State abbreviation or name")
):
    # ---- Geocode (Nominatim) ----
    geocode_url = "https://nominatim.openstreetmap.org/search"
    geocode_params = {
        "q": f"{city}, {state}, USA",
        "format": "json",
        "limit": 1
    }
    geocode_headers = {
        "User-Agent": "astra-proxy-weather/1.0"
    }

    try:
        geo_resp = httpx.get(
            geocode_url,
            params=geocode_params,
            headers=geocode_headers,
            timeout=10.0
        )
        geo_resp.raise_for_status()
        geo_data = geo_resp.json()
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Geocoding failed: {str(e)}")

    if not geo_data:
        raise HTTPException(status_code=404, detail="Location not found")

    lat = float(geo_data[0]["lat"])
    lon = float(geo_data[0]["lon"])

    # ---- Weather (Open-Meteo) ----
    weather_url = "https://api.open-meteo.com/v1/forecast"
    weather_params = {
        "latitude": lat,
        "longitude": lon,
        "current_weather": "true"
    }

    try:
        weather_resp = httpx.get(weather_url, params=weather_params, timeout=10.0)
        weather_resp.raise_for_status()
        weather_data = weather_resp.json()
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Weather service failed: {str(e)}")

    if "current_weather" not in weather_data:
        raise HTTPException(status_code=502, detail="Weather data unavailable")

    return {
        "location": f"{city}, {state}",
        "latitude": lat,
        "longitude": lon,
        "current_weather": weather_data["current_weather"]
    }

# =================================================
# GET /moon
# Accepts: optional date (YYYY-MM-DD)
# Returns: phase, illumination, age
# =================================================

@app.get("/moon")
def get_moon(phase_date: str | None = Query(
    default=None,
    description="Date in YYYY-MM-DD format (optional)"
)):
    if phase_date:
        try:
            target_date = datetime.strptime(phase_date, "%Y-%m-%d").date()
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid date format")
    else:
        target_date = date.today()

    known_new_moon = date(2000, 1, 6)
    days_since = (target_date - known_new_moon).days
    synodic_month = 29.53058867

    age = days_since % synodic_month
    illumination = (1 - math.cos(2 * math.pi * age / synodic_month)) / 2 * 100

    if age < 1:
        phase = "New Moon"
    elif age < 7:
        phase = "Waxing Crescent"
    elif age < 8:
        phase = "First Quarter"
    elif age < 14:
        phase = "Waxing Gibbous"
    elif age < 15:
        phase = "Full Moon"
    elif age < 22:
        phase = "Waning Gibbous"
    elif age < 23:
        phase = "Last Quarter"
    else:
        phase = "Waning Crescent"

    return {
        "date": target_date.isoformat(),
        "phase": phase,
        "illumination_percent": round(illumination, 1),
        "age_days": round(age, 1)
    }

# =================================================
# GET /apod
# Accepts: optional date (YYYY-MM-DD)
# Returns: NASA Astronomy Picture of the Day
# =================================================

@app.get("/apod")
def get_apod(apod_date: str | None = Query(
    default=None,
    description="Date in YYYY-MM-DD format (optional)"
)):
    api_key = os.getenv("NASA_API_KEY", "DEMO_KEY")

    params = {
        "api_key": api_key
    }

    if apod_date:
        params["date"] = apod_date

    url = "https://api.nasa.gov/planetary/apod"

    try:
        resp = httpx.get(url, params=params, timeout=10.0)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"NASA APOD failed: {str(e)}")

    return {
        "date": data.get("date"),
        "title": data.get("title"),
        "explanation": data.get("explanation"),
        "media_type": data.get("media_type"),
        "url": data.get("url"),
        "hdurl": data.get("hdurl")
    }

# =================================================
# Local run
# =================================================

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
