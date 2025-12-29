 """
Astra Astronomy API Backend
Complete FastAPI implementation with 9 endpoints for astronomical data.

Author: Claude (Anthropic)
Version: 2.0
Date: December 27, 2025
Platform: Optimized for Render deployment
"""

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any
import httpx
import json
import os
import numpy as np

# Astronomy libraries
from skyfield.api import load, wgs84, Star
from skyfield import almanac
from skyfield.data import hipparcos

# ============================================================================
# CONFIGURATION
# ============================================================================

app = FastAPI(
    title="Astra Astronomy API",
    description="Real-time astronomical data for the Astra companion",
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS - Allow Custom GPT to call our API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://chat.openai.com", "https://chatgpt.com"],
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
    allow_credentials=True
)

# ============================================================================
# SIMPLE IN-MEMORY CACHE WITH TTL
# ============================================================================

class SimpleCache:
    """Lightweight in-memory cache with TTL support."""
    
    def __init__(self):
        self.cache: Dict[str, str] = {}
        self.expiry: Dict[str, datetime] = {}
    
    def get(self, key: str) -> Optional[str]:
        """Get value from cache if not expired."""
        if key in self.cache and datetime.now() < self.expiry[key]:
            return self.cache[key]
        
        # Clean up expired entry
        if key in self.cache:
            del self.cache[key]
            del self.expiry[key]
        
        return None
    
    def setex(self, key: str, ttl_seconds: int, value: str):
        """Set value with TTL in seconds."""
        self.cache[key] = value
        self.expiry[key] = datetime.now() + timedelta(seconds=ttl_seconds)
    
    def delete(self, key: str):
        """Delete key from cache."""
        if key in self.cache:
            del self.cache[key]
            del self.expiry[key]
    
    def clear(self):
        """Clear all cache entries."""
        self.cache.clear()
        self.expiry.clear()

# Global cache instance
cache = SimpleCache()

# ============================================================================
# SKYFIELD INITIALIZATION (Lazy loaded)
# ============================================================================

_ts = None
_eph = None

def get_skyfield():
    """Lazy load Skyfield data (downloads ephemeris on first use)."""
    global _ts, _eph
    if _ts is None:
        _ts = load.timescale()
    if _eph is None:
        _eph = load('de421.bsp')  # ~10MB download, cached locally
    return _ts, _eph

# ============================================================================
# UNIT CONVERSION FUNCTIONS
# ============================================================================

def celsius_to_fahrenheit(celsius: float) -> int:
    """Convert Celsius to Fahrenheit, rounded to whole number."""
    return round((celsius * 9/5) + 32)

def kph_to_mph(kph: float) -> int:
    """Convert km/h to mph, rounded to whole number."""
    return round(kph * 0.621371)

def km_to_miles(km: float) -> int:
    """Convert kilometers to miles, rounded to whole number."""
    return round(km * 0.621371)

def meters_to_feet(meters: float) -> int:
    """Convert meters to feet, rounded to whole number."""
    return round(meters * 3.28084)

def degrees_to_cardinal(degrees: float) -> str:
    """Convert degrees to cardinal direction (N, NE, E, etc.)."""
    directions = ['N', 'NNE', 'NE', 'ENE', 'E', 'ESE', 'SE', 'SSE',
                  'S', 'SSW', 'SW', 'WSW', 'W', 'WNW', 'NW', 'NNW']
    index = round(degrees / 22.5) % 16
    return directions[index]

# ============================================================================
# WEATHER CODE MAPPING (WMO Standard)
# ============================================================================

WMO_WEATHER_CODES = {
    0: "Clear sky",
    1: "Mainly clear",
    2: "Partly cloudy",
    3: "Overcast",
    45: "Fog",
    48: "Depositing rime fog",
    51: "Light drizzle",
    53: "Moderate drizzle",
    55: "Dense drizzle",
    61: "Slight rain",
    63: "Moderate rain",
    65: "Heavy rain",
    71: "Slight snow",
    73: "Moderate snow",
    75: "Heavy snow",
    80: "Slight rain showers",
    81: "Moderate rain showers",
    85: "Slight snow showers",
    95: "Thunderstorm",
}

def get_weather_description(code: int) -> str:
    """Get weather description from WMO code."""
    return WMO_WEATHER_CODES.get(code, "Unknown")

# ============================================================================
# MOON PHASE MAPPING
# ============================================================================

