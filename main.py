from fastapi import FastAPI
import os
import httpx
from bs4 import BeautifulSoup
import pytz
import requests

app = FastAPI()


# ------------------------------------------------------------
# Weather Endpoint
# ------------------------------------------------------------

@app.get("/weather")
async def get_weather(lat: float, lon: float):
    """Return current weather."""
    url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current_weather=true"
    async with httpx.AsyncClient() as client:
        r = await client.get(url, timeout=10.0)
        data = r.json()
    return data


# ------------------------------------------------------------
# Moon Endpoint
# ------------------------------------------------------------

@app.get("/moon")
async def get_moon(lat: float, lon: float):
    """Return basic moon info from IPGeolocation."""
    api_key = os.getenv("IPGEO_KEY")
    url = f"https://api.ipgeolocation.io/astronomy?apiKey={api_key}&lat={lat}&long={lon}"

    async with httpx.AsyncClient() as client:
        r = await client.get(url, timeout=10.0)
        data = r.json()

    return data


# ------------------------------------------------------------
# ISS Tracker
# ------------------------------------------------------------

@app.get("/iss")
async def get_iss_position():
    """Return current ISS position."""
    url = "http://api.open-notify.org/iss-now.json"

    async with httpx.AsyncClient() as client:
        r = await client.get(url, timeout=10.0)
        data = r.json()

    return {
        "timestamp": data.get("timestamp"),
        "latitude": data.get("iss_position", {}).get("latitude"),
        "longitude": data.get("iss_position", {}).get("longitude")
    }


# ------------------------------------------------------------
# NASA APOD Helper
# ------------------------------------------------------------

async def fetch_apod():
    """Fetch NASA Astronomy Picture of the Day."""
    api_key = os.getenv("NASA_KEY", "DEMO_KEY")
    url = f"https://api.nasa.gov/planetary/apod?api_key={api_key}"

    try:
        async with httpx.AsyncClient() as client:
            r = await client.get(url, timeout=10.0)
            data = r.json()
        return {
            "title": data.get("title"),
            "description": data.get("explanation"),
            "image_url": data.get("url"),
            "date": data.get("date")
        }
    except:
        return {
            "title": None,
            "description": None,
            "image_url": None,
            "date": None,
            "error": "NASA APOD request failed."
        }


# ------------------------------------------------------------
# sky-photo Endpoint (NASA APOD)
# ------------------------------------------------------------

@app.get("/sky-photo")
async def sky_photo():
    """Return today's NASA sky photo info."""
    return await fetch_apod()


# ------------------------------------------------------------
# Health Check
# ------------------------------------------------------------

@app.get("/health")
async def health():
    return {"status": "ok"}


# ------------------------------------------------------------
# Run locally (ignored by Render)
# ------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", 8000)))
