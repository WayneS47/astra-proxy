from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
import requests
import os

# ---------------------------------------------------------
# App setup
# ---------------------------------------------------------
app = FastAPI()

# ---------------------------------------------------------
# CORS (open for Astra actions)
# ---------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------
# Environment Variables
# ---------------------------------------------------------
IPGEO_API_KEY = os.getenv("IPGEO_API_KEY")
NASA_API_KEY = os.getenv("NASA_API_KEY")

# ---------------------------------------------------------
# Root / Health
# ---------------------------------------------------------
@app.get("/")
def root():
    return {"message": "Astra Proxy API running"}

# ---------------------------------------------------------
# Geocoding (IPGeolocation)
# ---------------------------------------------------------
@app.get("/geocode")
def geocode(city: str, state: str, country: str = "US"):
    if not IPGEO_API_KEY:
        return Response(
            '{"error":"IPGEO_API_KEY not configured"}',
            status_code=500,
            mimetype="application/json"
        )

    url = (
        "https://api.ipgeolocation.io/geocoding"
        f"?apiKey={IPGEO_API_KEY}"
        f"&city={city}"
        f"&state_prov={state}"
        f"&country={country}"
    )

    try:
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        data = r.json()
    except Exception:
        return Response(
            '{"error":"Geocoding service unavailable"}',
            status_code=502,
            mimetype="application/json"
        )

    if not isinstance(data, list) or len(data) == 0:
        return Response(
            '{"error":"Location not found"}',
            status_code=404,
            mimetype="application/json"
        )

    item = data[0]

    if "latitude" not in item or "longitude" not in item:
        return Response(
            '{"error":"Invalid geocoding response"}',
            status_code=502,
            mimetype="application/json"
        )

    return {
        "lat": float(item["latitude"]),
        "lon": float(item["longitude"]),
        "confidence": "city-state"
    }

# ---------------------------------------------------------
# Weather (Open-Meteo — parsed JSON)
# ---------------------------------------------------------
@app.get("/weather")
def weather(lat: float, lon: float):
    url = (
        "https://api.open-meteo.com/v1/forecast"
        f"?latitude={lat}&longitude={lon}"
        "&current_weather=true"
    )

    r = requests.get(url, timeout=10)
    r.raise_for_status()
    return r.json()

# ---------------------------------------------------------
# Weather RAW (Open-Meteo — text/plain, no interpretation)
# ---------------------------------------------------------
@app.get("/weather-raw")
def weather_raw(lat: float, lon: float):
    url = (
        "https://api.open-meteo.com/v1/forecast"
        f"?latitude={lat}&longitude={lon}"
        "&current_weather=true"
    )

    r = requests.get(url, timeout=10)

    return Response(
        r.text,
        status_code=r.status_code,
        mimetype="text/plain"
    )
