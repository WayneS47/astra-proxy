from fastapi import FastAPI
import httpx
import os

app = FastAPI()

@app.get("/weather-astro")
async def get_weather_and_astronomy(lat: float, lon: float):
    async with httpx.AsyncClient(timeout=10.0) as client:

        # Load API key from environment variable
        api_key = os.getenv("IPGEO_API_KEY")

        # Weather API
        weather_url = (
            f"https://api.open-meteo.com/v1/forecast?"
            f"latitude={lat}&longitude={lon}&current_weather=true"
        )

        # Astronomy API (IPGeolocation)
        moon_url = (
            f"https://api.ipgeolocation.io/astronomy?"
            f"apiKey={api_key}&lat={lat}&long={lon}"
        )

        weather = None
        moon = None

        # ---- Weather call ----
        try:
            w = await client.get(weather_url)
            if w.status_code == 200:
                weather = w.json()
        except Exception:
            pass

        # ---- Moon/Astronomy call ----
        try:
            m = await client.get(moon_url)
            if m.status_code == 200:
                moon = m.json()
        except Exception:
            pass

        # ---- Level 3 Summaries ----

        # Weather summary
        weather_summary = None
        try:
            if weather and "current_weather" in weather:
                cw = weather["current_weather"]
                temp = cw.get("temperature")
                wind = cw.get("windspeed")
                weather_summary = (
                    f"The temperature is {temp}°C with wind at {wind} km/h."
                )
        except Exception:
            pass

        # Moon summary
        moon_summary = None
        try:
            if moon:
                phase = moon.get("moon_phase")
                illum = moon.get("moon_illumination_percentage")
                moon_summary = (
                    f"The moon phase is {phase} with {illum}% illumination."
                )
        except Exception:
            pass

        return {
            "ok": True,
            "raw": {
                "weather": weather,
                "moon": moon
            },
            "summary": {
                "weather_summary": weather_summary,
                "moon_summary": moon_summary
            }
        }
