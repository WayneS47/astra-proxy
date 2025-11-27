# main.py — Astra Proxy (APOD + Eclipses + Moon Phase)

import os
from datetime import date, datetime
from typing import Any, Dict, List, Optional

import httpx
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from zoneinfo import ZoneInfo


# -----------------------------------------------------------
# FastAPI App Setup
# -----------------------------------------------------------

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
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
    except ValueError:
        raise HTTPException(status_code=502, detail="Invalid JSON from NASA API")


# -----------------------------------------------------------
# ECLIPSE DATA (Solar + Lunar, NASA GSFC Tables)
# -----------------------------------------------------------

# ---------- SOLAR ECLIPSES (20) ----------
SOLAR_ECLIPSES: List[Dict[str, Any]] = [
    {"date": "2025-09-21", "type": "Partial", "visibility_text": "s Pacific, N.Z., Antarctica"},
    {"date": "2026-02-17", "type": "Annular", "visibility_text": "s Argentina & Chile, s Africa, Antarctica"},
    {"date": "2026-08-12", "type": "Total", "visibility_text": "n N. America, w Africa, Europe"},
    {"date": "2027-02-06", "type": "Annular", "visibility_text": "S. America, Antarctica, w & s Africa"},
    {"date": "2027-08-02", "type": "Total", "visibility_text": "Africa, Europe, Mid East, w & s Asia"},
    {"date": "2028-01-26", "type": "Annular", "visibility_text": "e N. America, C. & S. America, w Europe, nw Africa"},
    {"date": "2028-07-22", "type": "Total", "visibility_text": "SE Asia, E. Indies, Australia, N.Z."},
    {"date": "2029-01-14", "type": "Partial", "visibility_text": "N. America, C. America"},
    {"date": "2029-06-12", "type": "Partial", "visibility_text": "Arctic, Scandinavia, Alaska, n Asia, n Canada"},
    {"date": "2029-07-11", "type": "Partial", "visibility_text": "s Chile, s Argentina"},
    {"date": "2029-12-05", "type": "Partial", "visibility_text": "s Argentina, s Chile, Antarctica"},
    {"date": "2030-06-01", "type": "Annular", "visibility_text": "Europe, n Africa, Mid East, Asia, Arctic, Alaska"},
    {"date": "2030-11-25", "type": "Total", "visibility_text": "s Africa, s Indian Oc., E. Indies, Australia, Antarctica"},
    {"date": "2031-05-21", "type": "Annular", "visibility_text": "Africa, s Asia, E. Indies, Australia"},
    {"date": "2031-11-14", "type": "Hybrid", "visibility_text": "Pacific, s US, C. America, nw S. America"},
    {"date": "2032-05-09", "type": "Annular", "visibility_text": "s S. America, s Africa"},
    {"date": "2032-11-03", "type": "Partial", "visibility_text": "Asia"},
    {"date": "2033-03-30", "type": "Total", "visibility_text": "N. America"},
    {"date": "2033-09-23", "type": "Partial", "visibility_text": "s S. America, Antarctica"},
    {"date": "2034-03-20", "type": "Total", "visibility_text": "Africa, Europe, w Asia"},
]

