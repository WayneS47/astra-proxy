"""
Astra Backend - Main Application
FastAPI server providing 9 astronomy APIs
"""

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from datetime import datetime, timezone
from typing import Optional
import httpx
import os

# Initialize FastAPI app
app = FastAPI(
    title="Astra Astronomy API",
    version="2.0",
    description="Backend API for Astra astronomy companion"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API Keys (from environment variables)
NASA_API_KEY = os.getenv("NASA_API_KEY", "DEMO_KEY")

# Constants
GOES16_LATEST_IMAGE = "https://cdn.star.nesdis.noaa.gov/GOES16/ABI/FD/GEOCOLOR/latest.jpg"

# Health check
@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "version": "2.0"
    }

# API 1: Weather
@app.get("/v1/weather")
async def get_weather(
    latitude: float = Query(..., ge=-90, le=90),
    longitude: float = Query(..., ge=-180, le=180)
):
    """Get current weather conditions for stargazing"""
    try:
        url = f"https://api.open-meteo.com/v1/forecast"
        params = {
            "latitude": latitude,
            "longitude": longitude,
            "current_weather": true,
            "temperature_unit": "fahrenheit",
            "windspeed_unit": "mph"
        }
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
            data = response.json()
            
            return {
                "status": "ok",
                "latitude": latitude,
                "longitude": longitude,
                "current_weather": data.get("current_weather", {}),
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# API 2: Moon Phase
@app.get("/v1/moon")
async def get_moon_phase(
    date: Optional[str] = None,
    latitude: Optional[float] = None,
    longitude: Optional[float] = None
):
    """Get moon phase and rise/set times"""
    # Implementation depends on your moon calculation library
    # This is a placeholder structure
    return {
        "status": "ok",
        "phase": "WAXING_CRESCENT",
        "illumination": 15.3,
        "age_days": 3.2,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }

# API 3: ISS Position
@app.get("/v1/iss")
async def get_iss_position():
    """Get current ISS position"""
    try:
        url = "http://api.open-notify.org/iss-now.json"
        
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(url)
            response.raise_for_status()
            data = response.json()
            
            return {
                "status": "ok",
                "iss_position": data.get("iss_position", {}),
                "timestamp": data.get("timestamp"),
                "message": data.get("message")
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# API 4: APOD (Astronomy Picture of the Day)
@app.get("/v1/apod")
async def get_apod(date: Optional[str] = None):
    """Get NASA Astronomy Picture of the Day"""
    try:
        url = "https://api.nasa.gov/planetary/apod"
        params = {
            "api_key": NASA_API_KEY
        }
        if date:
            params["date"] = date
            
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
            data = response.json()
            
            return {
                "status": "ok",
                "title": data.get("title"),
                "date": data.get("date"),
                "explanation": data.get("explanation"),
                "url": data.get("url"),
                "hdurl": data.get("hdurl"),
                "media_type": data.get("media_type"),
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# API 5: Near-Earth Asteroids
@app.get("/v1/asteroids")
async def get_asteroids(
    days_ahead: int = Query(30, ge=1, le=90),
    max_distance_ld: float = Query(20.0, ge=0.1)
):
    """Get upcoming near-Earth asteroid close approaches"""
    try:
        today = datetime.now().strftime("%Y-%m-%d")
        url = f"https://api.nasa.gov/neo/rest/v1/feed"
        params = {
            "start_date": today,
            "api_key": NASA_API_KEY
        }
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
            data = response.json()
            
            return {
                "status": "ok",
                "element_count": data.get("element_count", 0),
                "near_earth_objects": data.get("near_earth_objects", {}),
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# API 6: Planetary Positions
@app.get("/v1/planetary-position")
async def get_planetary_position(
    planet: str = Query(...),
    date: Optional[str] = None,
    time: Optional[str] = None,
    latitude: Optional[float] = None,
    longitude: Optional[float] = None
):
    """Calculate planetary position"""
    # Implementation depends on your astronomy calculation library
    # This is a placeholder structure
    return {
        "status": "ok",
        "planet": planet,
        "right_ascension": 123.45,
        "declination": 23.45,
        "distance_au": 5.2,
        "magnitude": -2.5,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }

# API 7: Visible Constellations
@app.get("/v1/constellations")
async def get_constellations(
    latitude: float = Query(..., ge=-90, le=90),
    longitude: float = Query(..., ge=-180, le=180),
    date: Optional[str] = None,
    time: Optional[str] = None,
    min_altitude: float = Query(20.0, ge=0, le=90)
):
    """Get visible constellations from location"""
    # Implementation depends on your astronomy calculation library
    # This is a placeholder structure
    return {
        "status": "ok",
        "location": {"latitude": latitude, "longitude": longitude},
        "constellations": [],
        "timestamp": datetime.now(timezone.utc).isoformat()
    }

# API 8: Earth Images (UPDATED - NOAA GOES-16)
@app.get("/v1/earth-image")
async def get_earth_image():
    """
    Get near-real-time Earth image from NOAA GOES-16 weather satellite.
    
    Replaces unreliable NASA EPIC with operational weather satellite imagery.
    Updates every 10-15 minutes automatically.
    """
    
    response_data = {
        "status": "ok",
        "source": "NOAA GOES-16",
        "description": "Near-real-time full-disk Earth image",
        "image_url": GOES16_LATEST_IMAGE,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "update_frequency": "10-15 minutes"
    }
    
    return JSONResponse(
        content=response_data,
        headers={
            # Cache for 10 minutes (aligns with GOES update cadence)
            "Cache-Control": "public, max-age=600"
        }
    )

# API 9: Geocoding
@app.get("/v1/geocode")
async def geocode_location(city: str = Query(...)):
    """Convert city name to coordinates"""
    try:
        url = "https://geocoding-api.open-meteo.com/v1/search"
        params = {
            "name": city,
            "count": 1,
            "language": "en",
            "format": "json"
        }
        
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
            data = response.json()
            
            if not data.get("results"):
                raise HTTPException(status_code=404, detail="Location not found")
            
            result = data["results"][0]
            return {
                "status": "ok",
                "latitude": result.get("latitude"),
                "longitude": result.get("longitude"),
                "name": result.get("name"),
                "country": result.get("country"),
                "timezone": result.get("timezone"),
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Root endpoint
@app.get("/")
async def root():
    """Root endpoint - API information"""
    return {
        "name": "Astra Astronomy API",
        "version": "2.0",
        "status": "operational",
        "endpoints": {
            "health": "/health",
            "weather": "/v1/weather",
            "moon": "/v1/moon",
            "iss": "/v1/iss",
            "apod": "/v1/apod",
            "asteroids": "/v1/asteroids",
            "planetary_position": "/v1/planetary-position",
            "constellations": "/v1/constellations",
            "earth_image": "/v1/earth-image",
            "geocode": "/v1/geocode"
        },
        "documentation": "/docs"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
