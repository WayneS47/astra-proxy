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
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# -----------------------------------------------------------
# NASA APOD Setup (Stable)
# -----------------------------------------------------------

NASA_API_KEY = os.getenv("NASA_API_KEY", "DEMO_KEY")
NASA_BASE_URL = "https://api.nasa.gov"


async def fetch_json(client: httpx.AsyncClient, url: str, params: Dict[str, Any]) -> Any:
    """Stable NASA JSON helper with retry & fallback."""
    for _ in range(2):  # retry twice
        try:
            resp = await client.get(url, params=params, timeout=20, follow_redirects=False)
            resp.raise_for_status()
            return resp.json()
        except Exception:
            continue
    raise HTTPException(status_code=500, detail="NASA API request failed.")


# -----------------------------------------------------------
# Rollback Eclipse Tables (Known-Good)
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
# Region Helpers (Stable)
# -----------------------------------------------------------

def normalize_text(text: str) -> str:
    return text.lower().strip()


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
    r = normalize_text(region)
    return r in t


def is_visible_in_tennessee(visibility_text: str) -> bool:
    t = normalize_text(visibility_text)
    return (
        "north america" in t
        or "united states" in t
        or "usa" in t
    )


# -----------------------------------------------------------
# Next Eclipse Helper
# -----------------------------------------------------------

