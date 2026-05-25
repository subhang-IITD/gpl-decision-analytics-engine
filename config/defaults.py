"""Model default parameters and configurable weights.

Per the brief, infrastructure-score weights and many cost/margin defaults must
be configurable per micro-market. These are the system-wide defaults; the
warehouse stores per-micro-market overrides (see models.MicroMarketConfig).
"""
from __future__ import annotations

# --- Infrastructure proximity score (brief 4.1) ---
DEFAULT_INFRA_WEIGHTS = {
    "metro": 0.35,
    "it_park": 0.30,
    "highway": 0.15,
    "school": 0.10,
    "hospital": 0.10,
}

# Distance -> proximity score bands (metres), brief 4.1
PROXIMITY_BANDS = [
    (500, 1.0),
    (1000, 0.8),
    (2000, 0.5),
    (3000, 0.2),
]  # beyond last band -> 0.0


def proximity_score(distance_m: float) -> float:
    for threshold, score in PROXIMITY_BANDS:
        if distance_m < threshold:
            return score
    return 0.0


# --- Comparable selection (brief 2.1, 4.3) ---
DEFAULT_COMPARABLE_RADIUS_KM = 3.0
DEFAULT_LOOKBACK_MONTHS = 24
PRICING_COMPARABLE_RADIUS_KM = 5.0
PRICING_COMPARABLE_LOOKBACK_MONTHS = 36
MIN_COMPARABLES_FOR_REGRESSION = 5  # below this -> flag sparse data

# --- Residual land value cost defaults (Rs./sqft unless noted) ---
# These are "historical GPL averages" placeholders; GPL overrides via the form.
DEFAULT_COST_ASSUMPTIONS = {
    "construction_cost_per_sqft": 2800.0,
    "finance_cost_rate_annual": 0.12,
    "finance_avg_outstanding_factor": 0.5,  # avg drawn balance over the build
    "approvals_cost_per_sqft": 350.0,
    "marketing_cost_per_sqft": 250.0,
    "min_margin_pct_of_gdv": 0.20,
    "project_duration_months": 36,
    "saleable_ratio": 0.78,  # saleable / total built-up
}

# --- Scenario adjustments (brief 2.1) ---
SCENARIO_ADJUSTMENTS = {
    "base": {"realisation_multiplier": 1.00, "label": "Market as it is today"},
    "bull": {"realisation_multiplier": 1.18, "label": "Infra materialises, demand grows (18mo forward)"},
    "bear": {"realisation_multiplier": 0.85, "label": "Absorption slows 30% from current velocity"},
}

# --- Monte Carlo (brief 4.4) ---
MONTE_CARLO_RUNS = 10_000
MC_DEFAULT_RANGES = {
    "construction_cost_pct": 0.08,
    "absorption_rate_pct": 0.25,
    "realisation_price_pct": 0.10,
}
MC_CONFIDENCE_LEVELS = [0.80, 0.50, 0.20]

# --- Demand intensity score components (brief 2.1) ---
DEMAND_INTENSITY_WEIGHTS = {
    "absorption_velocity": 0.35,
    "inventory_overhang": 0.25,  # inverted: less overhang -> higher score
    "job_growth": 0.20,
    "infrastructure": 0.20,
}

# --- Phasing / saleability (brief 2.4) ---
SALEABILITY_WEIGHTS = {
    "floor_level": 0.25,
    "facing": 0.20,
    "amenity_proximity": 0.20,
    "configuration": 0.20,
    "price_point": 0.15,
}
PREMIUM_HOLD_ABSORPTION_THRESHOLD = 0.40  # 40% absorption before premium release
PREMIUM_RELEASE_UPLIFT_RANGE = (0.12, 0.18)  # 12-18% premium

# --- Competitive monitoring thresholds (brief 2.5) ---
PRICE_CHANGE_ALERT_PCT = 0.05
ABSORPTION_TIGHTENING_PCT = 0.80
NEW_FILING_RADIUS_KM = 3.0

# --- Standard unit configurations ---
CONFIG_TYPES = {
    "2BHK": {"typical_sqft": 1100, "default_cost_per_sqft": 2700},
    "3BHK": {"typical_sqft": 1550, "default_cost_per_sqft": 2800},
    "3.5BHK": {"typical_sqft": 1850, "default_cost_per_sqft": 2900},
    "4BHK": {"typical_sqft": 2400, "default_cost_per_sqft": 3050},
}
