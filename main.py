from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
import uvicorn

app = FastAPI()

# Optional: Allow all CORS for testing
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

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

@app.get("/weather", response_model=WeatherResponse)
def get_weather(lat: float = Query(...), lon: float = Query(...)):
    # MOCKED example — replace with real API call to Open-Meteo, etc.
    # You must map external data into this schema exactly

    # Example values (sunny, 0°C, light wind)
    return {
        "latitude": lat,
        "longitude": lon,
        "current_weather": {
            "temperature": 0.0,
            "windspeed": 12.3,
            "winddirection": 180.0,
            "weathercode": 0,  # 0 = Clear (per WMO)
            "is_day": True
        }
    }

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
