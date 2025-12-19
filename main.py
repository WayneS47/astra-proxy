from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Literal
import httpx
import uvicorn

app = FastAPI()

# Optional: Allow all CORS (for testing and external calls)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ===== WEATHER SCHEMA =====

class CurrentWeather(BaseModel):
    temperature: float
    windspeed: float
    winddirection: float
    weathercode: int  # WMO Code (0 = Clear, etc.)
    is_day: bool

class WeatherResponse(BaseModel):
    latitude: float
    longitude: float
    current_weather: CurrentWeather

# ===== GEOCODE SCHEMA =====

class GeocodeResponse(BaseModel):
    lat: float
    lon: float
    confidence: Literal["exact", "approximate"]

# ===== /weather ENDPOINT (LIVE) =====

@app.get("/weather", response_model=WeatherResponse)
def get_weather(lat: float = Query(...), lon: float = Query(...)):
    try:
        url = "https://api.open-meteo.com/v1/forecast"
        params = {
            "latitude": lat,
            "longitude": lon,
            "current_weather": "true"
        }
        response = httpx.get(url, params=params, timeout=10.0)
        response.raise_for_status()
        data = response.json()
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Weather service error: {str(e)}")

    if "current_weather" not in data:
        raise HTTPException(status_code=404, detail="No current weather data available.")

    return {
        "latitude": data["latitude"],
        "longitude": data["longitude"],
        "current_weather": data["current_weather"]
    }

# ===== /geocode ENDPOINT (STATIC DEMO) =====

@app.get("/geocode", response_model=GeocodeResponse)
def geocode_location(
    city: str = Query(...),
    state: str = Query(...)
):
    # Example: support only Franklin, TN
    if city.lower() == "franklin" and state.lower() == "tn":
        return {
            "lat": 35.93,
            "lon": -86.82,
            "confidence": "exact"
        }
    else:
        raise HTTPException(status_code=404, detail="City/state not found")

# ===== LOCAL RUN =====

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