def get_moon_phase_name(phase_value: float) -> str:
    """
    Convert phase value (0-1) to phase name.
    
    0.00 = New Moon
    0.25 = First Quarter
    0.50 = Full Moon
    0.75 = Last Quarter
    """
    if 0.00 <= phase_value < 0.03:
        return "New Moon"
    elif 0.03 <= phase_value < 0.22:
        return "Waxing Crescent"
    elif 0.22 <= phase_value < 0.28:
        return "First Quarter"
    elif 0.28 <= phase_value < 0.47:
        return "Waxing Gibbous"
    elif 0.47 <= phase_value < 0.53:
        return "Full Moon"
    elif 0.53 <= phase_value < 0.72:
        return "Waning Gibbous"
    elif 0.72 <= phase_value < 0.78:
        return "Last Quarter"
    elif 0.78 <= phase_value <= 1.00:
        return "Waning Crescent"
    else:
        return "Unknown"

# ============================================================================
# HELPER: STANDARD RESPONSE FORMAT
# ============================================================================

def success_response(data: Any, cached: bool = False, **metadata) -> Dict:
    """Create standard success response."""
    return {
        "status": "success",
        "data": data,
        "metadata": {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "cached": cached,
            "api_version": "2.0",
            **metadata
        }
    }

def error_response(code: str, message: str, status_code: int = 500):
    """Create standard error response and raise HTTPException."""
    raise HTTPException(
        status_code=status_code,
        detail={
            "status": "error",
            "error": {
                "code": code,
                "message": message
            },
            "metadata": {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "api_version": "2.0"
            }
        }
    )

# ============================================================================
# API 1: HEALTH CHECK
# ============================================================================

@app.get("/health")
async def health_check():
    """Health check endpoint for monitoring."""
    return {
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "version": "2.0.0",
        "service": "astra-api"
    }

# ============================================================================
# API 2: GET WEATHER
# ============================================================================

