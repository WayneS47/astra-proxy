from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Literal
import httpx
import uvicorn
from fastapi.responses import PlainTextResponse
import json

app = FastAPI()

# CORS settings (for Swagger, browser-based tools, etc.)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ===== SCHEMAS =====

class GeocodeResponse(BaseModel):
    lat: float
    lon: float
    confidence: Literal["exact", "approximate"]

# ===== /weather-raw ENDPOINT (OPAQUE WEATHER PAYLOAD) =====

@app.get("/weather-raw", response_class=PlainTextResponse)
def get_weather_raw(lat: float = Query(...), lon: float = Query(...)):
    try:
        url = "https://api.open-meteo.com/v1/forecast"
        params = {
            "latitude": lat,
            "longitude": lon,
            "current_weather": "true"
        }
        response = httpx.get(url, params=params, timeout=10.0)
        response.raise_for_status()
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Weather service error: {str(e)}")

    # Return opaque raw JSON text
    return response.text

# ===== /geocode ENDPOINT (LIVE FROM NOMINATIM) =====

@app.get("/geocode", response_model=GeocodeResponse)
def geocode_location(city: str = Query(...), state: str = Query(...)):
    query = f"{city}, {state}, USA"
    url = "https://nominatim.openstreetmap.org/search"
    params = {
        "q": query,
        "format": "json",
        "limit": 1
    }
    headers = {"User-Agent": "astra-weather-proxy/1.0"}

    try:
        response = httpx.get(url, params=params, headers=headers, timeout=10.0)
        response.raise_for_status()
        data = response.json()
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Geocoding service error: {str(e)}")

    if not data:
        raise HTTPException(status_code=404, detail="City/state not found")

    return {
        "lat": float(data[0]["lat"]),
        "lon": float(data[0]["lon"]),
        "confidence": "approximate"
    }

# ===== LOCAL RUN =====

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
