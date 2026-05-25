"""Unit tests for all model sub-modules and input validation."""
import pytest

from models.land_valuation import value_parcel
from models.launch_pricing import optimal_launch_price, simulate_price
from models.monitoring import scan
from models.phasing import Unit, competitor_response, plan_phasing
from models.product_mix import optimise_mix

LAT, LNG = 12.97, 80.22


# --- Sub-module 1: Land Valuation ---
def test_valuation_three_scenarios():
    r = value_parcel(LAT, LNG, area_acres=3.0, fsi=2.5)
    assert set(r.scenarios) == {"base", "bull", "bear"}
    base = r.scenarios["base"].residual.max_land_price_psf_land
    bull = r.scenarios["bull"].residual.max_land_price_psf_land
    bear = r.scenarios["bear"].residual.max_land_price_psf_land
    # bull >= base >= bear by construction (realisation multipliers)
    assert bull > base > bear


def test_valuation_monte_carlo_deterministic():
    r1 = value_parcel(LAT, LNG, 3.0, 2.5)
    r2 = value_parcel(LAT, LNG, 3.0, 2.5)
    assert r1.scenarios["base"].mc_confidence_prices == r2.scenarios["base"].mc_confidence_prices


def test_valuation_mc_confidence_ordering():
    r = value_parcel(LAT, LNG, 3.0, 2.5)
    cp = r.scenarios["base"].mc_confidence_prices
    # higher confidence -> lower supportable price
    assert cp["80%"] <= cp["50%"] <= cp["20%"]


def test_valuation_explainable():
    r = value_parcel(LAT, LNG, 3.0, 2.5)
    assert r.explanation and r.infra_breakdown and r.comparables_count > 0


# --- Sub-module 2: Product Mix ---
def test_mix_shares_and_revenue():
    r = optimise_mix(LAT, LNG, 3.0, 2.5)
    assert r.recommended_mix
    total_pct = sum(m.pct_of_units for m in r.recommended_mix)
    assert 0.95 <= total_pct <= 1.05
    assert r.total_revenue > 0


def test_mix_override_runs():
    r = optimise_mix(LAT, LNG, 3.0, 2.5, override_mix={"2BHK": 50, "3BHK": 50})
    assert r.recommended_mix


# --- Sub-module 3: Launch Pricing ---
def test_pricing_demand_curve():
    r = optimal_launch_price(LAT, LNG, total_units=200)
    assert r.optimal_launch_psf > 0
    assert r.months_to_sellout > 0
    if r.regression.get("status") == "ok":
        # best-fit form is chosen among linear/quadratic/exponential
        assert r.regression["form"] in {"linear", "quadratic", "exponential"}
        assert 0.0 <= r.regression["r2"] <= 1.0


def test_demand_curve_downward_sloping():
    # higher price should not increase predicted velocity across the comparable range
    from models.launch_pricing import _demand_points, fit_demand_curve
    import numpy as np
    pts = _demand_points(LAT, LNG)
    if len(pts) >= 5:
        prices = np.array([p.price_per_sqft for p in pts])
        curve = fit_demand_curve(prices, np.array([p.units_per_month for p in pts]))
        lo, hi = curve.predict(prices.min()), curve.predict(prices.max())
        assert lo >= hi - 1e-6  # demand at low price >= demand at high price


def test_price_simulation():
    sim = simulate_price(LAT, LNG, 200, 8000)
    assert sim["projected_velocity"] >= 0


def test_pricing_sparse_flag_remote_location():
    # far from any comparable -> sparse data flagged, no false precision
    r = optimal_launch_price(28.6, 77.2, total_units=200)
    assert r.sparse_data is True


# --- Sub-module 4: Phasing ---
def test_phasing_tiers_and_premium():
    units = [Unit(f"U{f}-{w}", "3BHK", f, fac, 7500 + f * 50, amenity_facing=(f < 5))
             for f in range(1, 21) for w, fac in enumerate(["E", "W", "N", "S"])]
    r = plan_phasing(units, launch_psf=7500,
                     drawdown=[{"phase": 1, "amount_inr": 1e8}])
    assert len(r.phases) == 3
    premium = next(p for p in r.phases if p.tier == "premium")
    p1 = next(p for p in r.phases if p.tier == "phase1")
    assert premium.recommended_psf > p1.recommended_psf  # premium uplift


def test_competitor_response_logic():
    assert "HOLD" in competitor_response("competitor price drop", 20)["recommendation"]


# --- Sub-module 5: Monitoring ---
def test_monitoring_scan_runs():
    raised = scan(deliver_alerts=False)
    assert isinstance(raised, list)
    kinds = {a["kind"] for a in raised}
    assert kinds.issubset({"new_filing", "price_change", "absorption", "gov"})


# --- Price model (XGBoost / GBR) ---
def test_price_model_trains_and_predicts():
    from models.price_model import get_price_model
    pm = get_price_model()
    if pm.trained:
        assert pm.cv_r2 is not None
        assert pm.backend in {"xgboost", "sklearn_gbr"}
        pred = pm.predict(LAT, LNG, "3BHK", 1550, 0.5, None)
        assert pred is None or pred > 0


# --- Trust score ---
def test_trust_score_bands():
    from models.trust import compute_trust
    strong = compute_trust(sample_size=40, values=[7500, 7600, 7550, 7580], fit_r2=0.7)
    weak = compute_trust(sample_size=2, values=[5000, 15000], fit_r2=0.05)
    assert strong.score > weak.score


def test_valuation_has_trust_and_crosscheck():
    r = value_parcel(LAT, LNG, 3.0, 2.5)
    assert r.trust and "band" in r.trust
    assert isinstance(r.model_cross_check, dict)
