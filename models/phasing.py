"""Sub-module 4: Phased Inventory Release Planner (brief 2.4).

Score each unit's saleability (floor, facing, amenity proximity, configuration,
price point), recommend a Phase-1 release of high-velocity units to set an
anchor, hold premium inventory until 40% absorption for a 12-18% uplift, emit
measurable release triggers, map phases to the construction drawdown schedule,
and react to competitor moves.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from config.defaults import (
    PREMIUM_HOLD_ABSORPTION_THRESHOLD,
    PREMIUM_RELEASE_UPLIFT_RANGE,
    SALEABILITY_WEIGHTS,
)

PREMIUM_FACINGS = {"E", "NE", "N"}
AMENITY_FLOORS = range(2, 6)  # low-mid floors nearest podium amenities


@dataclass
class Unit:
    unit_id: str
    config_type: str
    floor: int
    facing: str
    base_psf: float
    amenity_facing: bool = False


@dataclass
class ScoredUnit:
    unit_id: str
    config_type: str
    floor: int
    facing: str
    saleability: float
    tier: str            # phase1 | mid | premium
    base_psf: float


@dataclass
class PhasePlan:
    phase: int
    tier: str
    unit_ids: list[str]
    count: int
    recommended_psf: float
    release_trigger: str


@dataclass
class PhasingResult:
    total_units: int
    scored_units: list[ScoredUnit]
    phases: list[PhasePlan]
    cashflow_alignment: list[dict]
    explanation: list[str] = field(default_factory=list)


def _floor_score(floor: int, max_floor: int) -> float:
    # mid floors most liquid; very low and penthouse less so (but penthouse = premium)
    rel = floor / max(1, max_floor)
    if rel >= 0.85:
        return 0.55  # top floors: premium but slower velocity
    if 0.30 <= rel <= 0.70:
        return 1.0
    return 0.75


def _saleability(u: Unit, max_floor: int, median_psf: float) -> float:
    w = SALEABILITY_WEIGHTS
    floor_s = _floor_score(u.floor, max_floor)
    facing_s = 1.0 if u.facing in PREMIUM_FACINGS else 0.7
    amenity_s = 1.0 if u.amenity_facing else 0.8
    config_s = {"2BHK": 1.0, "3BHK": 0.95, "3.5BHK": 0.85, "4BHK": 0.7, "PLOT": 0.9}.get(u.config_type, 0.85)
    price_s = max(0.3, min(1.0, median_psf / u.base_psf)) if u.base_psf else 0.8
    return round(floor_s * w["floor_level"] + facing_s * w["facing"] + amenity_s * w["amenity_proximity"]
                 + config_s * w["configuration"] + price_s * w["price_point"], 4)


def plan_phasing(units: list[Unit], launch_psf: float, drawdown: list[dict] | None = None) -> PhasingResult:
    if not units:
        return PhasingResult(0, [], [], [], ["No units provided."])
    max_floor = max(u.floor for u in units)
    median_psf = sorted(u.base_psf for u in units)[len(units) // 2]

    scored = []
    for u in units:
        s = _saleability(u, max_floor, median_psf)
        is_premium = (u.floor / max_floor >= 0.85) or u.facing in PREMIUM_FACINGS or u.config_type in ("4BHK", "3.5BHK")
        tier = "premium" if is_premium and s < 0.9 else ("phase1" if s >= 0.85 else "mid")
        scored.append(ScoredUnit(u.unit_id, u.config_type, u.floor, u.facing, s, tier, u.base_psf))

    scored.sort(key=lambda x: x.saleability, reverse=True)
    phase1 = [u for u in scored if u.tier == "phase1"]
    mid = [u for u in scored if u.tier == "mid"]
    premium = [u for u in scored if u.tier == "premium"]

    uplift_lo, uplift_hi = PREMIUM_RELEASE_UPLIFT_RANGE
    premium_psf = round(launch_psf * (1 + (uplift_lo + uplift_hi) / 2), 0)

    phases = [
        PhasePlan(1, "phase1", [u.unit_id for u in phase1], len(phase1), round(launch_psf, 0),
                  "Launch immediately to establish velocity & price anchor"),
        PhasePlan(2, "mid", [u.unit_id for u in mid], len(mid), round(launch_psf * 1.05, 0),
                  "Release when Phase-1 absorption >= 15 units/month for 2 consecutive months"),
        PhasePlan(3, "premium", [u.unit_id for u in premium], len(premium), premium_psf,
                  f"Hold until >= {PREMIUM_HOLD_ABSORPTION_THRESHOLD:.0%} total absorption; "
                  f"then release at {uplift_lo:.0%}-{uplift_hi:.0%} premium"),
    ]

    cashflow = []
    if drawdown:
        cum_units = 0
        for ph in phases:
            cum_units += ph.count
            milestone = next((d for d in drawdown if d.get("phase") == ph.phase), None)
            cashflow.append({
                "phase": ph.phase,
                "expected_inflow_units": ph.count,
                "expected_revenue": round(ph.count * ph.recommended_psf * 1400, 0),
                "drawdown_milestone": milestone.get("amount_inr") if milestone else None,
                "covers_drawdown": (milestone is None) or (ph.count * ph.recommended_psf * 1400 >= milestone.get("amount_inr", 0)),
            })

    explanation = [
        f"Scored {len(units)} units on floor/facing/amenity/config/price (weights {SALEABILITY_WEIGHTS}).",
        f"Phase 1: {len(phase1)} high-velocity units (anchor). Phase 2: {len(mid)} mid units. "
        f"Phase 3: {len(premium)} premium units held to {PREMIUM_HOLD_ABSORPTION_THRESHOLD:.0%} absorption.",
        f"Premium release at Rs.{premium_psf:,.0f}/sqft ({uplift_lo:.0%}-{uplift_hi:.0%} over launch).",
    ]
    return PhasingResult(len(units), scored, phases, cashflow, explanation)


def competitor_response(event: str, phase1_absorption_per_month: float) -> dict:
    """Brief 2.4: react to a competitor launch / price drop in the micro-market."""
    e = event.lower()
    if "drop" in e or "discount" in e or "cut" in e:
        if phase1_absorption_per_month >= 15:
            rec = "HOLD pricing. Phase-1 velocity is strong; do not chase a competitor discount."
        else:
            rec = "CONSIDER tactical incentive (not headline price cut) to protect velocity; re-evaluate Phase-2 timing."
    elif "launch" in e or "new project" in e:
        rec = ("ACCELERATE Phase-2 release to capture demand before competitor absorbs it, "
               "if Phase-1 absorption supports it; else hold and differentiate.")
    else:
        rec = "MONITOR. No immediate pricing action; flag for next review cycle."
    return {"event": event, "phase1_velocity": phase1_absorption_per_month, "recommendation": rec}
