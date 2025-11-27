# main.py — Astra Proxy (APOD + Eclipses Only, 20+20 NASA GSFC)

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
# ECLIPSE DATA — 20 Solar + 20 Lunar (NASA GSFC)
# -----------------------------------------------------------

SOLAR_ECLIPSES: List[Dict[str, Any]] = [
    {"date": "2025-09-21", "calendar_date": "2025 Sep 21", "type": "Partial",
     "visibility_text": "s Pacific, N.Z., Antarctica", "source": "NASA GSFC"},
    {"date": "2026-02-17", "calendar_date": "2026 Feb 17", "type": "Annular",
     "visibility_text": "s Argentina & Chile, s Africa, Antarctica", "source": "NASA GSFC"},
    {"date": "2026-08-12", "calendar_date": "2026 Aug 12", "type": "Total",
     "visibility_text": "n N. America, w Africa, Europe", "source": "NASA GSFC"},
    {"date": "2027-02-06", "calendar_date": "2027 Feb 06", "type": "Annular",
     "visibility_text": "S. America, Antarctica, w & s Africa", "source": "NASA GSFC"},
    {"date": "2027-08-02", "calendar_date": "2027 Aug 02", "type": "Total",
     "visibility_text": "Africa, Europe, Mid East, w & s Asia", "source": "NASA GSFC"},
    {"date": "2028-01-26", "calendar_date": "2028 Jan 26", "type": "Annular",
     "visibility_text": "e N. America, C. & S. America, w Europe, nw Africa", "source": "NASA GSFC"},
    {"date": "2028-07-22", "calendar_date": "2028 Jul 22", "type": "Total",
     "visibility_text": "SE Asia, E. Indies, Australia, N.Z.", "source": "NASA GSFC"},
    {"date": "2029-01-14", "calendar_date": "2029 Jan 14", "type": "Partial",
     "visibility_text": "N. America, C. America", "source": "NASA GSFC"},
    {"date": "2029-06-12", "calendar_date": "2029 Jun 12", "type": "Partial",
     "visibility_text": "Arctic, Scandinavia, Alaska, n Asia, n Canada", "source": "NASA GSFC"},
    {"date": "2029-07-11", "calendar_date": "2029 Jul 11", "type": "Partial",
     "visibility_text": "s Chile, s Argentina", "source": "NASA GSFC"},
    {"date": "2029-12-05", "calendar_date": "2029 Dec 05", "type": "Partial",
     "visibility_text": "s Argentina, s Chile, Antarctica", "source": "NASA GSFC"},
    {"date": "2030-06-01", "calendar_date": "2030 Jun 01", "type": "Annular",
     "visibility_text": "Europe, n Africa, Mid East, Asia, Arctic, Alaska", "source": "NASA GSFC"},
    {"date": "2030-11-25", "calendar_date": "2030 Nov 25", "type": "Total",
     "visibility_text": "s Africa, s Indian Oc., E. Indies, Australia, Antarctica", "source": "NASA GSFC"},
    {"date": "2031-05-21", "calendar_date": "2031 May 21", "type": "Annular",
     "visibility_text": "Africa, s Asia, E. Indies, Australia", "source": "NASA GSFC"},
    {"date": "2031-11-14", "calendar_date": "2031 Nov 14", "type": "Hybrid",
     "visibility_text": "Pacific, s US, C. America, nw S. America", "source": "NASA GSFC"},
    {"date": "2032-05-09", "calendar_date": "2032 May 09", "type": "Annular",
     "visibility_text": "s S. America, s Africa", "source": "NASA GSFC"},
    {"date": "2032-11-03", "calendar_date": "2032 Nov 03", "type": "Partial",
     "visibility_text": "Asia", "source": "NASA GSFC"},
    {"date": "2033-03-30", "calendar_date": "2033 Mar 30", "type": "Total",
     "visibility_text": "N. America", "source": "NASA GSFC"},
    {"date": "2033-09-23", "calendar_date": "2033 Sep 23", "type": "Partial",
     "visibility_text": "s S. America, Antarctica", "source": "NASA GSFC"},
    {"date": "2034-03-20", "calendar_date": "2034 Mar 20", "type": "Total",
     "visibility_text": "Africa, Europe, w Asia", "source": "NASA GSFC"},
]

