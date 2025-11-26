from fastapi import FastAPI
import httpx

app = FastAPI()

@app.get("/weather-astro")
async def get_weather_and_astronomy(lat: float, lon: float):
    async with httpx.AsyncClient(timeout=10.0) as client:
        weather_url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current_weather=true"
        moon_url = f"https://api.ipgeolocation.io/astronomy?apiKey=8cba696ee6c045d49e8d3367fedea2aa&lat={lat}&long={lon}"

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

    fallback = {
        "ok": False,
        "weather": weather,
        "moon": moon,
    }

    return fallback