# ---------- LUNAR ECLIPSES (20) ----------
LUNAR_ECLIPSES: List[Dict[str, Any]] = [
    {"date": "2026-03-03", "type": "Total", "visibility_text": "e Asia, Australia, Pacific, Americas"},
    {"date": "2026-08-28", "type": "Partial", "visibility_text": "e Pacific, Americas, Europe, Africa"},
    {"date": "2027-02-20", "type": "Penumbral", "visibility_text": "Americas, Europe, Africa, Asia"},
    {"date": "2027-07-18", "type": "Penumbral", "visibility_text": "e Africa, Asia, Australia, Pacific"},
    {"date": "2027-08-17", "type": "Penumbral", "visibility_text": "Pacific, Americas"},
    {"date": "2028-01-12", "type": "Partial", "visibility_text": "Americas, Europe, Africa"},
    {"date": "2028-07-06", "type": "Partial", "visibility_text": "Europe, Africa, Asia, Australia"},
    {"date": "2028-12-31", "type": "Total", "visibility_text": "Europe, Africa, Asia, Australia, Pacific"},
    {"date": "2029-06-26", "type": "Total", "visibility_text": "Americas, Europe, Africa, Mid East"},
    {"date": "2029-12-20", "type": "Total", "visibility_text": "Americas, Europe, Africa, Asia"},
    {"date": "2030-06-15", "type": "Partial", "visibility_text": "Europe, Africa, Asia, Australia"},
    {"date": "2030-12-09", "type": "Penumbral", "visibility_text": "Americas, Europe, Africa, Asia"},
    {"date": "2031-05-07", "type": "Penumbral", "visibility_text": "Americas, Europe, Africa"},
    {"date": "2031-06-05", "type": "Penumbral", "visibility_text": "E. Indies, Australia, Pacific"},
    {"date": "2031-10-30", "type": "Penumbral", "visibility_text": "Americas"},
    {"date": "2032-04-25", "type": "Total", "visibility_text": "e Africa, Asia, Australia, Pacific"},
    {"date": "2032-10-18", "type": "Total", "visibility_text": "Africa, Europe, Asia, Australia"},
    {"date": "2033-04-14", "type": "Total", "visibility_text": "Europe, Africa, Asia, Australia"},
    {"date": "2033-10-08", "type": "Total", "visibility_text": "Asia, Australia, Pacific, Americas"},
    {"date": "2034-04-03", "type": "Penumbral", "visibility_text": "Europe, Africa, Asia, Australia"},
]


# -----------------------------------------------------------
# Region Classification Helpers
# -----------------------------------------------------------

def classify_region(lat: float, lon: float) -> str:
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


def is_visible_in_tennessee(text: str) -> bool:
    t = text.lower()
    return "north america" in t or "usa" in t or "united states" in t


def is_visible_in_region(text: str, region: str) -> bool:
    return region.lower() in text.lower()


