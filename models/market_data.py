"""Shared market-data access used by all model sub-modules.

Centralises: comparable-transaction selection (radius/recency/similarity),
infrastructure proximity score, and demand-intensity score. Keeping these in
one place means every sub-module computes them identically and the data
dictionary / model-logic docs describe them once.
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

from sqlalchemy import select

from config.defaults import (
    DEFAULT_INFRA_WEIGHTS,
    DEFAULT_LOOKBACK_MONTHS,
    DEMAND_INTENSITY_WEIGHTS,
    proximity_score,
)
from db.schema import (
    AbsorptionSnapshot,
    JobSignal,
    MicroMarket,
    MicroMarketConfig,
    PointOfInterest,
    Project,
    ReraTransaction,
)
from db.session import get_session
from ingestion.apis.google_maps import GoogleMapsClient, haversine_m


@dataclass
class Comparable:
    txn_id: int
    config_type: str
    price_per_sqft: float
    carpet_sqft: float
    distance_km: float
    months_old: float
    similarity: float
    weight: float


def _months_between(d: dt.date, now: dt.date | None = None) -> float:
    now = now or dt.date.today()
    if isinstance(d, dt.datetime):
        d = d.date()
    return max(0.0, (now - d).days / 30.4)


def get_comparables(
    lat: float,
    lng: float,
    radius_km: float,
    lookback_months: int = DEFAULT_LOOKBACK_MONTHS,
    config_filter: str | None = None,
) -> list[Comparable]:
    """Select comparable transactions, weighted by recency and project similarity.

    weight = recency_weight * similarity. recency_weight decays linearly over the
    lookback window; similarity blends distance closeness and config match.
    """
    cutoff = dt.date.today() - dt.timedelta(days=int(lookback_months * 30.4))
    out: list[Comparable] = []
    with get_session() as s:
        rows = s.execute(select(ReraTransaction)).scalars().all()
        for t in rows:
            tdate = t.txn_date.date() if isinstance(t.txn_date, dt.datetime) else t.txn_date
            if tdate < cutoff:
                continue
            dist_km = haversine_m(lat, lng, t.lat, t.lng) / 1000.0
            if dist_km > radius_km:
                continue
            if config_filter and t.config_type != config_filter:
                continue
            months_old = _months_between(t.txn_date)
            recency_w = max(0.05, 1.0 - months_old / lookback_months)
            dist_sim = max(0.0, 1.0 - dist_km / radius_km)
            cfg_sim = 1.0 if (config_filter is None or t.config_type == config_filter) else 0.5
            similarity = 0.6 * dist_sim + 0.4 * cfg_sim
            out.append(Comparable(
                txn_id=t.id, config_type=t.config_type, price_per_sqft=t.price_per_sqft,
                carpet_sqft=t.carpet_sqft, distance_km=round(dist_km, 3),
                months_old=round(months_old, 1), similarity=round(similarity, 3),
                weight=round(recency_w * similarity, 4),
            ))
    return out


def weighted_avg_psf(comps: list[Comparable]) -> float | None:
    if not comps:
        return None
    wsum = sum(c.weight for c in comps)
    if wsum == 0:
        return None
    return sum(c.price_per_sqft * c.weight for c in comps) / wsum


@dataclass
class InfraScore:
    score: float
    weights: dict
    breakdown: dict  # category -> {nearest_m, proximity, contribution}


def infrastructure_score(
    lat: float, lng: float, weights: dict | None = None, include_planned: bool = False
) -> InfraScore:
    """Brief 4.1: weighted sum of per-amenity proximity scores."""
    weights = weights or dict(DEFAULT_INFRA_WEIGHTS)
    gmaps = GoogleMapsClient()
    breakdown: dict = {}
    with get_session() as s:
        pois = s.execute(select(PointOfInterest)).scalars().all()
    for category, w in weights.items():
        candidates = [p for p in pois if p.category == category and (include_planned or not p.planned)]
        if not candidates:
            breakdown[category] = {"nearest_m": None, "proximity": 0.0, "weight": w, "contribution": 0.0}
            continue
        nearest_m = min(gmaps.distance_m((lat, lng), (p.lat, p.lng)) for p in candidates)
        prox = proximity_score(nearest_m)
        breakdown[category] = {
            "nearest_m": round(nearest_m, 1), "proximity": prox,
            "weight": w, "contribution": round(prox * w, 4),
        }
    score = sum(b["contribution"] for b in breakdown.values())
    return InfraScore(score=round(score, 4), weights=weights, breakdown=breakdown)


@dataclass
class DemandIntensity:
    score: float
    components: dict


def demand_intensity_score(micro_market_id: int, lat: float, lng: float, weights: dict | None = None) -> DemandIntensity:
    """Brief 2.1: blend absorption velocity, inventory overhang (inverted),
    job growth, and infrastructure into a 0-1 demand-intensity score."""
    with get_session() as s:
        projects = s.execute(
            select(Project).where(Project.micro_market_id == micro_market_id)
        ).scalars().all()
        snaps = s.execute(select(AbsorptionSnapshot)).scalars().all()
        jobs = s.execute(
            select(JobSignal).where(JobSignal.micro_market_id == micro_market_id)
        ).scalars().all()

    # absorption velocity: median recent units/month, normalised to 0-1 (cap 30/mo)
    recent_vel = [sn.units_sold_in_month for sn in snaps]
    velocity = (sorted(recent_vel)[len(recent_vel) // 2] if recent_vel else 0)
    velocity_norm = min(1.0, velocity / 30.0)

    # inventory overhang: unsold % across projects; invert (low overhang -> high score)
    overhangs = [1 - (p.pct_sold or 0) for p in projects if p.pct_sold is not None]
    overhang = sum(overhangs) / len(overhangs) if overhangs else 0.5
    overhang_score = 1.0 - overhang

    # job growth: slope of postings over time, normalised
    job_growth = 0.5
    if len(jobs) >= 2:
        ordered = sorted(jobs, key=lambda j: j.as_of)
        first, last = ordered[0].active_postings, ordered[-1].active_postings
        if first > 0:
            job_growth = max(0.0, min(1.0, (last - first) / first / 0.5))

    infra = infrastructure_score(lat, lng).score

    w = weights or DEMAND_INTENSITY_WEIGHTS
    components = {
        "absorption_velocity": {"raw": velocity, "norm": round(velocity_norm, 3), "weight": w["absorption_velocity"]},
        "inventory_overhang": {"raw_overhang_pct": round(overhang, 3), "norm": round(overhang_score, 3), "weight": w["inventory_overhang"]},
        "job_growth": {"norm": round(job_growth, 3), "weight": w["job_growth"]},
        "infrastructure": {"norm": round(infra, 3), "weight": w["infrastructure"]},
    }
    score = (
        velocity_norm * w["absorption_velocity"]
        + overhang_score * w["inventory_overhang"]
        + job_growth * w["job_growth"]
        + infra * w["infrastructure"]
    )
    return DemandIntensity(score=round(score, 4), components=components)


def get_micro_market_config(micro_market_id: int) -> tuple[dict, dict, float]:
    """Return (infra_weights, cost_assumptions, min_margin) for a micro-market."""
    from config.defaults import DEFAULT_COST_ASSUMPTIONS

    with get_session() as s:
        cfg = s.execute(
            select(MicroMarketConfig).where(MicroMarketConfig.micro_market_id == micro_market_id)
        ).scalar_one_or_none()
        if cfg:
            return cfg.infra_weights, cfg.cost_assumptions, cfg.min_margin_pct_of_gdv
    return dict(DEFAULT_INFRA_WEIGHTS), dict(DEFAULT_COST_ASSUMPTIONS), DEFAULT_COST_ASSUMPTIONS["min_margin_pct_of_gdv"]


def nearest_micro_market(lat: float, lng: float) -> MicroMarket | None:
    with get_session() as s:
        markets = s.execute(select(MicroMarket)).scalars().all()
        if not markets:
            return None
        best = min(markets, key=lambda m: haversine_m(lat, lng, m.center_lat, m.center_lng))
        s.expunge(best)
        return best
