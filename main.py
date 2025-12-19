from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import requests
import os

app = FastAPI()

# ---------------------------------------------------------
# CORS
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

# ---------------------------------------------------------
# Helpers
# ---------------------------------------------------------
def success(endpoint: str, data: dict):
    return {
        "ok": True,
        "service": "astra-proxy",
        "endpoint": endpoint,
        "data": data
    }

def failure(endpoint: str, error_type: str, message: str):
    return {
        "ok": False,
        "service": "astra-proxy",
        "endpoint": endpoint,
        "error": {
            "type": error_type,
            "message": message
        }
    }

# ---------------------------------------------------------
# Health Check (Astra Test 1)
# ---------------------------------------------------------
@app.get("/health")
def health():
    return success(
        endpoint="/health",
        data={"status": "running"}
    )

# ---------------------------------------------------------
# Root
# ---------------------------------------------------------
@app.get("/")
def root():
    return success(
        endpoint="/",
        data={"message": "Astra Proxy API running"}
    )

# ---------------------------------------------------------
# Geocode (City + State → Lat/Lon)
# ---------------------------------------------------------
@app.get("/geocode")
def geocode(city: str, state: str, country: str = "US"):
    if not IPGEO_API_KEY:
        return failure(
            "/geocode",
            "config_error",
            "IPGEO_API_KEY not configured"
        )

    url = "https://api.ipgeolocation.io/geocoding"
    params = {
        "apiKey": IPGEO_API_KEY,
        "city": city,
        "state_prov": state,
        "country": country
    }

    try:
        r = requests.get(url, params=params, timeout=10)
        r.raise_for_status()
        payload = r.json()

        if not payload or "latitude" not in payload[0]:
            return failure(
                "/geocode",
                "not_found",
                "Location not found"
            )

        location = payload[0]

        return success(
            "/geocode",
            {
                "latitude": float(location["latitude"]),
                "longitude": float(location["longitude"]),
                "city": location.get("city"),
                "state": location.get("state_prov"),
                "country": location.get("country_name")
            }
        )

    except Exception as e:
        return failure(
            "/geocode",
            "upstream_error",
            str(e)
        )

# ---------------------------------------------------------
# Weather (Open-Meteo — Parsed JSON, Astra-safe)
# ---------------------------------------------------------
@app.get("/weather")
def weather(lat: float, lon: float):
    url = (
        "https://api.open-meteo.com/v1/forecast"
        f"?latitude={lat}&longitude={lon}"
        "&current_weather=true"
    )

    try:
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        data = r.json()

        return success(
            "/weather",
            data
        )

    except Exception as e:
        return failure(
            "/weather",
            "upstream_error",
            str(e)
        )
