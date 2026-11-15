import csv
import io
import json
import time
from typing import Optional

import requests

from config import AIRPORTS_CACHE_PATH, AIRPORTS_DATA_URL

_CACHE_MAX_AGE_SECONDS = 30 * 24 * 3600
_CACHE_VERSION = 2
_airports_memory_cache: Optional[dict] = None


def _download_and_parse() -> dict:
    resp = requests.get(AIRPORTS_DATA_URL, timeout=15)
    resp.raise_for_status()
    result = {}
    reader = csv.reader(io.StringIO(resp.text))
    for row in reader:
        if len(row) < 8:
            continue
        icao = row[5].strip().upper()
        iata = row[4].strip().upper()
        if not icao or icao == "\\N":
            continue
        try:
            lat = float(row[6])
            lon = float(row[7])
        except ValueError:
            continue
        def _clean(val: str):
            return val if val and val != "\\N" else None
        entry = {"name": _clean(row[1]), "city": _clean(row[2]), "lat": lat, "lon": lon, "iata": iata if iata and iata != "\\N" else None}
        result[icao] = entry
        if entry["iata"] and entry["iata"] != icao:
            result[entry["iata"]] = entry
    return result


def _load_from_cache_file() -> Optional[dict]:
    try:
        with open(AIRPORTS_CACHE_PATH, "r", encoding="utf-8") as f:
            payload = json.load(f)
        if payload.get("_version") != _CACHE_VERSION:
            return None
        if time.time() - payload.get("_cached_at", 0) > _CACHE_MAX_AGE_SECONDS:
            return None
        return payload.get("data")
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def _save_to_cache_file(data: dict):
    with open(AIRPORTS_CACHE_PATH, "w", encoding="utf-8") as f:
        json.dump({"_cached_at": time.time(), "_version": _CACHE_VERSION, "data": data}, f)


def _ensure_loaded():
    global _airports_memory_cache
    if _airports_memory_cache is not None:
        return
    cached = _load_from_cache_file()
    if cached is not None:
        _airports_memory_cache = cached
        return
    data = _download_and_parse()
    _airports_memory_cache = data
    _save_to_cache_file(data)


def get_airport(code: str) -> Optional[dict]:
    _ensure_loaded()
    return _airports_memory_cache.get(code.strip().upper())


def _haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    import math
    R = 6371
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def find_nearest_airport(lat: float, lon: float, max_km: float = 150) -> Optional[dict]:
    _ensure_loaded()
    best = None
    best_dist = float("inf")
    seen = set()
    for entry in _airports_memory_cache.values():
        if not isinstance(entry, dict) or "lat" not in entry or "lon" not in entry:
            continue
        key = (entry["lat"], entry["lon"], entry.get("name"))
        if key in seen:
            continue
        seen.add(key)
        d = _haversine(lat, lon, entry["lat"], entry["lon"])
        if d < best_dist:
            best_dist = d
            best = entry
    if best and best_dist <= max_km:
        return {**best, "distance_km": round(best_dist, 1)}
    return None
