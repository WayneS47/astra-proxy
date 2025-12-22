from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import httpx
import uvicorn
import os
from datetime import datetime, date, timezone
import math

app = FastAPI(title="Astra Proxy")

# -------------------------------------------------
# CORS (safe for GPT Actions)
# -------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# =================================================
# Helper functions
# =================================================

def c_to_f(c: float) -> float:
    return (c * 9 / 5) + 32

def kmh_to_mph(kmh: float) -> float:
    return kmh * 0.621371

def km_to_miles(km: float) -> float:
    return km * 0.621371

def deg_to_compass_16(deg: float) -> str:
    directions = [
        "N", "NNE", "NE", "ENE",
        "E", "ESE", "SE", "SSE",
        "S", "SSW", "SW", "WSW",
        "W", "WNW", "NW", "NNW"
    ]
    deg = deg % 360
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
    if code in (51, 53, 55):
        return "Drizzle"
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
    state: str = Query(..., description="State abbreviation or name")
):
    geocode_url = "https://nominatim.openstreetmap.org/search"
    geo_params = {
        "q": f"{city}, {state}, USA",
        "format": "json",
        "limit": 1
    }
    geo_headers = {"User-Agent": "astra-proxy-weather/1.0"}

    try:
        geo_resp = httpx.get(geocode_url, params=geo_params, headers=geo_headers, timeout=10)
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

    cw = data["current_weather"]

    return {
        "location": f"{city}, {state}",
        "temperature_f": round(c_to_f(cw["temperature"]), 1),
        "temperature_c": round(cw["temperature"], 1),
        "wind_mph": round(kmh_to_mph(cw["windspeed"]), 1),
        "wind_kmh": round(cw["windspeed"], 1),
        "wind_direction": deg_to_compass_16(cw["winddirection"]),
        "sky": weathercode_to_sky(cw["weathercode"]),
        "daylight": bool(cw["is_day"])
    }

# =================================================
# MOON
# =================================================

def moon_info(target: date):
    ref = datetime(2000, 1, 6, 18, 14, tzinfo=timezone.utc)
    target_dt = datetime(target.year, target.month, target.day, tzinfo=timezone.utc)
    synodic = 29.53058867

    days = (target_dt - ref).total_seconds() / 86400
    age = days % synodic
    phase_angle = (age / synodic) * 2 * math.pi
    illumination = (1 - math.cos(phase_angle)) / 2 * 100

    if age < 1.84566:
        phase = "New Moon"
    elif age < 5.53699:
        phase = "Waxing Crescent"
    elif age < 9.22831:
        phase = "First Quarter"
    elif age < 12.91963:
        phase = "Waxing Gibbous"
    elif age < 16.61096:
        phase = "Full Moon"
    elif age < 20.30228:
        phase = "Waning Gibbous"
    elif age < 23.99361:
        phase = "Last Quarter"
    else:
        phase = "Waning Crescent"

    return phase, round(illumination, 1), round(age, 1)

@app.get("/moon")
def get_moon(date_str: str | None = Query(None, description="YYYY-MM-DD (optional)")):
    try:
        target = date.today() if not date_str else datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format")

    phase, illumination, age = moon_info(target)

    return {
        "date": target.isoformat(),
        "phase": phase,
        "illumination_percent": illumination,
        "age_days": age
    }

# =================================================
# APOD (NASA)
# =================================================

@app.get("/apod")
def get_apod(date_str: str | None = Query(None, description="YYYY-MM-DD (optional)")):
    if date_str:
        try:
            datetime.strptime(date_str, "%Y-%m-%d")
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid date format")

    api_key = os.getenv("NASA_API_KEY")
    if not api_key:
        raise HTTPException(
            status_code=500,
            detail="NASA API key not configured on server"
        )

    params = {"api_key": api_key}
    if date_str:
        params["date"] = date_str

    try:
        resp = httpx.get("https://api.nasa.gov/planetary/apod", params=params, timeout=10)
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
# ISS
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
# Local run
# =================================================

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
