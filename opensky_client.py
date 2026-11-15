import asyncio
import logging
import math
import socket

import httpx

from config import OPENSKY_USERNAME, OPENSKY_PASSWORD

API_HOST = "opensky-network.org"
API_PATH = "/api/states/all"
API_IP = None
logger = logging.getLogger(__name__)


def _resolve_ipv4():
    global API_IP
    try:
        addrs = socket.getaddrinfo(API_HOST, 443, socket.AF_INET)
        API_IP = addrs[0][4][0]
        logger.info("OpenSky IPv4 adresi: %s", API_IP)
    except Exception:
        logger.warning("OpenSky IPv4 cozulemedi.")


_resolve_ipv4()


async def fetch_states():
    auth = None
    if OPENSKY_USERNAME:
        auth = (OPENSKY_USERNAME, OPENSKY_PASSWORD)

    urls = []
    if API_IP:
        urls.append(f"https://{API_IP}{API_PATH}")
    urls.append(f"https://{API_HOST}{API_PATH}")

    errors = []
    for url in urls:
        for attempt in range(2):
            try:
                headers = {"Host": API_HOST} if API_IP and API_IP in url else {}
                async with httpx.AsyncClient(timeout=httpx.Timeout(60.0, connect=30.0)) as client:
                    resp = await client.get(url, auth=auth, headers=headers)
                    resp.raise_for_status()
                    data = resp.json()
                    return data.get("states") or []
            except Exception as e:
                errors.append(e)
                if attempt < 1:
                    await asyncio.sleep(1)
                continue

    logger.warning("OpenSky'ye baglanilamadi. Denenen URL'ler: %s", urls)
    return None


def match_callsign(states, flight_number):
    clean = flight_number.strip().upper()
    for s in states:
        callsign = (s[1] or "").strip()
        if callsign == clean:
            return {
                "icao24": s[0],
                "callsign": s[1],
                "lat": s[6],
                "lon": s[5],
                "baro_altitude": s[7],
                "on_ground": s[8],
                "velocity": s[9],
            }
    return None


def estimate_minutes_to_arrival(lat, lon, velocity, dest_lat, dest_lon):
    if velocity is None or velocity <= 0:
        return None

    velocity_ms = velocity / 3.6  # km/h -> m/s

    R = 6_371_000
    phi1 = math.radians(lat)
    phi2 = math.radians(dest_lat)
    delta_phi = math.radians(dest_lat - lat)
    delta_lambda = math.radians(dest_lon - lon)

    a = (
        math.sin(delta_phi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    distance = R * c

    seconds = distance / velocity_ms
    return seconds / 60
