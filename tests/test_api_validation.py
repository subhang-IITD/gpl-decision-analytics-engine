"""API boundary validation: impossible inputs rejected with 422 (brief 5.1)."""
from fastapi.testclient import TestClient

from api.main import app

client = TestClient(app)


def test_health():
    assert client.get("/health").json() == {"status": "ok"}


def test_valuation_ok():
    r = client.post("/api/v1/land-valuation", json={"lat": 12.97, "lng": 80.22, "area_acres": 3.0, "fsi": 2.5})
    assert r.status_code == 200
    assert "scenarios" in r.json()


def test_reject_excessive_fsi():
    r = client.post("/api/v1/land-valuation", json={"lat": 12.97, "lng": 80.22, "area_acres": 3.0, "fsi": 99})
    assert r.status_code == 422


def test_reject_negative_margin():
    r = client.post("/api/v1/land-valuation",
                    json={"lat": 12.97, "lng": 80.22, "area_acres": 3.0, "fsi": 2.5,
                          "cost_overrides": {"min_margin_pct_of_gdv": -0.1}})
    assert r.status_code == 422


def test_reject_zero_area():
    r = client.post("/api/v1/land-valuation", json={"lat": 12.97, "lng": 80.22, "area_acres": 0, "fsi": 2.5})
    assert r.status_code == 422


def test_pricing_endpoint():
    r = client.post("/api/v1/launch-pricing", json={"lat": 12.97, "lng": 80.22, "total_units": 200})
    assert r.status_code == 200
    assert r.json()["optimal_launch_psf"] > 0


def test_phasing_requires_units():
    r = client.post("/api/v1/phasing", json={"units": [], "launch_psf": 7500})
    assert r.status_code in (400, 422)
