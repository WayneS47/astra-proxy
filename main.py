from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import httpx
import uvicorn

app = FastAPI()

# CORS (safe for Actions)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# =========================
# GET /weather
# =========================
# Accepts: city, state
# Performs: geocoding + weather lookup internally
# Astra makes ONE call only
# =========================

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

# ===== Local run =====
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
