import json
from pathlib import Path
from typing import Optional

_countries = None


def _load():
    global _countries
    if _countries is not None:
        return _countries
    path = Path(__file__).parent / "countries.geojson"
    with open(path) as f:
        _countries = json.load(f)
    return _countries


def get_country(lat: float, lon: float) -> Optional[str]:
    """Return country name for given lat/lon, or None if over water.
    Falls back to sampling nearby points for coastal accuracy.
    """
    data = _load()
    best = _match(data, lat, lon)
    if best:
        return best

    for dlat, dlon in [(0.05, 0), (-0.05, 0), (0, 0.05), (0, -0.05),
                        (0.1, 0), (-0.1, 0), (0, 0.1), (0, -0.1),
                        (0.2, 0), (-0.2, 0), (0, 0.2), (0, -0.2)]:
        best = _match(data, lat + dlat, lon + dlon)
        if best:
            return best

    return None


def _match(data: dict, lat: float, lon: float) -> Optional[str]:
    for feature in data["features"]:
        props = feature.get("properties") or {}
        name = props.get("ADMIN") or props.get("NAME")
        if not name:
            continue
        geom = feature.get("geometry")
        if not geom:
            continue
        if _geom_contains(geom, lat, lon):
            return name
    return None


def _geom_contains(geom: dict, lat: float, lon: float) -> bool:
    t = geom["type"]
    coords = geom["coordinates"]
    if t == "Polygon":
        return _polygon_contains(coords, lat, lon)
    if t == "MultiPolygon":
        return any(_polygon_contains(p, lat, lon) for p in coords)
    return False


def _polygon_contains(coords: list, lat: float, lon: float) -> bool:
    outer = coords[0]
    if not _ray_contains(outer, lat, lon):
        return False
    for hole in coords[1:]:
        if _ray_contains(hole, lat, lon):
            return False
    return True


def _ray_contains(ring: list, lat: float, lon: float) -> bool:
    inside = False
    j = len(ring) - 1
    for i in range(len(ring)):
        xi, yi = ring[i]
        xj, yj = ring[j]
        if ((yi > lat) != (yj > lat)) and (lon < (xj - xi) * (lat - yi) / (yj - yi) + xi):
            inside = not inside
        j = i
    return inside
