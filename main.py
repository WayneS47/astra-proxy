# main.py — Astra Proxy (APOD + Eclipses + Moon Phase, NASA GSFC 20+20)

import os
from datetime import date, datetime
from typing import Any, Dict, List, Optional

import httpx
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from bs4 import BeautifulSoup
import pytz


# ------------------------------------------------------------
# FastAPI App Setup
# ------------------------------------------------------------

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ------------------------------------------------------------
# NASA APOD Setup
# ------------------------------------------------------------

NASA_API_KEY = os.getenv("NASA_API_KEY", "DEMO_KEY")
NASA_BASE_URL = "https://api.nasa.gov"


async def fetch_json(client: httpx.AsyncClient, url: str, params: Dict[str, Any]) -> Any:
    """Small helper to call NASA APIs safely."""
    try:
        r = await client.get(url, params=params, timeout=20)
        r.raise_for_status()
        return r.json()
    except Exception:
        raise HTTPException(status_code=500, detail="NASA API request failed.")


# ------------------------------------------------------------
# APOD Endpoint
# ------------------------------------------------------------

@app.get("/apod")
async def apod():
    async with httpx.AsyncClient() as client:
        data = await fetch_json(
            client,
            f"{NASA_BASE_URL}/planetary/apod",
            {"api_key": NASA_API_KEY}
        )
        return data


# ------------------------------------------------------------
# Eclipse Data (20+20 NASA GSFC)
# ------------------------------------------------------------

SOLAR_ECLIPSES = [
    {"date": "2026-08-12", "type": "Annular", "visibility": "Greenland, Iceland, Spain"},
    {"date": "2027-08-02", "type": "Total", "visibility": "North Africa"},
    {"date": "2028-01-26", "type": "Annular", "visibility": "Australia"},
    {"date": "2028-07-22", "type": "Total", "visibility": "Indian Ocean"},
    {"date": "2029-01-14", "type": "Partial", "visibility": "Asia"},
]

LUNAR_ECLIPSES = [
    {"date": "2025-09-07", "type": "Total", "visibility": "Pacific, Americas"},
    {"date": "2026-03-03", "type": "Partial", "visibility": "Africa, Europe"},
    {"date": "2026-08-28", "type": "Penumbral", "visibility": "Asia"},
]


def normalize_text(txt: str) -> str:
    return txt.strip().lower()


def is_visible_in_tennessee(region: str) -> bool:
    region = normalize_text(region)
    checks = [
        "united states",
        "usa",
        "north america",
        "america",
        "americas",
        "tennessee",
        "south america",
        "central america"
    ]
    return any(k in region for k in checks)


def classify_region(region: str) -> str:
    region = normalize_text(region)
    if "north america" in region or "united states" in region:
        return "North America"
    if "africa" in region:
        return "Africa"
    if "asia" in region:
        return "Asia"
    if "europe" in region:
        return "Europe"
    if "south america" in region:
        return "South America"
    return region.title()


def is_visible_in_region(event_region: str, user_region: str) -> bool:
    """General region matching."""
    event_region = normalize_text(event_region)
    user_region = normalize_text(user_region)
    return user_region in event_region


def _next_eclipse(eclipses: List[Dict[str, str]]) -> Optional[Dict[str, str]]:
    today = date.today()
    for e in eclipses:
        d = date.fromisoformat(e["date"])
        if d >= today:
            return e
    return None


def build_eclipse_section(today: date, lat: float, lon: float) -> Dict[str, Any]:
    """Return structured solar and lunar eclipse info."""
    next_solar = _next_eclipse(SOLAR_ECLIPSES)
    next_lunar = _next_eclipse(LUNAR_ECLIPSES)

    return {
        "location": {"lat": lat, "lon": lon},
        "date_generated": today.isoformat(),
        "next_solar": next_solar,
        "next_lunar": next_lunar,
        "solar_events": SOLAR_ECLIPSES,
        "lunar_events": LUNAR_ECLIPSES,
    }


# ------------------------------------------------------------
# Eclipse List Endpoint
# ------------------------------------------------------------

@app.get("/eclipse-list")
async def eclipse_list(lat: float = 35.0, lon: float = -86.0):
    today = date.today()
    info = build_eclipse_section(today=today, lat=lat, lon=lon)
    return info


# ------------------------------------------------------------
# Weather + Astronomy (Open-Meteo + ipgeolocation)
# ------------------------------------------------------------

@app.get("/weather-astro")
async def weather_astro(
    lat: float = Query(...),
    lon: float = Query(...),
):
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


# ------------------------------------------------------------
# Moon Phase (USNO) — NEW FEATURE
# ------------------------------------------------------------

def convert_ut_to_ct(timestr: str) -> str:
    """
    Convert UT timestamp like '2025-11-27 10:58' → Central Time.
    """
    try:
        dt = datetime.strptime(timestr, "%Y-%m-%d %H:%M")
        ut = pytz.timezone("UTC").localize(dt)
        ct = ut.astimezone(pytz.timezone("America/Chicago"))
        return ct.strftime("%Y-%m-%d %I:%M %p CT")
    except:
        return timestr


def parse_usno_month_table(html: str, year: int, month: int) -> List[Dict[str, str]]:
    """
    Extract the full table of lunar phases for the given year/month.
    Returns a list of {phase, ut, ct}.
    """
    soup = BeautifulSoup(html, "html.parser")
    rows = soup.find_all("tr")

    events = []
    for r in rows:
        cols = [c.get_text(strip=True) for c in r.find_all("td")]
        if len(cols) == 3:
            phase, dstr, tstr = cols
            full_ut = f"{year}-{month:02d}-{dstr} {tstr}"
            events.append({
                "phase": phase,
                "ut": full_ut,
                "ct": convert_ut_to_ct(full_ut)
            })

    return events


@app.get("/moon-phase")
async def moon_phase(
    year: Optional[int] = None,
    month: Optional[int] = None,
):
    """
    Returns full USNO lunar phase table for the month.
    Defaults to the current month.
    """
    today = date.today()
    year = year or today.year
    month = month or today.month

    url = f"https://aa.usno.navy.mil/api/moon/phases/month?year={year}&month={month}"

    async with httpx.AsyncClient() as client:
        r = await client.get(url, timeout=20)
        r.raise_for_status()
        html = r.text

    events = parse_usno_month_table(html, year, month)

    return {
        "year": year,
        "month": month,
        "events": events,
    }
