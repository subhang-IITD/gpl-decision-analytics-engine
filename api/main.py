"""FastAPI application exposing all engine sub-modules (brief 5.2).

Run:  uvicorn api.main:app --reload
Docs: http://localhost:8000/docs  (auto OpenAPI -- part of API documentation deliverable)
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from dataclasses import asdict, is_dataclass

from fastapi import FastAPI, HTTPException

from api.schemas import (
    CompetitorEventRequest,
    MixRequest,
    ParcelRequest,
    PhasingRequest,
    PriceSimRequest,
    PricingRequest,
)
from db.session import init_db
from models.land_valuation import value_parcel
from models.launch_pricing import optimal_launch_price, simulate_price
from models.monitoring import scan
from models.phasing import Unit, competitor_response, plan_phasing
from models.product_mix import optimise_mix

@asynccontextmanager
async def _lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(
    title="GPL Decision Analytics Engine",
    version="1.0.0",
    description="AI-powered land valuation, product mix, pricing, phasing & competitive monitoring.",
    lifespan=_lifespan,
)


def _ser(obj):
    if is_dataclass(obj):
        return {k: _ser(v) for k, v in asdict(obj).items()}
    if isinstance(obj, list):
        return [_ser(x) for x in obj]
    if isinstance(obj, dict):
        return {k: _ser(v) for k, v in obj.items()}
    return obj


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/api/v1/land-valuation")
def land_valuation(req: ParcelRequest) -> dict:
    overrides = req.cost_overrides.model_dump(exclude_none=True) if req.cost_overrides else None
    result = value_parcel(req.lat, req.lng, req.area_acres, req.fsi,
                          cost_overrides=overrides, radius_km=req.radius_km)
    return _ser(result)


@app.post("/api/v1/product-mix")
def product_mix(req: MixRequest) -> dict:
    result = optimise_mix(req.lat, req.lng, req.area_acres, req.fsi,
                          saleable_ratio=req.saleable_ratio, override_mix=req.override_mix)
    return _ser(result)


@app.post("/api/v1/launch-pricing")
def launch_pricing(req: PricingRequest) -> dict:
    result = optimal_launch_price(
        req.lat, req.lng, req.total_units, req.min_units_m1, req.min_units_m3,
        req.min_units_m6, req.max_months_to_sellout, req.instinct_price)
    return _ser(result)


@app.post("/api/v1/launch-pricing/simulate")
def price_sim(req: PriceSimRequest) -> dict:
    return simulate_price(req.lat, req.lng, req.total_units, req.price)


@app.post("/api/v1/phasing")
def phasing(req: PhasingRequest) -> dict:
    units = [Unit(u.unit_id, u.config_type, u.floor, u.facing, u.base_psf, u.amenity_facing) for u in req.units]
    if not units:
        raise HTTPException(400, "At least one unit is required.")
    return _ser(plan_phasing(units, req.launch_psf, req.drawdown))


@app.post("/api/v1/phasing/competitor-response")
def competitor(req: CompetitorEventRequest) -> dict:
    return competitor_response(req.event, req.phase1_absorption_per_month)


@app.post("/api/v1/monitoring/scan")
def monitoring_scan(deliver_alerts: bool = False) -> dict:
    raised = scan(deliver_alerts=deliver_alerts)
    return {"alerts": raised, "count": len(raised)}
