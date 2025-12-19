from fastapi import FastAPI
from fastapi.responses import Response
from fastapi.middleware.cors import CORSMiddleware
import requests
import os

# ---------------------------------------------------------
# App initialization
# ---------------------------------------------------------

app = FastAPI()

# ---------------------------------------------------------
# CORS (required for GPT Actions / browser calls)
# ---------------------------------------------------------

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------
# Environment variables
# ---------------------------------------------------------

IPGEO_API_KEY = os.getenv("IPGEO_API_KEY")
NASA_API_KEY = os.getenv("NASA_API_KEY")

# ---------------------------------------------------------
# Root / Health
# ---------------------------------------------------------

@app.get("/")
def root():
    return {"message": "Astra Proxy API running"}

@app.get("/health")
def health():
    return {"status": "ok"}

# ---------------------------------------------------------
# Weather (Parsed JSON – normal use)
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
# Weather (RAW – GPT Action passthrough)
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
        content=r.text,
        status_code=r.status_code,
        media_type="text/plain"
    )