def _next_eclipse(today: date, eclipses: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    upcoming = []
    for e in eclipses:
        d = date.fromisoformat(e["date"])
        if d >= today:
            upcoming.append({**e, "date_obj": d})
    if not upcoming:
        return None
    nxt = min(upcoming, key=lambda x: x["date_obj"])
    nxt.pop("date_obj", None)
    return nxt


# -----------------------------------------------------------
# Build Eclipse Section (Known Good)
# -----------------------------------------------------------

def build_eclipse_section(today: date, lat: float, lon: float) -> Dict[str, Any]:
    region = classify_region(lat, lon)

    solar = _next_eclipse(today, SOLAR_ECLIPSES)
    lunar = _next_eclipse(today, LUNAR_ECLIPSES)

    def decorate(e):
        if not e:
            return None
        vis = e["visibility_text"]
        return {
            "date": e["date"],
            "type": e["type"],
            "visibility_text": vis,
            "visible_from_tennessee": is_visible_in_tennessee(vis),
            "visible_from_user_region": is_visible_in_region(vis, region),
        }

    return {
        "user_region": region,
        "next_solar_eclipse": decorate(solar),
        "next_lunar_eclipse": decorate(lunar),
    }


# -----------------------------------------------------------
# Event Summary (Stable)
# -----------------------------------------------------------

def build_event_summary(today: date, eclipse_data: Dict[str, Any]) -> str:
    parts = []

    s = eclipse_data.get("next_solar_eclipse")
    if s:
        tn = "will" if s["visible_from_tennessee"] else "will not"
        parts.append(
            f"The next solar eclipse is a {s['type']} eclipse on {s['date']}. It {tn} be visible from Tennessee."
        )
    else:
        parts.append("There is no future solar eclipse in the list.")

    l = eclipse_data.get("next_lunar_eclipse")
    if l:
        tn = "will" if l["visible_from_tennessee"] else "may not"
        parts.append(
            f"The next lunar eclipse is a {l['type']} eclipse on {l['date']}. It {tn} be visible from Tennessee."
        )
    else:
        parts.append("There is no future lunar eclipse in the list.")

    return " ".join(parts)


# -----------------------------------------------------------
# NEW: STATIC MOON PHASE TABLE (No API)
# -----------------------------------------------------------

STATIC_PHASES = [
    {"phase": "New Moon", "approx_date": "2025-02-27"},
    {"phase": "First Quarter", "approx_date": "2025-03-06"},
    {"phase": "Full Moon", "approx_date": "2025-03-14"},
    {"phase": "Last Quarter", "approx_date": "2025-03-21"},
]


@app.get("/moon-phase")
async def moon_phase_static():
    return {
        "source": "static-table",
        "note": "approximate moon phases; no external API",
        "phases": STATIC_PHASES,
    }


# -----------------------------------------------------------
# NEW: /eclipse-list (Stable Rollback)
# -----------------------------------------------------------

@app.get("/eclipse-list")
async def eclipse_list(lat: float = Query(...), lon: float = Query(...)):
    region = classify_region(lat, lon)

    def decorate_all(lst):
        out = []
        for e in lst:
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
# /astro-events (Stable)
# -----------------------------------------------------------

@app.get("/astro-events")
async def astro_events(lat: float = Query(...), lon: float = Query(...)):
    today = date.today()

    async with httpx.AsyncClient(timeout=20, follow_redirects=False) as client:
        apod = await fetch_json(
            client,
            f"{NASA_BASE_URL}/planetary/apod",
            {"api_key": NASA_API_KEY, "date": today.isoformat()},
        )

    eclipse_data = build_eclipse_section(today, lat, lon)
    summary = build_event_summary(today, eclipse_data)

    return {
        "location": {"lat": lat, "lon": lon},
        "date_generated": today.isoformat(),
        "apod": apod,
        "eclipses": eclipse_data,
        "event_summary": summary,
    }


# -----------------------------------------------------------
# Weather + Astronomy (Stable)
# -----------------------------------------------------------

@app.get("/weather-astro")
async def weather_astro(lat: float = Query(...), lon: float = Query(...)):
    key = os.getenv("IPGEO_API_KEY")
    if not key:
        return {"error": "IPGEO_API_KEY missing"}

    open_meteo_url = (
        f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current_weather=true"
    )
    ipgeo_url = (
        f"https://api.ipgeolocation.io/astronomy?apiKey={key}&lat={lat}&long={lon}"
    )

    async with httpx.AsyncClient(timeout=20, follow_redirects=False) as client:
        w = await client.get(open_meteo_url)
        m = await client.get(ipgeo_url)

    return {"weather": w.json(), "moon": m.json()}


# -----------------------------------------------------------
# /iss-location (with HTTPS fallback)
# -----------------------------------------------------------

@app.get("/iss-location")
async def iss_location():
    primary = "http://api.open-notify.org/iss-now.json"
    fallback = "https://api.wheretheiss.at/v1/satellites/25544"

    async with httpx.AsyncClient(timeout=20, follow_redirects=False) as client:
        try:
            r = await client.get(primary)
            r.raise_for_status()
            j = r.json()
            pos = j.get("iss_position", {})
            return {
                "timestamp": j.get("timestamp"),
                "latitude": pos.get("latitude"),
                "longitude": pos.get("longitude"),
            }
        except Exception:
            try:
                r = await client.get(fallback)
                r.raise_for_status()
                j = r.json()
                return {
                    "timestamp": j.get("timestamp"),
                    "latitude": j.get("latitude"),
                    "longitude": j.get("longitude"),
                }
            except Exception:
                return {
                    "timestamp": None,
                    "latitude": None,
                    "longitude": None,
                    "error": "Both ISS APIs failed."
                }


# -----------------------------------------------------------
# /geocode — OpenStreetMap Nominatim
# -----------------------------------------------------------

@app.get("/geocode")
async def geocode(q: str = Query(...)):
    url = "https://nominatim.openstreetmap.org/search"

    params = {
        "q": q,
        "format": "json",
        "limit": 1
    }

    async with httpx.AsyncClient(timeout=20, follow_redirects=False) as client:
        try:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()
            if not data:
                return {"lat": None, "lon": None, "display_name": None}
            best = data[0]
            return {
                "lat": best.get("lat"),
                "lon": best.get("lon"),
                "display_name": best.get("display_name")
            }
        except Exception:
            return {"lat": None, "lon": None, "display_name": None, "error": "geocode failed"}


# -----------------------------------------------------------
# /sky-photo — NASA APOD
# -----------------------------------------------------------

async def fetch_apod():
    """Fetch the NASA Astronomy Picture of the Day."""
    api_key = os.getenv("NASA_API_KEY", "DEMO_KEY")
    url = "https://api.nasa.gov/planetary/apod"

    params = {"api_key": api_key}

    async with httpx.AsyncClient(timeout=20, follow_redirects=False) as client:
        try:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()

            return {
                "title": data.get("title"),
                "description": data.get("explanation"),
                "image_url": data.get("url"),
                "date": data.get("date")
            }

        except Exception:
            return {
                "title": None,
                "description": None,
                "image_url": None,
                "date": None,
                "error": "NASA APOD request failed."
            }


@app.get("/sky-photo")
async def sky_photo():
    """Return today's NASA sky photo info."""
    return await fetch_apod()


# -----------------------------------------------------------
# /health — System Check
# -----------------------------------------------------------

@app.get("/health")
async def health():
    return {"status": "ok"}


# -----------------------------------------------------------
# Run App (Optional)
# -----------------------------------------------------------

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", 8000)))
