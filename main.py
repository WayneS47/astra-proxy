import os
import requests
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

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
IPGEO_API_KEY = os.getenv("IPGEO_API_KEY")   # ← Correct variable name
NASA_API_KEY = os.getenv("NASA_API_KEY")

# ---------------------------------------------------------
# Root
# ---------------------------------------------------------
@app.get("/")
def root():
    return {"message": "Astra One API running"}

# ---------------------------------------------------------
# Health
# ---------------------------------------------------------
@app.get("/health")
def health():
    return {"status": "ok"}

# ---------------------------------------------------------
# Weather (Open-Meteo)
# ---------------------------------------------------------
@app.get("/weather")
def weather(lat: float, lon: float):
    url = (
        "https://api.open-meteo.com/v1/forecast"
        f"?latitude={lat}&longitude={lon}"
        "&current_weather=true"
    )
    r = requests.get(url, timeout=10)
    return r.json()

# ---------------------------------------------------------
# Moon (IPGeolocation - requires paid Astronomy upgrade)
# ---------------------------------------------------------
@app.get("/moon")
def moon(lat: float, lon: float):
    if not IPGEO_API_KEY:
        return {"error": "Missing IPGEO_API_KEY"}

    url = (
        "https://api.ipgeolocation.io/astronomy"
        f"?apiKey={IPGEO_API_KEY}"
        f"&lat={lat}&long={lon}"
    )

    r = requests.get(url, timeout=10)
    return r.json()

# ---------------------------------------------------------
# ISS Location
# ---------------------------------------------------------
@app.get("/iss")
def iss_location():
    url = "http://api.open-notify.org/iss-now.json"
    r = requests.get(url, timeout=10)
    return r.json()

# ---------------------------------------------------------
# NASA APOD
# ---------------------------------------------------------
@app.get("/apod")
def apod():
    if not NASA_API_KEY:
        return {"error": "Missing NASA_API_KEY"}

    url = (
        "https://api.nasa.gov/planetary/apod"
        f"?api_key={NASA_API_KEY}"
    )
    r = requests.get(url, timeout=10)
    return r.json()

# ---------------------------------------------------------
# Sky Photo (Static Rule)
# ---------------------------------------------------------
@app.get("/sky-photo")
def sky_photo():
    return {
        "photo_url":
        "https://upload.wikimedia.org/wikipedia/commons/0/0c/ESO_-_Milky_Way.jpg"
    }
