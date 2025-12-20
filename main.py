from fastapi import FastAPI, Query
from pydantic import BaseModel
from typing import Optional
import requests

app = FastAPI(
    title="Astra Weather Actions",
    version="1.0.0",
    description="Model-safe weather schema for Astra. All orchestration happens server-side. Weather and Moon data returned as opaque text payload.",
    servers=[{"url": "https://astra-proxy.onrender.com"}],
)

# ----------------------------
# Request schemas
# ----------------------------

class LatLonRequest(BaseModel):
    lat: float
    lon: float

# ----------------------------
# /geocodeLocation
# ----------------------------

@app.get("/geocodeLocation", operation_id="geocodeLocation", summary="Convert place name to coordinates")
def geocode_location(city: str = Query(...), state: str = Query(...), country: Optional[str] = "US"):
    response = requests.get(
        "https://nominatim.openstreetmap.org/search",
        params={
            "q": f"{city}, {state}, {country}",
            "format": "json",
            "limit": 1
        },
        headers={"User-Agent": "astra-bot"}
    )
    data = response.json()
    if not data:
        return {}

    result = {
        "lat": float(data[0]["lat"]),
        "lon": float(data[0]["lon"]),
        "confidence": "approximate"
    }
    return result

# ----------------------------
# /getWeatherRaw
# ----------------------------

@app.post("/getWeatherRaw", operation_id="getWeatherRaw", summary="Retrieve raw weather JSON as an opaque string")
def get_weather_raw(body: LatLonRequest):
    response = requests.get(
        "https://api.open-meteo.com/v1/forecast",
        params={
            "latitude": body.lat,
            "longitude": body.lon,
            "current_weather": True
        }
    )
    return response.json()

# ----------------------------
# /getMoon
# ----------------------------

@app.post("/getMoon", operation_id="getMoon", summary="Retrieve current moon data")
def get_moon(body: LatLonRequest):
    response = requests.get(
        "https://api.astronomyapi.com/api/v2/bodies/positions/moon",
        params={
            "latitude": body.lat,
            "longitude": body.lon,
            "from_date": "2025-12-20",  # Optional: dynamic date logic
            "to_date": "2025-12-20",
            "elevation": 0
        },
        headers={
            "Authorization": "Basic YOUR_API_KEY_HERE"
        }
    )
    return response.json()
