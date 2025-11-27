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
# ECLIPSE DATA — 20 Solar + 20 Lunar (NASA GSFC)
# -----------------------------------------------------------

SOLAR_ECLIPSES = [
    {"date": "2025-09-21", "calendar_date": "2025 Sep 21", "type": "Partial",
     "visibility": "s Pacific, N.Z., Antarctica", "source": "NASA GSFC"},
    {"date": "2026-02-17", "calendar_date": "2026 Feb 17", "type": "Annular",
     "visibility": "s Argentina & Chile, s Africa, Antarctica", "source": "NASA GSFC"},
    {"date": "2026-08-12", "calendar_date": "2026 Aug 12", "type": "Total",
     "visibility": "n N. America, w Africa, Europe", "source": "NASA GSFC"},
    {"date": "2027-02-06", "calendar_date": "2027 Feb 06", "type": "Annular",
     "visibility": "S. America, Antarctica, w & s Africa", "source": "NASA GSFC"},
    {"date": "2027-08-02", "calendar_date": "2027 Aug 02", "type": "Total",
     "visibility": "Africa, Europe, Mid East, w & s Asia", "source": "NASA GSFC"},
    {"date": "2028-01-26", "calendar_date": "2028 Jan 26", "type": "Annular",
     "visibility": "e N. America, C. & S. America, w Europe, nw Africa", "source": "NASA GSFC"},
    {"date": "2028-07-22", "calendar_date": "2028 Jul 22", "type": "Total",
     "visibility": "SE Asia, E. Indies, Australia, N.Z.", "source": "NASA GSFC"},
    {"date": "2029-01-14", "calendar_date": "2029 Jan 14", "type": "Partial",
     "visibility": "N. America, C. America", "source": "NASA GSFC"},
    {"date": "2029-06-12", "calendar_date": "2029 Jun 12", "type": "Partial",
     "visibility": "Arctic, Scandinavia, Alaska, n Asia, n Canada", "source": "NASA GSFC"},
    {"date": "2029-07-11", "calendar_date": "2029 Jul 11", "type": "Partial",
     "visibility": "s Chile, s Argentina", "source": "NASA GSFC"},
    {"date": "2029-12-05", "calendar_date": "2029 Dec 05", "type": "Partial",
     "visibility": "s Argentina, s Chile, Antarctica", "source": "NASA GSFC"},
    {"date": "2030-06-01", "calendar_date": "2030 Jun 01", "type": "Annular",
     "visibility": "Europe, n Africa, Mid East, Asia, Arctic, Alaska", "source": "NASA GSFC"},
    {"date": "2030-11-25", "calendar_date": "2030 Nov 25", "type": "Total",
     "visibility": "s Africa, s Indian Oc., E. Indies, Australia, Antarctica", "source": "NASA GSFC"},
    {"date": "2031-05-21", "calendar_date": "2031 May 21", "type": "Annular",
     "visibility": "Africa, s Asia, E. Indies, Australia", "source": "NASA GSFC"},
    {"date": "2031-11-14", "calendar_date": "2031 Nov 14", "type": "Hybrid",
     "visibility": "Pacific, s US, C. America, nw S. America", "source": "NASA GSFC"},
    {"date": "2032-05-09", "calendar_date": "2032 May 09", "type": "Annular",
     "visibility": "s S. America, s Africa", "source": "NASA GSFC"},
    {"date": "2032-11-03", "calendar_date": "2032 Nov 03", "type": "Partial",
     "visibility": "Asia", "source": "NASA GSFC"},
    {"date": "2033-03-30", "calendar_date": "2033 Mar 30", "type": "Total",
     "visibility": "N. America", "source": "NASA GSFC"},
    {"date": "2033-09-23", "calendar_date": "2033 Sep 23", "type": "Partial",
     "visibility": "s S. America, Antarctica", "source": "NASA GSFC"},
    {"date": "2034-03-20", "calendar_date": "2034 Mar 20", "type": "Total",
     "visibility": "Africa, Europe, w Asia", "source": "NASA GSFC"},
]


LUNAR_ECLIPSES = [
    {"date": "2026-03-03", "calendar_date": "2026 Mar 03", "type": "Total",
     "visibility": "e Asia, Australia, Pacific, Americas", "source": "NASA GSFC"},
    {"date": "2026-08-28", "calendar_date": "2026 Aug 28", "type": "Partial",
     "visibility": "e Pacific, Americas, Europe, Africa", "source": "NASA GSFC"},
    {"date": "2027-02-20", "calendar_date": "2027 Feb 20", "type": "Penumbral",
     "visibility": "Americas, Europe, Africa, Asia", "source": "NASA GSFC"},
    {"date": "2027-07-18", "calendar_date": "2027 Jul 18", "type": "Penumbral",
     "visibility": "e Africa, Asia, Australia, Pacific", "source": "NASA GSFC"},
    {"date": "2027-08-17", "calendar_date": "2027 Aug 17", "type": "Penumbral",
     "visibility": "Pacific, Americas", "source": "NASA GSFC"},
    {"date": "2028-01-12", "calendar_date": "2028 Jan 12", "type": "Partial",
     "visibility": "Americas, Europe, Africa", "source": "NASA GSFC"},
    {"date": "2028-07-06", "calendar_date": "2028 Jul 06", "type": "Partial",
     "visibility": "Europe, Africa, Asia, Australia", "source": "NASA GSFC"},
    {"date": "2028-12-31", "calendar_date": "2028 Dec 31", "type": "Total",
     "visibility": "Europe, Africa, Asia, Australia, Pacific", "source": "NASA GSFC"},
    {"date": "2029-06-26", "calendar_date": "2029 Jun 26", "type": "Total",
     "visibility": "Americas, Europe, Africa, Mid East", "source": "NASA GSFC"},
    {"date": "2029-12-20", "calendar_date": "2029 Dec 20", "type": "Total",
     "visibility": "Americas, Europe, Africa, Asia", "source": "NASA GSFC"},
    {"date": "2030-06-15", "calendar_date": "2030 Jun 15", "type": "Partial",
     "visibility": "Europe, Africa, Asia