LUNAR_ECLIPSES: List[Dict[str, Any]] = [
    {"date": "2026-03-03", "calendar_date": "2026 Mar 03", "type": "Total",
     "visibility_text": "e Asia, Australia, Pacific, Americas", "source": "NASA GSFC"},
    {"date": "2026-08-28", "calendar_date": "2026 Aug 28", "type": "Partial",
     "visibility_text": "e Pacific, Americas, Europe, Africa", "source": "NASA GSFC"},
    {"date": "2027-02-20", "calendar_date": "2027 Feb 20", "type": "Penumbral",
     "visibility_text": "Americas, Europe, Africa, Asia", "source": "NASA GSFC"},
    {"date": "2027-07-18", "calendar_date": "2027 Jul 18", "type": "Penumbral",
     "visibility_text": "e Africa, Asia, Australia, Pacific", "source": "NASA GSFC"},
    {"date": "2027-08-17", "calendar_date": "2027 Aug 17", "type": "Penumbral",
     "visibility_text": "Pacific, Americas", "source": "NASA GSFC"},
    {"date": "2028-01-12", "calendar_date": "2028 Jan 12", "type": "Partial",
     "visibility_text": "Americas, Europe, Africa", "source": "NASA GSFC"},
    {"date": "2028-07-06", "calendar_date": "2028 Jul 06", "type": "Partial",
     "visibility_text": "Europe, Africa, Asia, Australia", "source": "NASA GSFC"},
    {"date": "2028-12-31", "calendar_date": "2028 Dec 31", "type": "Total",
     "visibility_text": "Europe, Africa, Asia, Australia, Pacific", "source": "NASA GSFC"},
    {"date": "2029-06-26", "calendar_date": "2029 Jun 26", "type": "Total",
     "visibility_text": "Americas, Europe, Africa, Mid East", "source": "NASA GSFC"},
    {"date": "2029-12-20", "calendar_date": "2029 Dec 20", "type": "Total",
     "visibility_text": "Americas, Europe, Africa, Asia", "source": "NASA GSFC"},
    {"date": "2030-06-15", "calendar_date": "2030 Jun 15", "type": "Partial",
     "visibility_text": "Europe, Africa, Asia, Australia", "source": "NASA GSFC"},
    {"date": "2030-12-09", "calendar_date": "2030 Dec 09", "type": "Penumbral",
     "visibility_text": "Americas, Europe, Africa, Asia", "source": "NASA GSFC"},
    {"date": "2031-05-07", "calendar_date": "2031 May 07", "type": "Penumbral",
     "visibility_text": "Americas, Europe, Africa", "source": "NASA GSFC"},
    {"date": "2031-06-05", "calendar_date": "2031 Jun 05", "type": "Penumbral",
     "visibility_text": "E. Indies, Australia, Pacific", "source": "NASA GSFC"},
    {"date": "2031-10-30", "calendar_date": "2031 Oct 30", "type": "Penumbral",
     "visibility_text": "Americas", "source": "NASA GSFC"},
    {"date": "2032-04-25", "calendar_date": "2032 Apr 25", "type": "Total",
     "visibility_text": "e Africa, Asia, Australia, Pacific", "source": "NASA GSFC"},
    {"date": "2032-10-18", "calendar_date": "2032 Oct 18", "type": "Total",
     "visibility_text": "Africa, Europe, Asia, Australia", "source": "NASA GSFC"},
    {"date": "2033-04-14", "calendar_date": "2033 Apr 14", "type": "Total",
     "visibility_text": "Europe, Africa, Asia, Australia", "source": "NASA GSFC"},
    {"date": "2033-10-08", "calendar_date": "2033 Oct 08", "type": "Total",
     "visibility_text": "Asia, Australia, Pacific, Americas", "source": "NASA GSFC"},
    {"date": "2034-04-03", "calendar_date": "2034 Apr 03", "type": "Penumbral",
     "visibility_text": "Europe, Africa, Asia, Australia", "source": "NASA GSFC"},
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
            f"**The next lunar eclipse is a {l.get('type','?')} eclipse on {l.get('date','?')}. "
            f"It {tn} be visible from Tennessee.**"
        )
    else:
        parts.append("There is no future lunar eclipse in the current list.")

    return " ".join(parts)


# -----------------------------------------------------------
# NEW ENDPOINT: /eclipse-list
# -----------------------------------------------------------

@app.get("/eclipse-list")
async def eclipse_list(
    lat: float = Query(..., description="Latitude of user (for regional classification)"),
    lon: float = Query(..., description="Longitude of user"),
) -> Dict[str, Any]:
    """Return complete lists of all solar and lunar eclipses."""

    user_region = classify_region(lat, lon)

    # Decorate each eclipse with visibility flags
    def decorate(e: Dict[str, Any]) -> Dict[str, Any]:
        vis = e.get("visibility_text", "")
        return {
            "date": e.get("date"),
            "type": e.get("type"),
            "visibility_text": vis,
            "visible_from_tennessee": is_visible_in_tennessee(vis),
            "visible_from_user_region": is_visible_in_region(vis, user_region),
        }

    solar_list = [decorate(e) for e in SOLAR_ECLIPSES]
    lunar_list = [decorate(e) for e in LUNAR_ECLIPSES]

    return {
        "location": {"lat": lat, "lon": lon},
        "user_region": user_region,
        "total_solar_eclipses": len(solar_list),
        "total_lunar_eclipses": len(lunar_list),
        "solar_eclipses": solar_list,
        "lunar_eclipses": lunar_list,
    }


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
# Existing /weather-astro Endpoint
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
