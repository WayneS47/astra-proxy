# main.py — Astra Proxy (APOD + Eclipses Only)

import os
from datetime import date
from typing import Any, Dict, List, Optional

import httpx
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware


# -----------------------------------------------------------
# FastAPI App Setup
# -----------------------------------------------------------

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Astra will call from anywhere
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# -----------------------------------------------------------
# NASA APOD Setup
# -----------------------------------------------------------

NASA_API_KEY = os.getenv("NASA_API_KEY", "DEMO_KEY")
NASA_BASE_URL = "https://api.nasa.gov"


async def fetch_json(client: httpx.AsyncClient, url: str, params: Dict[str, Any]) -> Any:
    """Small helper to call NASA APIs safely."""
    try:
        resp = await client.get(url, params=params, timeout=20.0)
    except httpx.RequestError as exc:
        raise HTTPException(status_code=502, detail=f"NASA API request failed: {exc}") from exc

    if resp.status_code != 200:
        raise HTTPException(
            status_code=resp.status_code,
            detail=f"NASA API error: {resp.text}",
        )

    try:
        return resp.json()
    except ValueError as exc:
        raise HTTPException(status_code=502, detail="Invalid JSON from NASA API") from exc


# -----------------------------------------------------------
# ECLIPSE DATA (to be filled by you from NASA tables)
# -----------------------------------------------------------

SOLAR_ECLIPSES: List[Dict[str, Any]] = [
    # Example structure—replace with real NASA-derived data:
    # {
    #     "date": "2026-08-12",
    #     "type": "Total",
    #     "visibility_text": "Visible from Greenland, Iceland, and parts of Europe.",
    # }
]

LUNAR_ECLIPSES: List[Dict[str, Any]] = [
    # Example structure—replace with real NASA-derived data:
]


# -----------------------------------------------------------
# ECLIPSE VISIBILITY HELPERS
# -----------------------------------------------------------

def classify_region(lat: float, lon: float) -> str:
    """Map lat/lon to a simple region name."""
    if 5 <= lat <= 75 and -170 <= lon <= -30:
        return "north america"
    if -60 <= lat <= 15 and -90 <= lon <= -30:
        return "south america"
    if 35 <= lat <= 70 and -10 <= lon <= 40:
        return "europe"
    if -35 <= lat <= 35 and -20 <= lon <= 55:
        return "africa"
    if 5 <= lat <= 70 and 55 <= lon <= 180:
        return "asia"
    if -50 <= lat <= -10 and 110 <= lon <= 180:
        return "australia"
    return "other"


def is_visible_in_tennessee(visibility_text: str) -> bool:
    """Simple check: Tennessee = North America (USA)."""
    txt = visibility_text.lower()
    return (
        "north america" in txt
        or "united states" in txt
        or "usa" in txt
    )


def is_visible_in_region(visibility_text: str, region: str) -> bool:
    """Simple region substring match."""
    return region.lower() in visibility_text.lower()


def _next_eclipse(today: date, eclipses: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Return the next eclipse after today."""
    upcoming = []
    for e in eclipses:
        try:
            d = date.fromisoformat(e["date"])
        except Exception:
            continue
        if d >= today:
            upcoming.append({**e, "date_obj": d})

    if not upcoming:
        return None

    nxt = min(upcoming, key=lambda e: e["date_obj"])
    nxt["date"] = nxt["date_obj"].isoformat()
    nxt.pop("date_obj", None)
    return nxt


def build_eclipse_section(today: date, lat: float, lon: float) -> Dict[str, Any]:
    """Build the eclipse portion of the /astro-events JSON output."""
    user_region = classify_region(lat, lon)

    next_solar = _next_eclipse(today, SOLAR_ECLIPSES)
    next_lunar = _next_eclipse(today, LUNAR_ECLIPSES)

    def decorate(e: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        if e is None:
            return None
        vis_text = e.get("visibility_text", "")
        return {
            "date": e.get("date"),
            "type": e.get("type"),
            "visibility_text": vis_text,
            "visible_from_tennessee": is_visible_in_tennessee(vis_text),
            "visible_from_user_region": is_visible_in_region(vis_text, user_region),
        }

    return {
        "user_region": user_region,
        "next_solar_eclipse": decorate(next_solar),
        "next_lunar_eclipse": decorate(next_lunar),
    }


def build_event_summary(today: date, eclipse_info: Dict[str, Any]) -> str:
    """Short human-readable summary."""
    parts = []

    s = eclipse_info.get("next_solar_eclipse")
    if s:
        tn = "will" if s.get("visible_from_tennessee") else "will not"
        parts.append(
            f"The next solar eclipse is a {s.get('type','?')} eclipse on {s.get('date','?')}. "
            f"It {tn} be visible from Tennessee."
        )
    else:
        parts.append("There is no future solar eclipse in the current list.")

    l = eclipse_info.get("next_lunar_eclipse")
    if l:
        tn = "will" if l.get("visible_from_tennessee") else "may not"
        parts.append(
            f"The next lunar eclipse is a {l.get('type','?')} eclipse on {l.get('date','?')}. "
            f"It {tn} be visible from Tennessee."
        )
    else:
        parts.append("There is no future lunar eclipse in the current list.")

    return " ".join(parts)


# -----------------------------------------------------------
# /astro-events  (APOD + Eclipses Only)
# -----------------------------------------------------------

@app.get("/astro-events")
async def astro_events(
    lat: float = Query(..., description="Latitude of the observer"),
    lon: float = Query(..., description="Longitude of the observer"),
) -> Dict[str, Any]:
    """Return APOD + eclipse info."""
    if NASA_API_KEY is None:
        raise HTTPException(
            status_code=500,
            detail="NASA_API_KEY is not configured on the server.",
        )

    today = date.today()

    # Fetch APOD
    async with httpx.AsyncClient() as client:
        apod_params = {
            "api_key": NASA_API_KEY,
            "date": today.isoformat(),
        }
        apod_url = f"{NASA_BASE_URL}/planetary/apod"
        apod = await fetch_json(client, apod_url, apod_params)

    # Eclipse calculations
    eclipse_info = build_eclipse_section(today=today, lat=lat, lon=lon)

    # Summary
    event_summary = build_event_summary(today=today, eclipse_info=eclipse_info)

    return {
        "location": {"lat": lat, "lon": lon},
        "date_generated": today.isoformat(),
        "apod": apod,
        "eclipses": eclipse_info,
        "event_summary": event_summary,
    }


# -----------------------------------------------------------
# YOUR EXISTING WEATHER ENDPOINT (preserved exactly)
# -----------------------------------------------------------

@app.get("/weather-astro")
async def weather_astro(
    lat: float = Query(...),
    lon: float = Query(...),
):
    """Existing /weather-astro endpoint left intact."""
    open_meteo_url = (
        f"https://api.open-meteo.com/v1/forecast?"
        f"latitude={lat}&longitude={lon}&current_weather=true"
    )
    ipgeo_url = (
        f"https://api.ipgeolocation.io/astronomy?"
        f"apiKey={os.getenv('IPGEO_API_KEY')}&lat={lat}&long={lon}"
    )

    async with httpx.AsyncClient() as client:
        w = await client.get(open_meteo_url)
        m = await client.get(ipgeo_url)

    return {
        "weather": w.json(),
        "moon": m.json(),
    }
