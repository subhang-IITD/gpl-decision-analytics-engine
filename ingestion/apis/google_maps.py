"""Google Maps Distance Matrix client (brief 3.1, 4.1).

Computes parcel->amenity distances for the infrastructure proximity score.
With a key: calls the real Distance Matrix API. Without a key: falls back to
haversine straight-line distance over POIs already in the warehouse, so the
proximity score is always computable.
"""
from __future__ import annotations

import math

from config import get_settings


def haversine_m(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    r = 6_371_000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lng2 - lng1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


class GoogleMapsClient:
    def __init__(self) -> None:
        self._key = get_settings().keys.google_maps_api_key

    @property
    def live(self) -> bool:
        return bool(self._key)

    def distance_m(self, origin: tuple[float, float], dest: tuple[float, float]) -> float:
        """Road distance in metres if a key is set, else straight-line."""
        if not self.live:
            return haversine_m(*origin, *dest)
        try:
            import requests

            resp = requests.get(
                "https://maps.googleapis.com/maps/api/distancematrix/json",
                params={
                    "origins": f"{origin[0]},{origin[1]}",
                    "destinations": f"{dest[0]},{dest[1]}",
                    "mode": "driving",
                    "key": self._key,
                },
                timeout=20,
            )
            resp.raise_for_status()
            element = resp.json()["rows"][0]["elements"][0]
            if element.get("status") == "OK":
                return float(element["distance"]["value"])
        except Exception:
            pass
        return haversine_m(*origin, *dest)
