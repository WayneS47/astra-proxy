# main.py — Astra Proxy (APOD + Eclipses + Moon Phase, NASA GSFC 20+20)

import os
from datetime import date, datetime
from typing import Any, Dict, List, Optional

import httpx
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from bs4 import BeautifulSoup
import pytz


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
    except ValueError as exc:
        raise HTTPException(status_code=502, detail="Invalid JSON from NASA API") from exc


# -----------------------------------------------------------
# ECLIPSE DATA — NASA GSFC 20+20
# -----------------------------------------------------------

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
# VISIBILITY HELPERS
# -----------------------------------------------------------

def normalize_text(text: str) -> str:
    t = text.lower()
    replacements = {
        "n. america": "north america",
        "s. america": "south america",
        "americas": "north america south america",
        "c. america": "central america",
        "u.s.": "united states",
        "us": "united states",
        "usa": "united states",
    }
    for old, new in replacements.items():
        t = t.replace(old, new)
    return t


def is_visible_in_tennessee(visibility_text: str) -> bool:
    t = normalize_text(visibility_text)
    return (
        "north america" in t
        or "united states" in t
    )


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


def is_visible_in_region(visibility_text: str, region: str) -> bool:
    t = normalize_text(visibility_text)
    r = region.lower()
    return r in t


def _next_eclipse(today: date, eclipses: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
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
    region = classify_region(lat, lon)

    next_solar = _next_eclipse(today, SOLAR_ECLIPSES)
    next_lunar = _next_eclipse(today, LUNAR_ECLIPSES)

    def decorate(e: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        if e is None:
            return None
        vis_text = e["visibility_text"]
        return {
            "date": e["date"],
            "type": e["type"],
            "visibility_text": vis_text,
            "visible_from_tennessee": is_visible_in_tennessee(vis_text),
            "visible_from_user_region": is_visible_in_region(vis_text, region),
        }

    return {
        "user_region": region,
        "next_solar_eclipse": decorate(next_solar),
        "next_lunar_eclipse": decorate(next_lunar),
    }


def build_event_summary(today: date, eclipse_info: Dict[str, Any]) -> str:
    parts = []
    s = eclipse_info.get("next_solar_eclipse")
    if s:
        tn = "will" if s["visible_from_tennessee"] else "will not"
        parts.append(
            f"The next solar eclipse is a {s['type']} eclipse on {s['date']}. "
            f"It {tn} be visible from Tennessee."
        )
    l = eclipse_info.get("next_lunar_eclipse")
    if l:
        tn = "will" if l["visible_from_tennessee"] else "may not"
        parts.append(
            f"The next lunar eclipse is a {l['type']} eclipse on {l['date']}. "
            f"It {tn} be visible from Tennessee."
        )
    return " ".join(parts)


# -----------------------------------------------------------
# /eclipse-list — Full List
# -----------------------------------------------------------

@app.get("/eclipse-list")
async def eclipse_list(lat: float = Query(...), lon: float = Query(...)):
    region = classify_region(lat, lon)

    def decorate_all(eclipses: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        out = []
        for e in eclipses:
            vis = e["visibility_text"]
            out.append({
                "date": e["date"],
                "type": e["type"],
                "visibility_text": vis,
                "visible_from_tennessee": is_visible_in_tennessee(vis),
                "visible_from_user_region": is_visible_in_region(vis, region),
            })
        return out

    return {
        "location": {"lat": lat, "lon": lon},
        "user_region": region,
        "total_solar_eclipses": len(SOLAR_ECLIPSES),
        "total_lunar_eclipses": len(LUNAR_ECLIPSES),
        "solar_eclipses": decorate_all(SOLAR_ECLIPSES),
        "lunar_eclipses": decorate_all(LUNAR_ECLIPSES),
    }


# -----------------------------------------------------------
# /astro-events
# -----------------------------------------------------------

@app.get("/astro-events")
async def astro_events(lat: float = Query(...), lon: float = Query(...)):
    if NASA_API_KEY is None:
        raise HTTPException(
            status_code=500,
            detail="NASA_API_KEY is not configured."
        )

    today = date.today()

    async with httpx.AsyncClient() as client:
        apod_params = {"api_key": NASA_API_KEY, "date": today.isoformat()}
        apod_url = f"{NASA_BASE_URL}/planetary/apod"
        apod = await fetch_json(client, apod_url, apod_params)

    eclipse_info = build_eclipse_section(today, lat, lon)
    summary = build_event_summary(today, eclipse_info)

    return {
        "location": {"lat": lat, "lon": lon},
        "date_generated": today.isoformat(),
        "apod": apod,
        "eclipses": eclipse_info,
        "event_summary": summary,
    }


# -----------------------------------------------------------
# Weather + Astronomy
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


# -----------------------------------------------------------
# Moon Phase — /moon-phase
# -----------------------------------------------------------

def convert_ut_to_ct(ut_dt: datetime) -> str:
    ct = pytz.timezone("America/Chicago")
    ut = pytz.utc.localize(ut_dt)
    return ut.astimezone(ct).strftime("%Y-%m-%d %I:%M %p CT")


def parse_usno_month_table(html: str) -> List[Dict[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    table = soup.find("table")
    if not table:
        return []

    rows = table.find_all("tr")[1:]

    out = []
    for r in rows:
        cols = [c.get_text(strip=True) for c in r.find_all("td")]
        if len(cols) == 3:
            phase, day, ut_time = cols
            try:
                ut_dt = datetime.strptime(f"{day} {ut_time}", "%Y-%m-%d %H:%M")
                ct_str = convert_ut_to_ct(ut_dt)
            except:
                ct_str = "?"
            out.append({
                "phase": phase,
                "date_ut": f"{day} {ut_time} UT",
                "date_ct": ct_str
            })
    return out


@app.get("/moon-phase")
async def moon_phase():
    today = date.today()
    url = f"https://aa.usno.navy.mil/calculated/moon/phase?date={today.year}-{today.month:02d}"

    async with httpx.AsyncClient() as client:
        r = await client.get(url)
        if r.status_code != 200:
            raise HTTPException(status_code=502, detail="USNO request failed")

    events = parse_usno_month_table(r.text)

    return {
        "year": today.year,
        "month": today.month,
        "events": events,
    }
