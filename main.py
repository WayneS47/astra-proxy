from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Literal
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
    weathercode: int  # WMO Code (0 = Clear)
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

# ===== /weather ENDPOINT =====

@app.get("/weather", response_model=WeatherResponse)
def get_weather(lat: float = Query(...), lon: float = Query(...)):
    # Replace this mock with real API call logic if needed
    return {
        "latitude": lat,
        "longitude": lon,
        "current_weather": {
            "temperature": 0.0,
            "windspeed": 10.0,
            "winddirection": 270.0,
            "weathercode": 0,  # 0 = Clear
            "is_day": True
        }
    }

# ===== /geocode ENDPOINT =====

@app.get("/geocode", response_model=GeocodeResponse)
def geocode_location(
    city: str = Query(...),
    state: str = Query(...)
):
    # Optional: Add lookup table or real API here.
    # For demo, return static known location for Franklin, TN
    if city.lower() == "franklin" and state.lower() == "tn":
        return {
            "lat": 35.93,
            "lon": -86.82,
            "confidence": "exact"
        }
    else:
        # Minimal fallback for unsupported inputs
        raise HTTPException(status_code=404, detail="City/state not found")

# ===== RUN LOCAL (OPTIONAL) =====

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
