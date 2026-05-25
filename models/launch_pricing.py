"""Sub-module 3: Launch Pricing & Price Escalation (brief 2.3, 4.3).

Fit a demand curve (units/month vs price/sqft) from comparable projects, find
the launch price that maximises revenue subject to cash-flow (min units by
month 1/3/6) and time-to-sellout constraints, and emit a phased escalation
schedule. Flags sparse data (fewer than MIN_COMPARABLES_FOR_REGRESSION points)
rather than presenting false precision.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from sklearn.metrics import r2_score
from sqlalchemy import select

from config.defaults import (
    MIN_COMPARABLES_FOR_REGRESSION,
    PRICING_COMPARABLE_LOOKBACK_MONTHS,
    PRICING_COMPARABLE_RADIUS_KM,
)
from db.schema import AbsorptionSnapshot, Project
from db.session import get_session
from ingestion.apis.google_maps import haversine_m
from models.market_data import nearest_micro_market


@dataclass
class DemandPoint:
    price_per_sqft: float
    units_per_month: float
    project: str


@dataclass
class DemandCurve:
    """Fitted demand curve. `predict(price)` returns units/month (clipped >= 0).

    We try several economically-sensible forms and keep whichever explains the
    data best (highest R2), so the curve adapts to the real shape rather than
    forcing a straight line:
      - linear:      v = a + b*price
      - quadratic:   v = a + b*price + c*price^2   (captures curvature)
      - exponential: v = exp(a + b*price)          (constant-elasticity decay; v>0 always)
    """
    form: str
    r2: float
    n_points: int
    _coef: np.ndarray
    _kind: str

    def predict(self, price):
        p = np.asarray(price, dtype=float)
        if self._kind == "poly":
            deg = len(self._coef) - 1
            X = np.vander(p.ravel(), deg + 1, increasing=True)
            y = X @ self._coef
        else:  # exponential
            y = np.exp(self._coef[0] + self._coef[1] * p.ravel())
        y = np.clip(y, 0, None)
        return float(y[0]) if y.shape == (1,) else y

    def summary(self) -> dict:
        return {"status": "ok", "form": self.form, "r2": round(self.r2, 3), "n_points": self.n_points}


def fit_demand_curve(prices: np.ndarray, vels: np.ndarray) -> DemandCurve:
    """Fit linear, quadratic and exponential forms; return the best by R2."""
    candidates: list[DemandCurve] = []

    # Polynomial fits (degree 1 = linear, degree 2 = quadratic curvature)
    for deg, name in ((1, "linear"), (2, "quadratic")):
        if len(prices) <= deg + 1:
            continue
        coef = np.polyfit(prices, vels, deg)[::-1]  # ascending powers
        pred = np.vander(prices, deg + 1, increasing=True) @ coef
        candidates.append(DemandCurve(name, r2_score(vels, pred), len(prices), coef, "poly"))

    # Exponential fit: log(v) = a + b*price  (only on strictly positive velocities)
    pos = vels > 0
    if pos.sum() > 2:
        b, a = np.polyfit(prices[pos], np.log(vels[pos]), 1)
        pred = np.exp(a + b * prices)
        candidates.append(DemandCurve("exponential", r2_score(vels, pred), len(prices),
                                      np.array([a, b]), "exp"))

    if not candidates:
        # fall back to flat line at the mean
        return DemandCurve("linear", 0.0, len(prices), np.array([float(vels.mean()), 0.0]), "poly")
    return max(candidates, key=lambda c: c.r2)


@dataclass
class PhasePrice:
    phase: int
    month: int
    price_per_sqft: float
    escalation_trigger: str


@dataclass
class PricingResult:
    micro_market: str | None
    demand_points: list[DemandPoint]
    regression: dict                   # form, r2, n_points or "insufficient"
    optimal_launch_psf: float
    projected_velocity: float
    months_to_sellout: float
    total_units: int
    phased_schedule: list[PhasePrice]
    upside_vs_instinct: dict
    sparse_data: bool
    trust: dict = field(default_factory=dict)
    explanation: list[str] = field(default_factory=list)


def _demand_points(lat: float, lng: float) -> list[DemandPoint]:
    out: list[DemandPoint] = []
    with get_session() as s:
        projects = s.execute(select(Project)).scalars().all()
        snaps = s.execute(select(AbsorptionSnapshot)).scalars().all()
    by_proj: dict[int, list[AbsorptionSnapshot]] = {}
    for sn in snaps:
        by_proj.setdefault(sn.project_id, []).append(sn)
    for p in projects:
        if haversine_m(lat, lng, p.lat, p.lng) / 1000.0 > PRICING_COMPARABLE_RADIUS_KM:
            continue
        rows = by_proj.get(p.id, [])
        rows = [r for r in rows if r.units_sold_in_month and r.avg_price_per_sqft]
        if not rows:
            continue
        vel = float(np.mean([r.units_sold_in_month for r in rows]))
        price = float(np.mean([r.avg_price_per_sqft for r in rows]))
        if price > 100 and vel > 0:
            out.append(DemandPoint(price_per_sqft=round(price, 1), units_per_month=round(vel, 2), project=p.name))
    return out


def optimal_launch_price(lat: float, lng: float, total_units: int,
                         min_units_m1: float = 8, min_units_m3: float = 25, min_units_m6: float = 50,
                         max_months_to_sellout: float = 36, instinct_price: float | None = None) -> PricingResult:
    mm = nearest_micro_market(lat, lng)
    points = _demand_points(lat, lng)
    sparse = len(points) < MIN_COMPARABLES_FOR_REGRESSION

    prices = np.array([p.price_per_sqft for p in points]) if points else np.array([])
    vels = np.array([p.units_per_month for p in points]) if points else np.array([])

    curve: DemandCurve | None = None
    if sparse:
        # honest fallback: use raw points + interpolation if any, else market median
        ref_price = float(np.median(prices)) if len(prices) else 7000.0
        ref_vel = float(np.median(vels)) if len(vels) else 12.0
        regression = {"status": "insufficient", "n_points": len(points),
                      "note": f"Fewer than {MIN_COMPARABLES_FOR_REGRESSION} comparables; manual interpolation used."}
        r2 = None
        optimal = ref_price
        velocity = ref_vel
    else:
        # Compare like-with-like: fit velocity against price RELATIVE to the
        # local median, not absolute price. This removes the cross-segment bias
        # (a 15k luxury tower and a 5k mid project are no longer forced onto one
        # absolute curve) and isolates genuine price-sensitivity.
        median_price = float(np.median(prices))
        rel_prices = prices / median_price
        curve = fit_demand_curve(rel_prices, vels)
        regression = curve.summary()
        regression["normalised_to_median_psf"] = round(median_price, 0)
        r2 = curve.r2
        # search over absolute price grid, mapping back to relative for the curve
        grid = np.linspace(prices.min() * 0.9, prices.max() * 1.1, 400)
        vel_grid = curve.predict(grid / median_price)
        feasible = vel_grid >= min_units_m1                       # month-1 cash-flow floor
        rev_month = grid * vel_grid
        rev_month[~feasible] = -1
        with np.errstate(divide="ignore"):                        # sellout-time constraint
            months = np.where(vel_grid > 0, total_units / vel_grid, 1e9)
        rev_month[months > max_months_to_sellout] = -1
        optimal = float(grid[int(np.argmax(rev_month))]) if (rev_month > 0).any() else float(prices.mean())
        velocity = float(max(0.1, curve.predict(optimal / median_price)))

    months_to_sellout = round(total_units / velocity, 1) if velocity > 0 else float("inf")

    # phased escalation: +X% each phase as absorption milestones hit
    schedule = [
        PhasePrice(1, 0, round(optimal, 0), "Launch price"),
        PhasePrice(2, 3, round(optimal * 1.04, 0), f"If Month-3 absorption >= {min_units_m3} units"),
        PhasePrice(3, 6, round(optimal * 1.09, 0), f"If Month-6 absorption >= {min_units_m6} units"),
        PhasePrice(4, 12, round(optimal * 1.15, 0), "If cumulative absorption tracking above plan"),
    ]

    # upside vs instinct
    instinct = instinct_price or round(optimal * 0.93, 0)
    v_inst = max(0.1, curve.predict(instinct / median_price)) if curve is not None else velocity
    rev_opt = optimal * velocity * months_to_sellout if months_to_sellout != float("inf") else optimal * total_units
    rev_inst = instinct * v_inst * (total_units / v_inst if v_inst else months_to_sellout)
    upside = {
        "instinct_price": instinct, "model_price": round(optimal, 0),
        "instinct_velocity": round(v_inst, 1), "model_velocity": round(velocity, 1),
        "revenue_uplift_pct": round((rev_opt - rev_inst) / rev_inst * 100, 1) if rev_inst else 0.0,
        "note": "Model price trades some velocity for higher realisation; net revenue impact shown.",
    }

    explanation = [
        f"Demand curve from {len(points)} comparable projects within {PRICING_COMPARABLE_RADIUS_KM}km "
        f"(lookback {PRICING_COMPARABLE_LOOKBACK_MONTHS}mo).",
        ("Sparse data: showing raw points + interpolation, not a fitted curve."
         if sparse else f"Best-fit demand curve: {curve.form} (R2={r2:.2f}); "
                        f"revenue maximised under cash-flow + sellout constraints."),
        f"Optimal launch Rs.{optimal:,.0f}/sqft -> ~{velocity:.0f} units/month, sellout ~{months_to_sellout} months.",
    ]

    from dataclasses import asdict
    from models.trust import compute_trust
    trust = compute_trust(sample_size=len(points),
                          values=[p.price_per_sqft for p in points] or None,
                          fit_r2=r2)

    return PricingResult(
        micro_market=mm.name if mm else None, demand_points=points, regression=regression,
        optimal_launch_psf=round(optimal, 0), projected_velocity=round(velocity, 1),
        months_to_sellout=months_to_sellout, total_units=total_units, phased_schedule=schedule,
        upside_vs_instinct=upside, sparse_data=sparse, trust=asdict(trust), explanation=explanation)


def simulate_price(lat: float, lng: float, total_units: int, price: float) -> dict:
    """Scenario test: user sets a price, model projects velocity/sellout/revenue."""
    points = _demand_points(lat, lng)
    if len(points) < MIN_COMPARABLES_FOR_REGRESSION:
        vel = float(np.median([p.units_per_month for p in points])) if points else 12.0
    else:
        prices = np.array([p.price_per_sqft for p in points])
        vels = np.array([p.units_per_month for p in points])
        median_price = float(np.median(prices))
        vel = max(0.1, fit_demand_curve(prices / median_price, vels).predict(price / median_price))
    months = round(total_units / vel, 1) if vel > 0 else float("inf")
    avg_unit_sqft = 1400.0  # representative; revenue scales with total saleable area
    total_revenue = round(price * total_units * avg_unit_sqft, 0)
    return {"price_per_sqft": round(price, 0), "projected_velocity": round(vel, 1),
            "months_to_sellout": months, "total_revenue_est": total_revenue}
