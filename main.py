from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import httpx
import uvicorn
import os
from datetime import date, datetime
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
# Helpers
# =================================================

def km_to_miles(km: float) -> float:
    return km * 0.621371

def c_to_f(c: float) -> float:
    return (c * 9.0 / 5.0) + 32.0

def kmh_to_mph(kmh: float) -> float:
    return kmh * 0.621371

def deg_to_compass_16(deg: float) -> str:
    # 16-point compass
    directions = [
        "N", "NNE", "NE", "ENE",
        "E", "ESE", "SE", "SSE",
        "S", "SSW", "SW", "WSW",
        "W", "WNW", "NW", "NNW"
    ]
    deg = deg % 360.0
    idx = int((deg + 11.25) // 22.5) % 16
    return directions[idx]

def weathercode_to_sky(weathercode: int) -> str:
    # Open-Meteo WMO codes (simplified, readable mapping)
    if weathercode == 0:
        return "Clear"
    if weathercode in (1, 2, 3):
        return "Partly Cloudy" if weathercode in (1, 2) else "Cloudy"
    if weathercode in (45, 48):
        return "Fog"
    if weathercode in (51, 53, 55):
        return "Drizzle"
    if weathercode in (56, 57):
        return "Freezing Drizzle"
    if weathercode in (61, 63, 65):
        return "Rain"
    if weathercode in (66, 67):
        return "Freezing Rain"
    if weathercode in (71, 73, 75):
        return "Snow"
    if weathercode == 77:
        return "Snow Grains"
    if weathercode in (80, 81, 82):
        return "Rain Showers"
    if weathercode in (85, 86):
        return "Snow Showers"
    if weathercode in (95, 96, 99):
        return "Thunderstorm"
    return "Unknown"

def moon_info(target: date):
    """
    Returns:
      phase_name: str
      illumination_percent: float
      age_days: float
    This is an approximation sufficient for consumer-facing "moon phase" responses.
    """
    # Reference new moon: 2000-01-06 18:14 UTC (approx), common epoch
    known_new_moon = datetime(2000, 1, 6, 18, 14, 0)
    target_dt = datetime(target.year, target.month, target.day, 0, 0, 0)

    synodic_month = 29.53058867  # days
    days_since = (target_dt - known_new_moon).total_seconds() / 86400.0
    age = days_since % synodic_month

    # Illumination approximation (0..1)
    # Phase angle
    phase = (age / synodic_month) * 2.0 * math.pi
    illumination = (1.0 - math.cos(phase)) / 2.0  # 0=new, 1=full
    illumination_percent = illumination * 100.0

    # Phase name (8 major phases)
    # Boundaries in days
    if age < 1.84566:
        phase_name = "New Moon"
    elif age < 5.53699:
        phase_name = "Waxing Crescent"
    elif age < 9.22831:
        phase_name = "First Quarter"
    elif age < 12.91963:
        phase_name = "Waxing Gibbous"
    elif age < 16.61096:
        phase_name = "Full Moon"
    elif age < 20.30228:
        phase_name = "Waning Gibbous"
    elif age < 23.99361:
        phase_name = "Last Quarter"
    elif age < 27.68493:
        phase_name = "Waning Crescent"
    else:
        phase_name = "New Moon"

    return phase_name, round(illumination_percent, 1), round(age, 1)

# =================================================
# GET /weather
# Accepts: city, state
# Performs: geocoding + weather lookup internally
# Astra calls ONE endpoint only
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
    geocode_headers = {"User-Agent": "astra-proxy-weather/1.0"}

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

    cw = weather_data["current_weather"]
    temp_c = float(cw.get("temperature"))
    wind_kmh = float(cw.get("windspeed"))
    wind_deg = float(cw.get("winddirection"))
    is_day = bool(int(cw.get("is_day", 0)))
    code = int(cw.get("weathercode", -1))

    return {
        "location": f"{city}, {state}",
        "latitude": lat,
        "longitude": lon,
        "temperature_c": temp_c,
        "temperature_f": round(c_to_f(temp_c), 1),
        "wind_kmh": wind_kmh,
        "wind_mph": round(kmh_to_mph(wind_kmh), 1),
        "wind_degrees": wind_deg,
        "wind_direction": deg_to_compass_16(wind_deg),
        "sky": weathercode_to_sky(code),
        "daylight": is_day
    }

# =================================================
# GET /moon
# Optional: date=YYYY-MM-DD
# =================================================

@app.get("/moon")
def get_moon(moon_date: str | None = Query(default=None, description="Date in YYYY-MM-DD format (optional)")):
    try:
        target = date.today() if not moon_date else datetime.strptime(moon_date, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD.")

    phase_name, illumination_percent, age_days = moon_info(target)

    return {
        "date": target.isoformat(),
        "phase": phase_name,
        "illumination_percent": illumination_percent,
        "age_days": age_days
    }

# =================================================
# GET /apod
# Optional: date=YYYY-MM-DD
# =================================================

@app.get("/apod")
def get_apod(apod_date: str | None = Query(default=None, description="Date in YYYY-MM-DD format (optional)")):
    if apod_date:
        try:
            datetime.strptime(apod_date, "%Y-%m-%d")
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD.")

    api_key = os.getenv("NASA_API_KEY", "DEMO_KEY")
    params = {"api_key": api_key}
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
# GET /iss
# Current ISS position and telemetry
# =================================================

@app.get("/iss")
def get_iss():
    # Reliable HTTPS source for ISS telemetry
    iss_url = "https://api.wheretheiss.at/v1/satellites/25544"

    try:
        resp = httpx.get(iss_url, timeout=10.0)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"ISS service failed: {str(e)}")

    # wheretheiss.at returns altitude (km), velocity (km/h)
    lat = float(data.get("latitude"))
    lon = float(data.get("longitude"))
    alt_km = float(data.get("altitude"))
    vel_kmh = float(data.get("velocity"))
    ts = int(data.get("timestamp"))

    return {
        "timestamp": ts,
        "latitude": lat,
        "longitude": lon,
        "altitude_km": round(alt_km, 1),
        "altitude_miles": round(km_to_miles(alt_km), 1),
        "velocity_kmh": round(vel_kmh, 1),
        "velocity_mph": round(kmh_to_mph(vel_kmh), 1),
        "visibility": data.get("visibility")
    }

# ===== Local run =====
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
