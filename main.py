from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Literal
import httpx
import uvicorn

app = FastAPI()

# Allow all CORS for testing and external API tools like Swagger
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ====== SCHEMAS ======

class CurrentWeather(BaseModel):
    temperature: float
    windspeed: float
    winddirection: float
    weathercode: int
    is_day: bool

class WeatherResponse(BaseModel):
    latitude: float
    longitude: float
    current_weather: CurrentWeather

class GeocodeResponse(BaseModel):
    lat: float
    lon: float
    confidence: Literal["exact", "approximate"]

# ====== /weather ENDPOINT ======

@app.get("/weather", response_model=WeatherResponse)
def get_weather(lat: float = Query(...), lon: float = Query(...)):
    # Replace this static mock with live weather API if needed
    return {
        "latitude": lat,
        "longitude": lon,
        "current_weather": {
            "temperature": 0.0,
            "windspeed": 10.0,
            "winddirection": 270.0,
            "weathercode": 0,
            "is_day": True
        }
    }

# ====== /geocode ENDPOINT ======

@app.get("/geocode", response_model=GeocodeResponse)
def geocode_location(city: str = Query(...), state: str = Query(...)):
    query = f"{city}, {state}, USA"
    url = "https://nominatim.openstreetmap.org/search"
    params = {
        "q": query,
        "format": "json",
        "limit": 1,
    }
    headers = {"User-Agent": "astra-weather-proxy/1.0"}

    try:
        response = httpx.get(url, params=params, headers=headers)
        response.raise_for_status()
        data = response.json()
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Error contacting geocoding service: {str(e)}")

    if not data:
        raise HTTPException(status_code=404, detail="City/state not found")

    return {
        "lat": float(data[0]["lat"]),
        "lon": float(data[0]["lon"]),
        "confidence": "approximate"
    }

# ====== RUN LOCAL ======

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
