"""PropEquity API client (brief 3.1).

Transaction-level price data, absorption velocity, inventory overhang. Written
against PropEquity's documented REST contract; reads the key from config. When
no subscription key is present, ingestion reads the equivalent data already in
the warehouse (seeded or previously fetched), so downstream models never block.
"""
from __future__ import annotations

from config import get_settings


class PropEquityClient:
    def __init__(self) -> None:
        cfg = get_settings().keys
        self._key = cfg.propequity_api_key
        self._base = cfg.propequity_base_url

    @property
    def live(self) -> bool:
        return bool(self._key)

    def _get(self, path: str, params: dict) -> dict:
        import requests

        resp = requests.get(
            f"{self._base}/{path.lstrip('/')}",
            headers={"Authorization": f"Bearer {self._key}", "Accept": "application/json"},
            params=params,
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()

    def projects_near(self, lat: float, lng: float, radius_km: float) -> list[dict]:
        """Return competitor projects with absorption/overhang near a point.

        Live mode hits PropEquity; otherwise returns [] and the caller uses the
        warehouse. Shape mirrors the warehouse Project + AbsorptionSnapshot.
        """
        if not self.live:
            return []
        data = self._get("projects", {"lat": lat, "lng": lng, "radius_km": radius_km})
        return data.get("projects", [])