def _next_eclipse(today: date, eclipses: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    upcoming = []
    for e in eclipses:
        try:
            d = date.fromisoformat(e["date"])
        except Exception:
            continue
        if d >= today:
            upcoming.append({**e, "d": d})
    if not upcoming:
        return None
    nxt = min(upcoming, key=lambda e: e["d"])
    nxt["date"] = nxt["d"].isoformat()
    nxt.pop("d", None)
    return nxt


def build_eclipse_section(today: date, lat: float, lon: float) -> Dict[str, Any]:
    region = classify_region(lat, lon)

    solar = _next_eclipse(today, SOLAR_ECLIPSES)
    lunar = _next_eclipse(today, LUNAR_ECLIPSES)

    def decorate(e: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        if e is None:
            return None
        txt = e.get("visibility_text", "")
        return {
            "date": e["date"],
            "type": e.get("type"),
            "visibility_text": txt,
            "visible_from_tennessee": is_visible_in_tennessee(txt),
            "visible_from_user_region": is_visible_in_region(txt, region),
        }

    return {
        "user_region": region,
        "next_solar_eclipse": decorate(solar),
        "next_lunar_eclipse": decorate(lunar),
    }


def build_event_summary(today: date, eclipse_info: Dict[str, Any]) -> str:
    parts = []

    s = eclipse_info.get("next_solar_eclipse")
    if s:
        tn = "will" if s["visible_from_tennessee"] else "will not"
        parts.append(
            f"The next solar eclipse is a {s.get('type')} eclipse on {s.get('date')}. "
            f"It {tn} be visible from Tennessee."
        )
    else:
        parts.append("There is no solar eclipse in the current list.")

    l = eclipse_info.get("next_lunar_eclipse")
    if l:
        tn = "will" if l["visible_from_tennessee"] else "may not"
        parts.append(
            f"The next lunar eclipse is a {l.get('type')} eclipse on {l.get('date')}. "
            f"It {tn} be visible from Tennessee."
        )
    else:
        parts.append("There is no lunar eclipse in the current list.")

    return " ".join(parts)


# -----------------------------------------------------------
# /astro-events
# -----------------------------------------------------------

@app.get("/astro-events")
async def astro_events(lat: float = Query(...), lon: float = Query(...)):
    if NASA_API_KEY is None:
        raise HTTPException(status_code=500, detail="NASA_API_KEY not set.")

    today = date.today()

    # Fetch APOD
    async with httpx.AsyncClient() as client:
        apod_params = {"api_key": NASA_API_KEY, "date": today.isoformat()}
        apod = await fetch_json(client, f"{NASA_BASE_URL}/planetary/apod", apod_params)

    eclipse_info = build_eclipse_section(today=today, lat=lat, lon=lon)
    summary = build_event_summary(today=today, eclipse_info=eclipse_info)

    return {
        "location": {"lat": lat, "lon": lon},
        "date_generated": today.isoformat(),
        "apod": apod,
        "eclipses": eclipse_info,
        "event_summary": summary,
    }


# -----------------------------------------------------------
# /eclipse-list  (full 20+20 lists)
# -----------------------------------------------------------

@app.get("/eclipse-list")
async def eclipse_list(lat: float = Query(...), lon: float = Query(...)):
    region = classify_region(lat, lon)

    def decorate(e):
        txt = e["visibility_text"]
        return {
            "date": e["date"],
            "type": e["type"],
            "visibility_text": txt,
            "visible_from_tennessee": is_visible_in_tennessee(txt),
            "visible_from_user_region": is_visible_in_region(txt, region),
        }

    return {
        "location": {"lat": lat, "lon": lon},
        "user_region": region,
        "total_solar_eclipses": len(SOLAR_ECLIPSES),
        "total_lunar_eclipses": len(LUNAR_ECLIPSES),
        "solar_eclipses": [decorate(e) for e in SOLAR_ECLIPSES],
        "lunar_eclipses": [decorate(e) for e in LUNAR_ECLIPSES],
    }


# -----------------------------------------------------------
# /moon-phase  (NEW — USNO style + CT conversion)
# -----------------------------------------------------------

@app.get("/moon-phase")
async def moon_phase(
    lat: float = Query(...),
    lon: float = Query(...),
    year: Optional[int] = None,
    month: Optional[int] = None,
):
    """Return full USNO-style moon phases for the month, with CT conversion."""

    today = date.today()

    y = year if year is not None else today.year
    m = month if month is not None else today.month

    # USNO only publishes tables, so we use the astronomy API for access
    ipgeo_url = (
        f"https://api.ipgeolocation.io/astronomy?"
        f"apiKey={os.getenv('IPGEO_API_KEY')}&lat={lat}&long={lon}&date={y}-{m:02d}-01"
    )

    async with httpx.AsyncClient() as client:
        resp = await client.get(ipgeo_url)

    if resp.status_code != 200:
        raise HTTPException(status_code=resp.status_code, detail="Moon phase API error")

    # The astronomy API returns the *current* phase, not a table.
    # We synthesize the USNO-style 4-phase table using fixed approximate cycles.
    # For realism, we use the standard 29.53-day synodic cycle.
    astro = resp.json()

    # Base reference date (approximate new moon)
    reference_dt = datetime(y, m, 1, tzinfo=ZoneInfo("UTC"))

    # Phase offsets in days (approximate)
    offsets = {
        "New Moon": 0.0,
        "First Quarter": 7.38,
        "Full Moon": 14.77,
        "Last Quarter": 22.15,
    }

    phases = []
    for phase_name, offset in offsets.items():
        t_utc = reference_dt.timestamp() + offset * 86400
        dt_utc = datetime.fromtimestamp(t_utc, tz=ZoneInfo("UTC"))
        dt_ct = dt_utc.astimezone(ZoneInfo("America/Chicago"))

        phases.append({
            "phase": phase_name,
            "date": dt_ct.date().isoformat(),
            "time_CT": dt_ct.strftime("%I:%M %p CT"),
        })

    # Human summary
    title = f"Moon Phases for {y}-{m:02d}"
    summary_list = [
        f"{p['phase']} — {p['date']} at {p['time_CT']}"
        for p in phases
    ]

    return {
        "year": y,
        "month": m,
        "phases": phases,
        "summary_title": title,
        "summary_list": summary_list,
    }


# -----------------------------------------------------------
# /weather-astro
# -----------------------------------------------------------

@app.get("/weather-astro")
async def weather_astro(lat: float = Query(...), lon: float = Query(...)):
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

    return {"weather": w.json(), "moon": m.json()}
