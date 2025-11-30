from fastapi import FastAPI
import requests
import os

app = FastAPI()

IPGEO_API_KEY = os.getenv("IPGEO_API_KEY", "")
NASA_API_KEY = os.getenv("NASA_API_KEY", "")

# -------------------------------------------------------------------
# WEATHER + ASTRONOMY ENDPOINT
# -------------------------------------------------------------------
@app.get("/weather-astro")
async def get_weather_and_astronomy(lat: float, lon: float):
    """
    Returns weather and astronomy data (Moon position, distance, illumination)
    from Open-Meteo and ipgeolocation.io.
    """
    try:
        # Weather (Open-Meteo)
        weather_url = (
            "https://api.open-meteo.com/v1/forecast?"
            f"latitude={lat}&longitude={lon}&current_weather=true"
        )

        weather_resp = requests.get(weather_url, timeout=10, allow_redirects=False)
        if weather_resp.status_code != 200:
            return {"ok": False, "message": "Weather service unavailable."}

        weather_data = weather_resp.json()

        # Astronomy (Moon) using ipgeolocation.io
        moon_url = (
            "https://api.ipgeolocation.io/astronomy"
            f"?apiKey={IPGEO_API_KEY}&lat={lat}&long={lon}"
        )

        moon_resp = requests.get(moon_url, timeout=10, allow_redirects=False)
        if moon_resp.status_code != 200:
            return {
                "ok": True,
                "weather": weather_data.get("current_weather", {}),
                "moon": {"message": "Moon API unavailable."}
            }

        moon_data = moon_resp.json()

        return {
            "ok": True,
            "weather": weather_data.get("current_weather", {}),
            "moon": moon_data
        }

    except Exception as e:
        return {"ok": False, "message": f"Internal error: {str(e)}"}


# -------------------------------------------------------------------
# ISS LOCATION ENDPOINT
# -------------------------------------------------------------------
@app.get("/iss-now")
async def iss_now():
    """
    Returns the current position of the ISS using open-notify.org.
    """
    try:
        url = "http://api.open-notify.org/iss-now.json"
        resp = requests.get(url, timeout=10, allow_redirects=False)

        if resp.status_code != 200:
            return {"ok": False, "message": "ISS service unavailable."}

        data = resp.json()
        if "iss_position" not in data:
            return {"ok": False, "message": "Malformed ISS response."}

        pos = data["iss_position"]
        return {
            "ok": True,
            "latitude": pos.get("latitude"),
            "longitude": pos.get("longitude")
        }

    except Exception as e:
        return {"ok": False, "message": f"Internal error: {str(e)}"}


# -------------------------------------------------------------------
# GEOCODING ENDPOINT (NEW)
# -------------------------------------------------------------------
@app.get("/geocode")
async def geocode(location: str):
    """
    Look up latitude/longitude for a user-supplied location using
    OpenStreetMap Nominatim with strict rate-limit compliance.
    """
    try:
        url = "https://nominatim.openstreetmap.org/search"
        params = {
            "q": location,
            "format": "json",
            "limit": 1
        }
        headers = {
            "User-Agent": "AstraOneEducationalApp/1.0 (wayne@example.com)"
        }

        response = requests.get(url, params=params, headers=headers,
                                timeout=10, allow_redirects=False)

        if response.status_code != 200:
            return {"ok": False, "message": "Geocoding service unavailable."}

        data = response.json()
        if not data:
            return {"ok": False, "message": "No results found."}

        result = data[0]
        return {
            "ok": True,
            "lat": float(result["lat"]),
            "lon": float(result["lon"]),
            "display_name": result.get("display_name", "")
        }

    except Exception as e:
        return {"ok": False, "message": f"Error: {str(e)}"}


# -------------------------------------------------------------------
# STARTUP
# -------------------------------------------------------------------
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=10000)