@app.get("/v1/weather")
async def get_weather(
    latitude: float = Query(..., ge=-90, le=90, description="Latitude (-90 to 90)"),
    longitude: float = Query(..., ge=-180, le=180, description="Longitude (-180 to 180)")
):
    """
    Get current weather conditions from Open-Meteo API.
    Free, no API key required.
    """
    # Round coordinates for cache key
    lat_key = round(latitude, 2)
    lon_key = round(longitude, 2)
    cache_key = f"weather:{lat_key}:{lon_key}"
    
    # Try cache (5 minute TTL)
    cached_data = cache.get(cache_key)
    if cached_data:
        return success_response(json.loads(cached_data), cached=True)
    
    try:
        # Call Open-Meteo API
        url = "https://api.open-meteo.com/v1/forecast"
        params = {
            "latitude": latitude,
            "longitude": longitude,
            "current": ["temperature_2m", "wind_speed_10m", "wind_direction_10m",
                       "weather_code", "is_day", "cloud_cover"],
            "temperature_unit": "celsius",
            "wind_speed_unit": "kmh",
            "timezone": "UTC"
        }
        
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
            data = response.json()
        
        current = data["current"]
        
        # Extract and convert data
        temp_c = current["temperature_2m"]
        wind_kph = current["wind_speed_10m"]
        wind_dir = current["wind_direction_10m"]
        weather_code = current["weather_code"]
        is_day = bool(current["is_day"])
        cloud_cover = current.get("cloud_cover", 0)
        
        result = {
            "latitude": latitude,
            "longitude": longitude,
            "temperature_f": celsius_to_fahrenheit(temp_c),
            "temperature_c": round(temp_c),
            "wind_speed_mph": kph_to_mph(wind_kph),
            "wind_speed_kph": round(wind_kph),
            "wind_direction_degrees": round(wind_dir),
            "wind_direction_cardinal": degrees_to_cardinal(wind_dir),
            "weather_code": weather_code,
            "weather_description": get_weather_description(weather_code),
            "is_day": is_day,
            "cloud_cover_percent": round(cloud_cover),
            "visibility_miles": 10,  # Default (Open-Meteo doesn't provide)
            "visibility_km": 16,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
        # Cache for 5 minutes
        cache.setex(cache_key, 300, json.dumps(result))
        
        return success_response(result, cached=False)
    
    except httpx.TimeoutException:
        error_response("SERVICE_UNAVAILABLE", 
                      "Weather service temporarily unavailable", 503)
    except httpx.HTTPStatusError as e:
        error_response("SERVICE_ERROR",
                      f"Weather service error: {e.response.status_code}", 503)
    except Exception as e:
        error_response("INTERNAL_ERROR", f"Unexpected error: {str(e)}", 500)

# ============================================================================
# API 3: GET MOON
# ============================================================================

@app.get("/v1/moon")
async def get_moon(
    date: Optional[str] = Query(None, regex=r'^\d{4}-\d{2}-\d{2}$', 
                                description="Date (YYYY-MM-DD), default today"),
    latitude: Optional[float] = Query(None, ge=-90, le=90, 
                                     description="Latitude for rise/set times"),
    longitude: Optional[float] = Query(None, ge=-180, le=180,
                                      description="Longitude for rise/set times")
):
    """
    Calculate moon phase and optional rise/set times using Skyfield.
    Local calculations, no API calls.
    """
    cache_key = f"moon:{date or 'today'}:{latitude}:{longitude}"
    
    # Try cache (24 hour TTL)
    cached_data = cache.get(cache_key)
    if cached_data:
        return success_response(json.loads(cached_data), cached=True)
    
    try:
        ts, eph = get_skyfield()
        
        # Parse date or use today
        if date:
            dt = datetime.strptime(date, '%Y-%m-%d').replace(tzinfo=timezone.utc)
        else:
            dt = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        
        t = ts.utc(dt.year, dt.month, dt.day, 12)  # Noon UTC
        
        # Calculate phase
        earth = eph['earth']
        moon = eph['moon']
        sun = eph['sun']
        
        e = earth.at(t)
        s = e.observe(sun).apparent()
        m = e.observe(moon).apparent()
        
        # Phase angle calculation
        elongation = s.separation_from(m).degrees
        phase_value = (1 - np.cos(np.radians(elongation))) / 2
        
        # Illumination
        illumination = almanac.fraction_illuminated(eph, 'moon', t)
        
        # Age in days (synodic month = 29.53 days)
        age_days = phase_value * 29.53
        
        result = {
            "date": dt.date().isoformat(),
            "phase": round(phase_value, 3),
            "phase_name": get_moon_phase_name(phase_value),
            "illumination_percent": round(illumination * 100, 1),
            "age_days": round(age_days, 1),
            "distance_km": 384400,  # Average
            "distance_miles": 238855,
            "angular_diameter_arcminutes": 31.1
        }
        
        # Add rise/set if location provided
        if latitude is not None and longitude is not None:
            location = wgs84.latlon(latitude, longitude)
            
            t0 = ts.utc(dt.year, dt.month, dt.day, 0, 0)
            t1 = ts.utc(dt.year, dt.month, dt.day, 23, 59)
            
            times, events = almanac.find_discrete(
                t0, t1,
                almanac.risings_and_settings(eph, moon, location)
            )
            
            moonrise = None
            moonset = None
            
            for time, event in zip(times, events):
                if event == 1:  # Rising
                    moonrise = time.utc_strftime('%H:%M')
                elif event == 0:  # Setting
                    moonset = time.utc_strftime('%H:%M')
            
            result["moonrise_utc"] = moonrise
            result["moonset_utc"] = moonset
        
        # Cache for 24 hours
        cache.setex(cache_key, 86400, json.dumps(result))
        
        return success_response(result, cached=False, 
                              location_provided=latitude is not None)
    
    except ValueError as e:
        error_response("INVALID_DATE", str(e), 400)
    except Exception as e:
        error_response("INTERNAL_ERROR", f"Moon calculation error: {str(e)}", 500)

# ============================================================================
# API 4: GET ISS
# ============================================================================

@app.get("/v1/iss")
async def get_iss():
    """
    Get current ISS position from Where The ISS At API.
    Free, no API key required, more reliable than Open Notify.
    """
    cache_key = "iss:current"
    
    # Try cache (1 minute TTL)
    cached_data = cache.get(cache_key)
    if cached_data:
        return success_response(json.loads(cached_data), cached=True)
    
    try:
        # Use wheretheiss.at (more reliable and detailed)
        url = "https://api.wheretheiss.at/v1/satellites/25544"
        
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(url)
            response.raise_for_status()
            data = response.json()
        
        result = {
            "latitude": round(data["latitude"], 4),
            "longitude": round(data["longitude"], 4),
            "altitude_km": round(data["altitude"], 1),
            "altitude_miles": km_to_miles(data["altitude"]),
            "velocity_kmh": round(data["velocity"], 1),
            "velocity_mph": km_to_miles(data["velocity"]),
            "visibility": data.get("visibility"),
            "timestamp": datetime.fromtimestamp(
                data["timestamp"],
                tz=timezone.utc
            ).isoformat()
        }
        
        # Cache for 1 minute
        cache.setex(cache_key, 60, json.dumps(result))
        
        return success_response(result, cached=False, source="Where The ISS At")
    
    except httpx.TimeoutException:
        error_response("SERVICE_UNAVAILABLE",
                      "ISS tracking service temporarily unavailable", 503)
    except httpx.HTTPStatusError as e:
        error_response("SERVICE_ERROR",
                      f"ISS tracking service error: {e.response.status_code}", 503)
    except Exception as e:
        error_response("INTERNAL_ERROR", f"ISS API error: {str(e)}", 500)

# ============================================================================
# API 5: GET APOD (Astronomy Picture of the Day)
# ============================================================================

@app.get("/v1/apod")
async def get_apod(
    date: Optional[str] = Query(None, regex=r'^\d{4}-\d{2}-\d{2}$',
                                description="Date (YYYY-MM-DD), default today")
):
    """
    Get NASA Astronomy Picture of the Day.
    Requires NASA API key in environment.
    """
    cache_key = f"apod:{date or 'today'}"
    
    # Try cache (24 hour TTL)
    cached_data = cache.get(cache_key)
    if cached_data:
        return success_response(json.loads(cached_data), cached=True)
    
    try:
        api_key = os.getenv("NASA_API_KEY", "DEMO_KEY")
        url = "https://api.nasa.gov/planetary/apod"
        params = {"api_key": api_key}
        
        if date:
            # Validate date range
            date_obj = datetime.strptime(date, '%Y-%m-%d').date()
            min_date = datetime(1995, 6, 16).date()
            max_date = datetime.now().date()
            
            if date_obj < min_date:
                error_response("INVALID_DATE",
                             "APOD started on June 16, 1995", 400)
            if date_obj > max_date:
                error_response("INVALID_DATE",
                             "Cannot retrieve APOD for future dates", 400)
            
            params["date"] = date
        
        async with httpx.AsyncClient(timeout=8.0) as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
            data = response.json()
        
        result = {
            "title": data["title"],
            "date": data["date"],
            "explanation": data["explanation"],  # Verbatim as per spec
            "media_type": data["media_type"],
            "url": data["url"],
            "hdurl": data.get("hdurl"),
            "copyright": data.get("copyright")
        }
        
        # Cache for 24 hours
        cache.setex(cache_key, 86400, json.dumps(result))
        
        return success_response(result, cached=False)
    
    except ValueError as e:
        error_response("INVALID_DATE", str(e), 400)
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 429:
            error_response("RATE_LIMITED",
                          "NASA API rate limit exceeded", 429)
        error_response("SERVICE_UNAVAILABLE",
                      "NASA APOD service temporarily unavailable", 503)
    except Exception as e:
        error_response("INTERNAL_ERROR", f"APOD API error: {str(e)}", 500)

# ============================================================================
# API 6: GET ASTEROIDS (JPL Close Approach Data)
# ============================================================================

@app.get("/v1/asteroids")
async def get_asteroids(
    days_ahead: int = Query(30, ge=1, le=365, description="Days to look ahead"),
    max_distance_ld: float = Query(10.0, gt=0, description="Max distance in lunar distances")
):
    """
    Get asteroid close approaches from JPL Close Approach Database.
    Free, no API key required.
    """
    cache_key = f"asteroids:{days_ahead}:{max_distance_ld}"
    
    # Try cache (12 hour TTL)
    cached_data = cache.get(cache_key)
    if cached_data:
        return success_response(json.loads(cached_data), cached=True)
    
    try:
        start_date = datetime.now(timezone.utc)
        end_date = start_date + timedelta(days=days_ahead)
        
        url = "https://ssd-api.jpl.nasa.gov/cad.api"
        params = {
            "date-min": start_date.strftime("%Y-%m-%d"),
            "date-max": end_date.strftime("%Y-%m-%d"),
            "dist-max": f"{max_distance_ld}LD",
            "sort": "dist",
            "fullname": "true"
        }
        
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
            data = response.json()
        
        # Transform JPL format
        approaches = []
        fields = data.get("fields", [])
        rows = data.get("data", [])
        
        if not fields or not rows:
            result = {
                "query": {
                    "days_ahead": days_ahead,
                    "max_distance_ld": max_distance_ld,
                    "date_range": {
                        "start": start_date.date().isoformat(),
                        "end": end_date.date().isoformat()
                    }
                },
                "count": 0,
                "close_approaches": []
            }
            cache.setex(cache_key, 43200, json.dumps(result))
            return success_response(result, cached=False)
        
        # Parse fields
        des_idx = fields.index("des")
        fullname_idx = fields.index("fullname") if "fullname" in fields else None
        cd_idx = fields.index("cd")
        dist_idx = fields.index("dist")
        v_rel_idx = fields.index("v_rel")
        h_idx = fields.index("h") if "h" in fields else None
        
        for row in rows:
            designation = row[des_idx]
            name = row[fullname_idx] if fullname_idx else designation
            close_date = row[cd_idx]
            dist_au = float(row[dist_idx])
            velocity_kms = float(row[v_rel_idx])
            
            # Convert distances
            dist_ld = dist_au * 149597870.7 / 384400
            dist_km = dist_au * 149597870.7
            dist_miles = dist_km * 0.621371
            
            # Convert velocity
            velocity_mph = velocity_kms * 2236.94
            
            # Estimate diameter from absolute magnitude
            diameter_m = None
            if h_idx and row[h_idx]:
                h_mag = float(row[h_idx])
                diameter_km = 1.329 / (0.14 ** 0.5) * (10 ** (-0.2 * h_mag))
                diameter_m = diameter_km * 1000
            
            approach = {
                "designation": designation,
                "name": name,
                "close_approach_date": close_date,
                "distance_ld": round(dist_ld, 2),
                "distance_km": round(dist_km),
                "distance_miles": round(dist_miles),
                "velocity_kms": round(velocity_kms, 1),
                "velocity_mph": round(velocity_mph),
                "diameter_meters": round(diameter_m) if diameter_m else None,
                "diameter_feet": round(diameter_m * 3.28084) if diameter_m else None,
                "is_potentially_hazardous": dist_ld < 0.05
            }
            approaches.append(approach)
        
        result = {
            "query": {
                "days_ahead": days_ahead,
                "max_distance_ld": max_distance_ld,
                "date_range": {
                    "start": start_date.date().isoformat(),
                    "end": end_date.date().isoformat()
                }
            },
            "count": len(approaches),
            "close_approaches": approaches
        }
        
        # Cache for 12 hours
        cache.setex(cache_key, 43200, json.dumps(result))
        
        return success_response(result, cached=False, source="JPL SBDB CAD")
    
    except httpx.TimeoutException:
        error_response("SERVICE_UNAVAILABLE",
                      "JPL asteroid service temporarily unavailable", 503)
    except Exception as e:
        error_response("INTERNAL_ERROR", f"Asteroid API error: {str(e)}", 500)

# ============================================================================
# API 7: GET PLANETARY POSITION
# ============================================================================

# Valid planets for position calculations
VALID_PLANETS = ["Mercury", "Venus", "Mars", "Jupiter", "Saturn", "Uranus", "Neptune"]

@app.get("/v1/planetary-position")
async def get_planetary_position(
    planet: str = Query(..., description="Planet name"),
    date: Optional[str] = Query(None, regex=r'^\d{4}-\d{2}-\d{2}$'),
    time: Optional[str] = Query(None, regex=r'^\d{2}:\d{2}$'),
    latitude: Optional[float] = Query(None, ge=-90, le=90),
    longitude: Optional[float] = Query(None, ge=-180, le=180)
):
    """
    Calculate planetary position using Skyfield.
    Local calculations, no API calls.
    """
    # Validate planet
    planet_cap = planet.capitalize()
    if planet_cap not in VALID_PLANETS:
        error_response("INVALID_PLANET",
                      f"Planet must be one of: {', '.join(VALID_PLANETS)}", 400)
    
    cache_key = f"planet:{planet_cap}:{date or 'now'}:{time or 'now'}:{latitude}:{longitude}"
    
    # Cache TTL: 1 hour without location, 5 min with location
    ttl = 300 if latitude is not None else 3600
    
    cached_data = cache.get(cache_key)
    if cached_data:
        return success_response(json.loads(cached_data), cached=True)
    
    try:
        ts, eph = get_skyfield()
        
        # Parse date/time
        if date and time:
            dt = datetime.strptime(f"{date} {time}", '%Y-%m-%d %H:%M')
            dt = dt.replace(tzinfo=timezone.utc)
        elif date:
            dt = datetime.strptime(date, '%Y-%m-%d')
            dt = dt.replace(hour=21, minute=0, tzinfo=timezone.utc)
        else:
            dt = datetime.now(timezone.utc)
        
        t = ts.utc(dt.year, dt.month, dt.day, dt.hour, dt.minute)
        
        # Get bodies
        earth = eph['earth']
        
        # Map planet names to Skyfield identifiers
        planet_map = {
            "Mercury": "mercury",
            "Venus": "venus", 
            "Mars": "mars",
            "Jupiter": "jupiter barycenter",
            "Saturn": "saturn barycenter",
            "Uranus": "uranus barycenter",
            "Neptune": "neptune barycenter"
        }
        
        planet_obj = eph[planet_map[planet_cap]]
        
        # Calculate position
        astrometric = earth.at(t).observe(planet_obj)
        ra, dec, distance = astrometric.radec()
        
        # Simple magnitude estimate
        base_mags = {
            "Mercury": -0.6, "Venus": -4.4, "Mars": -1.5,
            "Jupiter": -9.4, "Saturn": -8.9,
            "Uranus": -7.2, "Neptune": -6.9
        }
        magnitude = base_mags.get(planet_cap, 0) + 5 * np.log10(distance.au)
        
        result = {
            "planet": planet_cap,
            "date": dt.date().isoformat(),
            "time_utc": dt.strftime('%H:%M'),
            "position": {
                "right_ascension": str(ra),
                "right_ascension_degrees": round(ra._degrees, 2),
                "declination": str(dec),
                "declination_degrees": round(dec.degrees, 2)
            },
            "physical": {
                "distance_au": round(distance.au, 3),
                "distance_million_km": round(distance.km / 1_000_000, 1),
                "distance_million_miles": round(distance.km * 0.621371 / 1_000_000, 1),
                "light_minutes": round(distance.au * 8.317, 1),
                "magnitude": round(magnitude, 1)
            }
        }
        
        # Add observability if location provided
        if latitude is not None and longitude is not None:
            location = earth + wgs84.latlon(latitude, longitude)
            topocentric = location.at(t).observe(planet_obj)
            alt, az, _ = topocentric.apparent().altaz()
            
            def altitude_desc(altitude):
                if altitude < 0:
                    return "Below horizon"
                elif altitude < 10:
                    return "Very low, poor viewing"
                elif altitude < 30:
                    return "Low, atmospheric interference"
                elif altitude < 60:
                    return "Well placed for viewing"
                else:
                    return "Excellent altitude"
            
            result["observability"] = {
                "is_visible": bool(alt.degrees > 0),
                "altitude_degrees": round(float(alt.degrees), 1),
                "altitude_description": altitude_desc(alt.degrees),
                "azimuth_degrees": round(float(az.degrees), 1),
                "azimuth_cardinal": degrees_to_cardinal(az.degrees)
            }
        
        cache.setex(cache_key, ttl, json.dumps(result))
        
        return success_response(result, cached=False,
                              location_provided=latitude is not None)
    
    except Exception as e:
        error_response("INTERNAL_ERROR", f"Planetary calculation error: {str(e)}", 500)

# ============================================================================
# API 8: GET CONSTELLATIONS
# ============================================================================

# Abbreviated constellation data (full list would have all 88)
CONSTELLATION_DATA = {
    "Ori": {"name": "Orion", "genitive": "Orionis",
            "stars": [("Betelgeuse", 27989), ("Rigel", 24436)]},
    "UMa": {"name": "Ursa Major", "genitive": "Ursae Majoris",
            "stars": [("Dubhe", 54061), ("Merak", 53910)]},
    "Tau": {"name": "Taurus", "genitive": "Tauri",
            "stars": [("Aldebaran", 21421)]},
    "Gem": {"name": "Gemini", "genitive": "Geminorum",
            "stars": [("Pollux", 37826), ("Castor", 36850)]},
    "Leo": {"name": "Leo", "genitive": "Leonis",
            "stars": [("Regulus", 49669)]},
    "Vir": {"name": "Virgo", "genitive": "Virginis",
            "stars": [("Spica", 65474)]},
    "Sco": {"name": "Scorpius", "genitive": "Scorpii",
            "stars": [("Antares", 80763)]},
    "Sgr": {"name": "Sagittarius", "genitive": "Sagittarii",
            "stars": [("Kaus Australis", 90185)]},
    "Aql": {"name": "Aquila", "genitive": "Aquilae",
            "stars": [("Altair", 97649)]},
    "Cyg": {"name": "Cygnus", "genitive": "Cygni",
            "stars": [("Deneb", 102098)]},
    "Peg": {"name": "Pegasus", "genitive": "Pegasi",
            "stars": [("Enif", 107315)]},
    "And": {"name": "Andromeda", "genitive": "Andromedae",
            "stars": [("Alpheratz", 677)]},
}

@app.get("/v1/constellations")
async def get_constellations(
    latitude: float = Query(..., ge=-90, le=90),
    longitude: float = Query(..., ge=-180, le=180),
    date: Optional[str] = Query(None, regex=r'^\d{4}-\d{2}-\d{2}$'),
    time: Optional[str] = Query(None, regex=r'^\d{2}:\d{2}$'),
    min_altitude: float = Query(20.0, ge=0, le=90, description="Minimum altitude in degrees")
):
    """
    Calculate visible constellations from location using Skyfield.
    """
    cache_key = f"constellations:{latitude}:{longitude}:{date or 'now'}:{time or 'now'}:{min_altitude}"
    
    # Try cache (30 minute TTL)
    cached_data = cache.get(cache_key)
    if cached_data:
        return success_response(json.loads(cached_data), cached=True)
    
    try:
        ts, eph = get_skyfield()
        
        # Parse date/time
        if date and time:
            dt = datetime.strptime(f"{date} {time}", '%Y-%m-%d %H:%M')
            dt = dt.replace(tzinfo=timezone.utc)
        elif date:
            dt = datetime.strptime(date, '%Y-%m-%d')
            dt = dt.replace(hour=21, minute=0, tzinfo=timezone.utc)
        else:
            dt = datetime.now(timezone.utc)
        
        t = ts.utc(dt.year, dt.month, dt.day, dt.hour, dt.minute)
        
        # Observer location
        earth = eph['earth']
        location = earth + wgs84.latlon(latitude, longitude)
        observer = location.at(t)
        
        visible = []
        
        # Load Hipparcos catalog (cached after first load)
        with load.open(hipparcos.URL) as f:
            stars = hipparcos.load_dataframe(f)
        
        for abbr, data in CONSTELLATION_DATA.items():
            if not data["stars"]:
                continue
            
            # Use brightest star as reference
            star_name, hip_id = data["stars"][0]
            
            try:
                star_data = stars.loc[hip_id]
                star = Star.from_dataframe(star_data)
                
                # Calculate position
                astrometric = observer.observe(star)
                alt, az, _ = astrometric.apparent().altaz()
                
                # Check if above minimum altitude
                if alt.degrees >= min_altitude:
                    # Get notable stars
                    notable = []
                    for s_name, s_hip in data["stars"][:3]:
                        s_data = stars.loc[s_hip]
                        notable.append({
                            "name": s_name,
                            "magnitude": round(s_data['magnitude'], 1)
                        })
                    
                    def visibility_desc(altitude):
                        if altitude >= 60:
                            return "excellent"
                        elif altitude >= 45:
                            return "very good"
                        elif altitude >= 30:
                            return "good"
                        else:
                            return "fair"
                    
                    visible.append({
                        "name": data["name"],
                        "abbreviation": abbr,
                        "genitive": data["genitive"],
                        "altitude_degrees": round(alt.degrees, 1),
                        "azimuth_degrees": round(az.degrees, 1),
                        "azimuth_cardinal": degrees_to_cardinal(az.degrees),
                        "visibility": visibility_desc(alt.degrees),
                        "notable_stars": notable
                    })
            except KeyError:
                continue  # Star not in catalog
        
        # Sort by altitude (highest first)
        visible.sort(key=lambda x: x["altitude_degrees"], reverse=True)
        
        result = {
            "date": dt.date().isoformat(),
            "time_utc": dt.strftime('%H:%M'),
            "location": {
                "latitude": latitude,
                "longitude": longitude
            },
            "visible_constellations": visible,
            "total_visible": len(visible)
        }
        
        # Cache for 30 minutes
        cache.setex(cache_key, 1800, json.dumps(result))
        
        return success_response(result, cached=False, min_altitude_filter=min_altitude)
    
    except Exception as e:
        error_response("INTERNAL_ERROR", f"Constellation calculation error: {str(e)}", 500)

# ============================================================================
# API 9: GET EARTH IMAGE (NASA EPIC)
# ============================================================================

@app.get("/v1/earth-image")
async def get_earth_image(
    date: Optional[str] = Query(None, regex=r'^\d{4}-\d{2}-\d{2}$',
                                description="Date (YYYY-MM-DD), default latest"),
    image_type: str = Query("natural", regex='^(natural|enhanced)$',
                           description="Image type: natural or enhanced")
):
    """
    Get Earth images from NASA EPIC (Earth Polychromatic Imaging Camera).
    Requires NASA API key in environment.
    """
    cache_key = f"earth:{date or 'latest'}:{image_type}"
    
    # Try cache (2 hour TTL)
    cached_data = cache.get(cache_key)
    if cached_data:
        return success_response(json.loads(cached_data), cached=True)
    
    try:
        api_key = os.getenv("NASA_API_KEY", "DEMO_KEY")
        
        # Build URL
        if date:
            url = f"https://api.nasa.gov/EPIC/api/{image_type}/date/{date}"
        else:
            url = f"https://api.nasa.gov/EPIC/api/{image_type}"
        
        params = {"api_key": api_key}
        
        async with httpx.AsyncClient(timeout=8.0) as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
            data = response.json()
        
        if not data:
            error_response("NO_IMAGES_AVAILABLE",
                          "No images available for specified date", 404)
        
        # Transform response
        images = []
        for img in data:
            img_date = img["date"].split()[0]
            date_parts = img_date.split("-")
            year, month, day = date_parts[0], date_parts[1], date_parts[2]
            
            base_url = f"https://epic.gsfc.nasa.gov/archive/{image_type}/{year}/{month}/{day}"
            
            images.append({
                "identifier": img["image"],
                "caption": img.get("caption", "This image was taken by NASA's EPIC camera"),
                "image_url": f"{base_url}/png/{img['image']}.png",
                "thumbnail_url": f"{base_url}/thumbs/{img['image']}.jpg",
                "date_time": img["date"],
                "centroid_coordinates": {
                    "lat": img["centroid_coordinates"]["lat"],
                    "lon": img["centroid_coordinates"]["lon"]
                },
                "sun_j2000_position": img.get("sun_j2000_position", {}),
                "dscovr_j2000_position": img.get("dscovr_j2000_position", {})
            })
        
        result = {
            "date": images[0]["date_time"].split()[0] if images else date,
            "image_type": image_type,
            "images": images,
            "images_available": len(images)
        }
        
        # Cache for 2 hours
        cache.setex(cache_key, 7200, json.dumps(result))
        
        return success_response(result, cached=False, source="NASA EPIC")
    
    except ValueError as e:
        error_response("NO_IMAGES_AVAILABLE", str(e), 404)
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 429:
            error_response("RATE_LIMITED", "NASA API rate limit exceeded", 429)
        error_response("SERVICE_UNAVAILABLE",
                      "NASA EPIC service temporarily unavailable", 503)
    except Exception as e:
        error_response("INTERNAL_ERROR", f"Earth image API error: {str(e)}", 500)

# ============================================================================
# API 10: GEOCODE (Internal Helper)
# ============================================================================

@app.get("/v1/geocode")
async def geocode(
    city: str = Query(..., min_length=1, description="City name"),
    state: Optional[str] = Query(None, description="State code (US) or name"),
    country: str = Query("US", description="Country code (2-letter)")
):
    """
    Geocode city/state to coordinates using Nominatim (OpenStreetMap).
    Free, no API key required.
    """
    cache_key = f"geocode:{city}:{state}:{country}"
    
    # Try cache (30 day TTL)
    cached_data = cache.get(cache_key)
    if cached_data:
        return success_response(json.loads(cached_data), cached=True)
    
    try:
        url = "https://nominatim.openstreetmap.org/search"
        
        # Build query
        query_parts = [city]
        if state:
            query_parts.append(state)
        query_parts.append(country)
        query = ", ".join(query_parts)
        
        params = {
            "q": query,
            "format": "json",
            "limit": 1,
            "addressdetails": 1
        }
        
        headers = {
            "User-Agent": "AstraAstronomyApp/2.0"
        }
        
        async with httpx.AsyncClient(timeout=4.0) as client:
            response = await client.get(url, params=params, headers=headers)
            response.raise_for_status()
            results = response.json()
        
        if not results:
            error_response("LOCATION_NOT_FOUND",
                          f"Location not found: {query}", 404)
        
        result = results[0]
        address = result.get("address", {})
        
        data = {
            "city": address.get("city") or address.get("town") or address.get("village") or city,
            "state": address.get("state"),
            "country": address.get("country"),
            "country_code": address.get("country_code", "").upper(),
            "latitude": float(result["lat"]),
            "longitude": float(result["lon"]),
            "display_name": result["display_name"]
        }
        
        # Cache for 30 days (coordinates don't change)
        cache.setex(cache_key, 2592000, json.dumps(data))
        
        return success_response(data, cached=False)
    
    except httpx.TimeoutException:
        error_response("SERVICE_UNAVAILABLE",
                      "Geocoding service temporarily unavailable", 503)
    except Exception as e:
        error_response("INTERNAL_ERROR", f"Geocoding error: {str(e)}", 500)

# ============================================================================
# ROOT ENDPOINT
# ============================================================================

@app.get("/")
async def root():
    """API information and documentation links."""
    return {
        "service": "Astra Astronomy API",
        "version": "2.0.0",
        "description": "Real-time astronomical data backend for Astra companion",
        "documentation": "/docs",
        "health": "/health",
        "endpoints": {
            "weather": "/v1/weather",
            "moon": "/v1/moon",
            "iss": "/v1/iss",
            "apod": "/v1/apod",
            "asteroids": "/v1/asteroids",
            "planetary_position": "/v1/planetary-position",
            "constellations": "/v1/constellations",
            "earth_image": "/v1/earth-image",
            "geocode": "/v1/geocode"
        }
    }

# ============================================================================
# APPLICATION STARTUP
# ============================================================================

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=port,
        log_level="info"
    )
