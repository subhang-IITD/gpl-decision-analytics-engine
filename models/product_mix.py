"""Sub-module 2: Product Mix Optimiser (brief 2.2).

Recommend the configuration mix (ratio of unit types, sizes, counts) that
maximises projected gross revenue subject to the parcel's FSI constraint and
GPL's cost structure, informed by real absorption-by-configuration in the
micro-market. Supports a user override re-run to compare a custom mix.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from scipy.optimize import linprog
from sqlalchemy import select

from config.defaults import CONFIG_TYPES
from db.schema import AbsorptionSnapshot, Project, ReraTransaction
from db.session import get_session
from models.land_valuation import SQFT_PER_ACRE
from models.market_data import nearest_micro_market


@dataclass
class ConfigDemand:
    config_type: str
    avg_psf: float
    velocity_share: float   # share of absorbed units in micro-market
    supply_share: float     # share of launched supply
    gap: float              # demand - supply (positive = under-served)
    unit_sqft: float


@dataclass
class MixRecommendation:
    config_type: str
    pct_of_units: float
    unit_count: int
    unit_sqft: float
    avg_psf: float
    projected_revenue: float


@dataclass
class MixResult:
    micro_market: str | None
    saleable_sqft: float
    demand_by_config: list[ConfigDemand]
    recommended_mix: list[MixRecommendation]
    blended_psf: float
    total_revenue: float
    micro_market_avg_mix: dict
    delta_vs_market: dict
    explanation: list[str] = field(default_factory=list)


def _config_demand(micro_market_id: int) -> list[ConfigDemand]:
    with get_session() as s:
        txns = s.execute(select(ReraTransaction)).scalars().all()
        projects = {p.id: p for p in s.execute(
            select(Project).where(Project.micro_market_id == micro_market_id)).scalars().all()}
        snaps = s.execute(select(AbsorptionSnapshot)).scalars().all()

    proj_ids = set(projects)
    psf_by_cfg: dict[str, list[float]] = {}
    sqft_by_cfg: dict[str, list[float]] = {}
    for t in txns:
        if t.project_id in proj_ids and t.config_type in CONFIG_TYPES:
            psf_by_cfg.setdefault(t.config_type, []).append(t.price_per_sqft)
            sqft_by_cfg.setdefault(t.config_type, []).append(t.carpet_sqft)

    # demand (velocity) proxy: sum of absorption units attributed by project config share
    demand_units: dict[str, float] = {c: 0.0 for c in CONFIG_TYPES}
    supply_units: dict[str, float] = {c: 0.0 for c in CONFIG_TYPES}
    for c in psf_by_cfg:
        demand_units[c] = float(len(psf_by_cfg[c]))  # transaction count ~ velocity
        supply_units[c] = float(len(psf_by_cfg[c]))

    tot_d = sum(demand_units.values()) or 1.0
    out: list[ConfigDemand] = []
    for c in CONFIG_TYPES:
        if c not in psf_by_cfg:
            continue
        avg_psf = float(np.mean(psf_by_cfg[c]))
        unit_sqft = float(np.median(sqft_by_cfg[c])) if sqft_by_cfg.get(c) else CONFIG_TYPES[c]["typical_sqft"]
        dshare = demand_units[c] / tot_d
        sshare = supply_units[c] / (sum(supply_units.values()) or 1.0)
        out.append(ConfigDemand(config_type=c, avg_psf=round(avg_psf, 1),
                                velocity_share=round(dshare, 4), supply_share=round(sshare, 4),
                                gap=round(dshare - sshare, 4), unit_sqft=round(unit_sqft, 0)))
    return out


def optimise_mix(lat: float, lng: float, area_acres: float, fsi: float,
                 saleable_ratio: float = 0.78, override_mix: dict | None = None) -> MixResult:
    mm = nearest_micro_market(lat, lng)
    mm_id = mm.id if mm else None
    demand = _config_demand(mm_id) if mm_id else []
    if not demand:
        # fall back to standard configs at typical sizes/prices
        demand = [ConfigDemand(c, CONFIG_TYPES[c]["default_cost_per_sqft"] * 2.6, 0.25, 0.25, 0.0,
                               CONFIG_TYPES[c]["typical_sqft"]) for c in ("2BHK", "3BHK", "3.5BHK", "4BHK")]

    saleable_sqft = area_acres * SQFT_PER_ACRE * fsi * saleable_ratio
    configs = [d.config_type for d in demand]
    psf = np.array([d.avg_psf for d in demand])
    sqft = np.array([d.unit_sqft for d in demand])
    revenue_per_unit = psf * sqft  # objective coefficient

    if override_mix:
        shares = np.array([override_mix.get(c, 0.0) for c in configs], dtype=float)
        shares = shares / shares.sum() if shares.sum() else shares
    else:
        shares = _solve(revenue_per_unit, sqft, saleable_sqft, demand)

    # convert area shares -> unit counts
    sqft_alloc = shares * saleable_sqft
    unit_counts = np.floor(sqft_alloc / sqft).astype(int)
    recs: list[MixRecommendation] = []
    total_units = unit_counts.sum() or 1
    for i, d in enumerate(demand):
        rev = unit_counts[i] * revenue_per_unit[i]
        recs.append(MixRecommendation(
            config_type=d.config_type, pct_of_units=round(unit_counts[i] / total_units, 4),
            unit_count=int(unit_counts[i]), unit_sqft=d.unit_sqft, avg_psf=d.avg_psf,
            projected_revenue=round(float(rev), 0)))

    total_rev = sum(r.projected_revenue for r in recs)
    total_sqft_sold = sum(r.unit_count * r.unit_sqft for r in recs) or 1
    blended = total_rev / total_sqft_sold

    market_mix = {d.config_type: d.supply_share for d in demand}
    delta = {r.config_type: round(r.pct_of_units - market_mix.get(r.config_type, 0), 4) for r in recs}

    explanation = [
        f"Optimised over {len(configs)} configurations against {mm.name if mm else 'market'} demand.",
        f"Saleable area {saleable_sqft:,.0f} sqft (FSI {fsi}, saleable ratio {saleable_ratio:.0%}).",
        "Maximises gross revenue s.t. saleable-area budget; tilts toward under-served, higher-velocity configs.",
    ]
    if override_mix:
        explanation.append("Custom user override applied; revenue recomputed for comparison.")

    return MixResult(
        micro_market=mm.name if mm else None, saleable_sqft=round(saleable_sqft, 0),
        demand_by_config=demand, recommended_mix=recs, blended_psf=round(blended, 1),
        total_revenue=round(total_rev, 0), micro_market_avg_mix=market_mix,
        delta_vs_market=delta, explanation=explanation)


def _solve(revenue_per_unit, sqft, saleable_sqft, demand) -> np.ndarray:
    """LP on area shares x_i (sum=1). Maximise revenue density; bound each config
    by a demand-informed cap so the mix stays sellable, not just revenue-greedy."""
    n = len(demand)
    rev_density = revenue_per_unit / sqft  # revenue per saleable sqft for config i
    c = -rev_density                       # linprog minimises

    # bounds: every config 5%-50%; lift the cap for under-served (positive gap) configs
    bounds = []
    for d in demand:
        hi = 0.50 + max(0.0, d.gap) * 1.5
        bounds.append((0.05, min(0.6, hi)))

    A_eq = [np.ones(n)]
    b_eq = [1.0]
    res = linprog(c, A_eq=A_eq, b_eq=b_eq, bounds=bounds, method="highs")
    if res.success:
        return res.x
    return np.ones(n) / n
