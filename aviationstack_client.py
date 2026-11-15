import logging

import httpx

from config import AVIATIONSTACK_API_KEY

BASE_URL = "https://api.aviationstack.com/v1/flights"
logger = logging.getLogger(__name__)


async def lookup_flight(flight_iata: str):
    if not AVIATIONSTACK_API_KEY:
        return None

    params = {
        "access_key": AVIATIONSTACK_API_KEY,
        "flight_iata": flight_iata.upper(),
    }

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(BASE_URL, params=params)
            resp.raise_for_status()
            data = resp.json()
            if data.get("data"):
                return data["data"][0]
            return None
    except Exception:
        logger.exception("AviationStack cagri basarisiz: %s", flight_iata)
        return None


def extract_position(flight_data: dict):
    if not flight_data:
        return None
    live = flight_data.get("live") or {}
    if live.get("latitude") is not None:
        return {
            "lat": live["latitude"],
            "lon": live["longitude"],
            "alt": live.get("altitude"),
            "speed": live.get("speed_horizontal"),
            "direction": live.get("direction"),
        }
    return None


def extract_schedule(flight_data: dict):
    if not flight_data:
        return None

    dep = flight_data.get("departure") or {}
    arr = flight_data.get("arrival") or {}

    return {
        "flight_status": flight_data.get("flight_status"),
        "dep_iata": dep.get("iata"),
        "dep_icao": dep.get("icao"),
        "dep_scheduled": dep.get("scheduled"),
        "dep_estimated": dep.get("estimated"),
        "dep_actual": dep.get("actual"),
        "dep_gate": dep.get("gate"),
        "dep_terminal": dep.get("terminal"),
        "arr_iata": arr.get("iata"),
        "arr_icao": arr.get("icao"),
        "arr_scheduled": arr.get("scheduled"),
        "arr_estimated": arr.get("estimated"),
        "arr_actual": arr.get("actual"),
        "arr_gate": arr.get("gate"),
        "arr_terminal": arr.get("terminal"),
    }
