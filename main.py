from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import httpx
import uvicorn
from datetime import datetime, timezone
import math

app = FastAPI()

# CORS (safe for Actions)
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
# Astra calls ONE endpoint for weather
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
        weather_resp = httpx.get(
            weather_url,
            params=weather_params,
            timeout=10.0
        )
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
# Accepts: optional date (YYYY-MM-DD). Defaults to today (UTC).
# Returns: deterministic moon phase approximation
# Notes:
# - No external API calls.
# - Phase is global; does not require location.
# =================================================

def _parse_date_utc(date_str: str | None) -> datetime:
    if not date_str:
        return datetime.now(timezone.utc)
    try:
        # Interpret provided date as midnight UTC
        return datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")

def _moon_phase_approx(dt: datetime):
    """
    Deterministic approximation using a synodic month length.
    Output:
      - phase_name (string)
      - age_days (float)
      - illumination (float 0..1)
    """
    # Reference new moon (UTC): 2000-01-06 18:14
    ref = datetime(2000, 1, 6, 18, 14, tzinfo=timezone.utc)

    # Synodic month length (days)
    synodic_month = 29.530588853

    delta_days = (dt - ref).total_seconds() / 86400.0
    age = delta_days % synodic_month  # days since new moon in current cycle

    # Illumination fraction approximation (0..1)
    # 0 at new moon, 1 at full moon
    phase_angle = 2.0 * math.pi * (age / synodic_month)
    illumination = (1.0 - math.cos(phase_angle)) / 2.0

    # Name buckets by age
    # (simple, readable categories)
    if age < 1.0:
        name = "New Moon"
    elif age < 6.382:
        name = "Waxing Crescent"
    elif age < 8.382:
        name = "First Quarter"
    elif age < 13.765:
        name = "Waxing Gibbous"
    elif age < 15.765:
        name = "Full Moon"
    elif age < 21.147:
        name = "Waning Gibbous"
    elif age < 23.147:
        name = "Last Quarter"
    else:
        name = "Waning Crescent"

    return name, age, illumination

@app.get("/moon")
def get_moon(
    date: str | None = Query(None, description="Optional date in YYYY-MM-DD. Defaults to today (UTC).")
):
    dt = _parse_date_utc(date)
    phase_name, age_days, illumination = _moon_phase_approx(dt)

    return {
        "date_utc": dt.strftime("%Y-%m-%d"),
        "phase": phase_name,
        "age_days": round(age_days, 2),
        "illumination": round(illumination, 3)
    }


# ===== Local run =====
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
