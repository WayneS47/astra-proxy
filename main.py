from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
import requests
import os

# ---------------------------------------------------------
# App
# ---------------------------------------------------------
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
NASA_API_KEY = os.getenv("NASA_API_KEY")

# ---------------------------------------------------------
# Root / Health
# ---------------------------------------------------------
@app.get("/")
def root():
    return {"message": "Astra Proxy API running"}

# ---------------------------------------------------------
# Weather (Open-Meteo — RAW, Astra-compatible)
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

    return Response(
        r.text,
        status_code=r.status_code,
        mimetype="text/plain"
    )
