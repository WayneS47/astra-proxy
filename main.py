from fastapi import FastAPI
import httpx

app = FastAPI()

@app.get("/weather-astro")
async def get_weather_and_astronomy(lat: float, lon: float):
    async with httpx.AsyncClient(timeout=10.0) as client:
        weather_url = (
            f"https://api.open-meteo.com/v1/forecast?"
            f"latitude={lat}&longitude={lon}&current_weather=true"
        )
        moon_url = (
            f"https://api.ipgeolocation.io/astronomy?"
            f"apiKey=8cba696ee6c045d49e8d3367fedea2aa&lat={lat}&long={lon}"
        )

        weather = None
        moon = None

        try:
            w = await client.get(weather_url)
            if w.status_code == 200:
                weather = w.json()
        except Exception:
            pass

        try:
            m = await client.get(moon_url)
            if m.status_code == 200:
                moon = m.json()
        except Exception:
            pass

    # ----- Level 3 Summaries Added -----

    weather_summary = None
    if weather and "current_weather" in weather:
        cw = weather["current_weather"]
        temp = cw.get("temperature")
        wind = cw.get("windspeed")
        code = cw.get("weathercode")

        weather_summary = (
            f"Current temperature is {temp}°C with wind at {wind} km/h. "
            f"Weather code: {code}."
        )

    moon_summary = None
    if moon:
        phase = moon.get("moon_phase")
        illumination = moon.get("moon_illumination_percentage")
        moon_summary = (
            f"The moon phase is {phase} with {illumination}% illumination."
        )

    result = {
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

    return result
