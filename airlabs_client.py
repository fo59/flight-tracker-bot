import logging
from typing import Optional

import httpx

from config import AIRLABS_API_KEY

BASE_URL_FLIGHT = "https://airlabs.co/api/v9/flight"
BASE_URL_FLIGHTS = "https://airlabs.co/api/v9/flights"
logger = logging.getLogger(__name__)


async def lookup_flight(flight_iata: str):
    if not AIRLABS_API_KEY:
        return None

    params = {
        "api_key": AIRLABS_API_KEY,
        "flight_iata": flight_iata.upper(),
    }

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(BASE_URL_FLIGHT, params=params)
            resp.raise_for_status()
            data = resp.json()
            return data.get("response")
    except Exception:
        logger.exception("AirLabs cagri basarisiz: %s", flight_iata)
        return None


async def fetch_all_active_flights() -> Optional[dict[str, dict]]:
    """Fetch all active flights from AirLabs. Returns dict of flight_iata -> flight data."""
    if not AIRLABS_API_KEY:
        return None
    params = {"api_key": AIRLABS_API_KEY}
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(BASE_URL_FLIGHTS, params=params)
            resp.raise_for_status()
            data = resp.json()
            items = data.get("response") or []
            return {item.get("flight_iata"): item for item in items if item.get("flight_iata")}
    except Exception:
        logger.exception("AirLabs bulk flights cagri basarisiz")
        return None


def extract_position(flight_data: dict):
    if not flight_data:
        return None
    lat = flight_data.get("lat")
    lng = flight_data.get("lng")
    if lat is not None and lng is not None:
        return {
            "lat": lat,
            "lon": lng,
            "alt": flight_data.get("alt"),
            "speed": flight_data.get("speed"),
            "direction": flight_data.get("dir"),
        }
    return None
