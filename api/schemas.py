"""Pydantic request/response schemas with input validation (brief 5.1).

Impossible inputs are rejected at the boundary with clear errors: FSI outside a
sane band, negative margins/costs, areas <= 0. The dashboard surfaces these.
"""
from __future__ import annotations

from pydantic import BaseModel, Field, field_validator

MAX_FSI = 6.0  # generous upper bound; per-plan limits enforced client-side too


class CostAssumptions(BaseModel):
    construction_cost_per_sqft: float | None = Field(None, gt=0)
    finance_cost_rate_annual: float | None = Field(None, ge=0, le=1)
    approvals_cost_per_sqft: float | None = Field(None, ge=0)
    marketing_cost_per_sqft: float | None = Field(None, ge=0)
    project_duration_months: int | None = Field(None, gt=0, le=120)
    saleable_ratio: float | None = Field(None, gt=0, le=1)
    min_margin_pct_of_gdv: float | None = Field(None, ge=0, le=0.9)


class ParcelRequest(BaseModel):
    lat: float = Field(..., ge=-90, le=90)
    lng: float = Field(..., ge=-180, le=180)
    area_acres: float = Field(..., gt=0, le=500)
    fsi: float = Field(..., gt=0, le=MAX_FSI)
    radius_km: float = Field(3.0, gt=0, le=25)
    cost_overrides: CostAssumptions | None = None


class MixRequest(ParcelRequest):
    saleable_ratio: float = Field(0.78, gt=0, le=1)
    override_mix: dict[str, float] | None = None


class PricingRequest(BaseModel):
    lat: float = Field(..., ge=-90, le=90)
    lng: float = Field(..., ge=-180, le=180)
    total_units: int = Field(..., gt=0, le=10000)
    min_units_m1: float = Field(8, ge=0)
    min_units_m3: float = Field(25, ge=0)
    min_units_m6: float = Field(50, ge=0)
    max_months_to_sellout: float = Field(36, gt=0, le=180)
    instinct_price: float | None = Field(None, gt=0)


class PriceSimRequest(BaseModel):
    lat: float
    lng: float
    total_units: int = Field(..., gt=0)
    price: float = Field(..., gt=0)


class UnitIn(BaseModel):
    unit_id: str
    config_type: str
    floor: int = Field(..., ge=0)
    facing: str
    base_psf: float = Field(..., gt=0)
    amenity_facing: bool = False


class PhasingRequest(BaseModel):
    units: list[UnitIn]
    launch_psf: float = Field(..., gt=0)
    drawdown: list[dict] | None = None


class CompetitorEventRequest(BaseModel):
    event: str
    phase1_absorption_per_month: float = Field(..., ge=0)
