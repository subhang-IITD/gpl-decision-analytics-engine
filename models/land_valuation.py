"""Sub-module 1: Land Valuation Engine (brief 2.1, 4.2, 4.4).

Given a parcel, output the justifiable land price per sqft of land area across
base / bull / bear scenarios, each with a Monte Carlo confidence band. Every
number is explainable: the result carries the comparables, the demand-intensity
breakdown, the residual-value line items, and the assumptions per scenario.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from config.defaults import (
    MC_CONFIDENCE_LEVELS,
    MC_DEFAULT_RANGES,
    MONTE_CARLO_RUNS,
    SCENARIO_ADJUSTMENTS,
)
from models.market_data import (
    Comparable,
    demand_intensity_score,
    get_comparables,
    get_micro_market_config,
    infrastructure_score,
    nearest_micro_market,
    weighted_avg_psf,
)

# acre -> sqft
SQFT_PER_ACRE = 43_560.0


@dataclass
class ResidualLineItems:
    projected_realisation_psf_saleable: float
    saleable_ratio: float
    realisation_psf_builtup: float
    construction_cost_psf: float
    finance_cost_psf: float
    approvals_cost_psf: float
    marketing_cost_psf: float
    margin_psf: float
    max_land_price_psf_builtup: float
    max_land_price_psf_land: float
    fsi: float


@dataclass
class ScenarioResult:
    name: str
    label: str
    realisation_multiplier: float
    residual: ResidualLineItems
    assumptions: list[str]
    conditions_to_materialise: list[str]
    mc_confidence_prices: dict          # confidence level -> land price psf (land area)
    mc_distribution_summary: dict


@dataclass
class ValuationResult:
    parcel: dict
    micro_market: str | None
    comparables_count: int
    base_realisation_psf: float
    weighted_avg_comparable_psf: float | None
    infra_score: float
    infra_breakdown: dict
    demand_intensity: float
    demand_components: dict
    scenarios: dict                     # name -> ScenarioResult
    data_quality_flag: str | None
    model_cross_check: dict = field(default_factory=dict)  # XGBoost/GBR prediction + CV metrics
    trust: dict = field(default_factory=dict)
    explanation: list[str] = field(default_factory=list)


def _residual_value(realisation_psf_saleable: float, costs: dict, fsi: float, min_margin: float) -> ResidualLineItems:
    """Brief 4.2 residual land value, expressed per sqft of LAND area.

    Per sqft of land, FSI sqft of built-up area is constructed, of which
    saleable_ratio is saleable. Realisation accrues on the saleable area;
    construction/finance/approvals/marketing accrue on the built-up area.
    The residual after costs and margin is the supportable land price.
    """
    saleable_ratio = costs["saleable_ratio"]
    builtup_per_land = fsi                      # sqft built-up per sqft land
    saleable_per_land = fsi * saleable_ratio    # sqft saleable per sqft land

    # Gross realisation per sqft of land
    gdv_per_land = realisation_psf_saleable * saleable_per_land

    # Costs per sqft of land (built-up basis)
    construction_per_land = costs["construction_cost_per_sqft"] * builtup_per_land
    avg_factor = costs.get("finance_avg_outstanding_factor", 0.5)
    finance_per_land = (
        construction_per_land * costs["finance_cost_rate_annual"]
        * costs["project_duration_months"] / 12.0 * avg_factor
    )
    approvals_per_land = costs["approvals_cost_per_sqft"] * builtup_per_land
    marketing_per_land = costs["marketing_cost_per_sqft"] * builtup_per_land
    margin_per_land = gdv_per_land * min_margin

    max_land_psf_land = (
        gdv_per_land - construction_per_land - finance_per_land
        - approvals_per_land - marketing_per_land - margin_per_land
    )
    return ResidualLineItems(
        projected_realisation_psf_saleable=round(realisation_psf_saleable, 1),
        saleable_ratio=saleable_ratio,
        realisation_psf_builtup=round(gdv_per_land, 1),         # GDV per sqft land
        construction_cost_psf=round(construction_per_land, 1),
        finance_cost_psf=round(finance_per_land, 1),
        approvals_cost_psf=round(approvals_per_land, 1),
        marketing_cost_psf=round(marketing_per_land, 1),
        margin_psf=round(margin_per_land, 1),
        max_land_price_psf_builtup=round(max_land_psf_land / fsi, 1),
        max_land_price_psf_land=round(max_land_psf_land, 1),
        fsi=fsi,
    )


def _monte_carlo(base_realisation: float, multiplier: float, costs: dict, fsi: float,
                 min_margin: float, ranges: dict, runs: int, seed: int = 42) -> tuple[dict, dict]:
    """Brief 4.4: 10k sims varying construction cost, realisation, absorption."""
    rng = np.random.default_rng(seed)
    constr = costs["construction_cost_per_sqft"] * (1 + rng.uniform(-ranges["construction_cost_pct"], ranges["construction_cost_pct"], runs))
    real = base_realisation * multiplier * (1 + rng.uniform(-ranges["realisation_price_pct"], ranges["realisation_price_pct"], runs))
    # absorption affects finance duration: slower absorption -> longer hold -> higher finance cost
    absorption_factor = 1 + rng.uniform(-ranges["absorption_rate_pct"], ranges["absorption_rate_pct"], runs)
    duration = costs["project_duration_months"] / np.clip(absorption_factor, 0.4, 1.6)

    saleable_ratio = costs["saleable_ratio"]
    gdv_per_land = real * fsi * saleable_ratio
    constr_per_land = constr * fsi
    avg_factor = costs.get("finance_avg_outstanding_factor", 0.5)
    finance_per_land = constr_per_land * costs["finance_cost_rate_annual"] * duration / 12.0 * avg_factor
    margin = gdv_per_land * min_margin
    land_psf_land = (
        gdv_per_land - constr_per_land - finance_per_land
        - costs["approvals_cost_per_sqft"] * fsi
        - costs["marketing_cost_per_sqft"] * fsi - margin
    )

    # Confidence: price the market supports with X% confidence = X-th percentile
    # from the top (i.e. 80% confidence -> value exceeded in 80% of sims -> 20th pct).
    conf_prices = {f"{int(c*100)}%": round(float(np.percentile(land_psf_land, (1 - c) * 100)), 0) for c in MC_CONFIDENCE_LEVELS}
    summary = {
        "mean": round(float(land_psf_land.mean()), 0),
        "p10": round(float(np.percentile(land_psf_land, 10)), 0),
        "p50": round(float(np.percentile(land_psf_land, 50)), 0),
        "p90": round(float(np.percentile(land_psf_land, 90)), 0),
        "std": round(float(land_psf_land.std()), 0),
        "runs": runs,
    }
    return conf_prices, summary


def value_parcel(
    lat: float,
    lng: float,
    area_acres: float,
    fsi: float,
    cost_overrides: dict | None = None,
    radius_km: float = 3.0,
    mc_runs: int = MONTE_CARLO_RUNS,
) -> ValuationResult:
    mm = nearest_micro_market(lat, lng)
    mm_id = mm.id if mm else None
    infra_w, base_costs, min_margin = get_micro_market_config(mm_id) if mm_id else (None, None, 0.20)
    costs = dict(base_costs or {})
    if cost_overrides:
        costs.update({k: v for k, v in cost_overrides.items() if v is not None})

    comps = get_comparables(lat, lng, radius_km=radius_km)
    wavg = weighted_avg_psf(comps)
    base_realisation = wavg or 7600.0  # fall back to a default if no comps

    infra = infrastructure_score(lat, lng, weights=infra_w)
    infra_bull = infrastructure_score(lat, lng, weights=infra_w, include_planned=True)
    demand = demand_intensity_score(mm_id, lat, lng) if mm_id else None

    data_flag = None
    if len(comps) < 5:
        data_flag = (f"SPARSE DATA: only {len(comps)} comparable transactions within "
                     f"{radius_km}km. Confidence intervals widened; treat point estimates with caution.")

    scenarios: dict = {}
    for name, adj in SCENARIO_ADJUSTMENTS.items():
        mult = adj["realisation_multiplier"]
        # widen MC ranges under sparse data
        ranges = dict(MC_DEFAULT_RANGES)
        if data_flag:
            ranges = {k: v * 1.5 for k, v in ranges.items()}
        residual = _residual_value(base_realisation * mult, costs, fsi, min_margin)
        conf_prices, summary = _monte_carlo(base_realisation, mult, costs, fsi, min_margin, ranges, mc_runs)

        assumptions = [
            f"Projected realisation: Rs.{base_realisation*mult:,.0f}/sqft saleable ({adj['label']}).",
            f"Construction Rs.{costs['construction_cost_per_sqft']:,.0f}/sqft built-up; "
            f"finance {costs['finance_cost_rate_annual']*100:.0f}% over {costs['project_duration_months']} months "
            f"on {costs.get('finance_avg_outstanding_factor',0.5)*100:.0f}% avg outstanding.",
            f"Minimum margin {min_margin*100:.0f}% of GDV; saleable ratio {costs['saleable_ratio']*100:.0f}%.",
        ]
        if name == "bull":
            conditions = [
                f"Planned infrastructure materialises (infra score {infra.score:.2f} -> {infra_bull.score:.2f}).",
                "Demand continues current upward trajectory for ~18 months.",
            ]
        elif name == "bear":
            conditions = ["Absorption slows ~30% from current velocity.", "No new demand catalysts; possible supply overhang."]
        else:
            conditions = ["Current market conditions persist with no major shift in demand or supply."]

        scenarios[name] = ScenarioResult(
            name=name, label=adj["label"], realisation_multiplier=mult, residual=residual,
            assumptions=assumptions, conditions_to_materialise=conditions,
            mc_confidence_prices=conf_prices, mc_distribution_summary=summary,
        )

    # Independent ML cross-check on the realisation estimate (brief 5.2 XGBoost).
    model_cross_check: dict = {}
    try:
        from models.price_model import get_price_model
        pm = get_price_model()
        if pm.trained:
            pred = pm.predict(lat, lng, "3BHK", 1550, demand.score if demand else 0.5, mm_id)
            model_cross_check = {
                "backend": pm.backend, "predicted_psf_3bhk": round(pred, 0) if pred else None,
                "cv_r2": pm.cv_r2, "cv_mae_psf": pm.cv_mae, "n_rows": pm.n_rows,
                "vs_comparable_avg_pct": (round((pred / base_realisation - 1) * 100, 1)
                                          if pred and base_realisation else None),
                "note": "Independent gradient-boosted model; agreement with the comparable average raises confidence.",
            }
    except Exception as exc:
        model_cross_check = {"note": f"price model unavailable: {exc}"}

    from dataclasses import asdict
    from models.trust import compute_trust
    trust = compute_trust(sample_size=len(comps),
                          values=[c.price_per_sqft for c in comps] or None,
                          fit_r2=model_cross_check.get("cv_r2"))

    explanation = [
        f"Base realisation Rs.{base_realisation:,.0f}/sqft from recency+similarity-weighted average of {len(comps)} comparables within {radius_km}km.",
        f"Infrastructure score {infra.score:.2f} (metro/IT-park/highway/school/hospital proximity).",
    ]
    if demand:
        explanation.append(f"Demand-intensity score {demand.score:.2f} (velocity, overhang, jobs, infra).")
    if model_cross_check.get("predicted_psf_3bhk"):
        explanation.append(
            f"ML cross-check ({model_cross_check['backend']}, CV R2={model_cross_check['cv_r2']}): "
            f"Rs.{model_cross_check['predicted_psf_3bhk']:,.0f}/sqft "
            f"({model_cross_check['vs_comparable_avg_pct']:+.1f}% vs comparable avg).")
    explanation.append(f"Confidence: {trust.band} ({trust.score}). " + " ".join(trust.reasons[:2]))
    explanation.append("Residual land value = realisation - construction - finance - approvals - marketing - margin, scaled by FSI.")

    return ValuationResult(
        parcel={"lat": lat, "lng": lng, "area_acres": area_acres, "fsi": fsi,
                "land_area_sqft": round(area_acres * SQFT_PER_ACRE, 0)},
        micro_market=mm.name if mm else None,
        comparables_count=len(comps),
        base_realisation_psf=round(base_realisation, 1),
        weighted_avg_comparable_psf=round(wavg, 1) if wavg else None,
        infra_score=infra.score, infra_breakdown=infra.breakdown,
        demand_intensity=demand.score if demand else 0.0,
        demand_components=demand.components if demand else {},
        scenarios=scenarios, data_quality_flag=data_flag,
        model_cross_check=model_cross_check, trust=asdict(trust), explanation=explanation,
    )
