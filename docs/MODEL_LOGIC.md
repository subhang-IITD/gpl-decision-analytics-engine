# Model Logic

How each sub-module computes its output. All numbers are explainable: every
result object carries the inputs, intermediate scores, and assumptions.

---

## Shared: comparable selection (`models/market_data.py`)

Transactions are comparable if within `radius_km` (default 3km) and inside the
lookback window (default 24 months). Each comparable gets:

```
recency_weight  = max(0.05, 1 − months_old / lookback_months)
distance_sim    = max(0, 1 − distance_km / radius_km)
config_sim      = 1.0 if config matches else 0.5
similarity      = 0.6·distance_sim + 0.4·config_sim
weight          = recency_weight · similarity
```

Weighted-average realisation: `Σ(price·weight) / Σ(weight)`.

---

## 1 · Land Valuation Engine (`models/land_valuation.py`)

### Infrastructure proximity score (brief 4.1)
```
proximity(d) = 1.0 (<500m) | 0.8 (500m–1km) | 0.5 (1–2km) | 0.2 (2–3km) | 0.0 (>3km)
InfraScore   = Σ_amenity  weight_amenity · proximity(nearest_distance_amenity)
default weights: metro 0.35, IT-park 0.30, highway 0.15, school 0.10, hospital 0.10
```
Weights are configurable per micro-market. Distances use Google Maps Distance
Matrix when a key is present, else haversine.

### Demand-intensity score (brief 2.1)
```
score = 0.35·velocity_norm + 0.25·(1−overhang) + 0.20·job_growth + 0.20·InfraScore
```
where `velocity_norm = min(1, median_units_per_month / 30)`, `overhang` = mean
unsold fraction across projects, `job_growth` = normalised posting-count slope.

### Residual land value (brief 4.2), per sqft of **land area**
```
builtup_per_land  = FSI
saleable_per_land = FSI · saleable_ratio
GDV_per_land      = realisation_psf_saleable · saleable_per_land
construction      = construction_psf · FSI
finance           = construction · finance_rate · (duration_months/12) · avg_outstanding_factor
approvals         = approvals_psf · FSI
marketing         = marketing_psf · FSI
margin            = GDV_per_land · min_margin_pct
MaxLandPrice/sqft = GDV_per_land − construction − finance − approvals − marketing − margin
```
`avg_outstanding_factor` (default 0.5) reflects that the construction loan is
drawn progressively, not fully on day one.

### Three scenarios (brief 2.1)
Run with realisation multipliers: **base ×1.00**, **bull ×1.18** (planned infra
materialises, 18-mo forward), **bear ×0.85** (absorption −30%). Each carries its
assumptions and the conditions that must hold to materialise.

### Monte Carlo (brief 4.4)
10,000 simulations sampling: construction ±8%, realisation ±10%, absorption ±25%
(absorption maps to finance duration: slower sales → longer hold → higher cost).
Outputs the supportable price at **80% / 50% / 20% confidence** = the
(1−c)·100th percentile of the simulated land-price distribution. Sparse data
widens the ranges ×1.5 and raises a flag.

---

## 2 · Product Mix Optimiser (`models/product_mix.py`)

For each configuration: average realisation (`avg_psf`), median unit size,
demand share (transaction velocity) and supply share → **gap = demand − supply**
(positive = under-served).

Linear program over area-share variables `x_i` (Σ=1):
```
maximise   Σ x_i · (revenue_per_unit_i / sqft_i)     # revenue per saleable sqft
s.t.       Σ x_i = 1
           0.05 ≤ x_i ≤ min(0.60, 0.50 + 1.5·max(0, gap_i))
```
The gap-based upper bound tilts the mix toward under-served, higher-velocity
configurations rather than being purely revenue-greedy. Shares convert to unit
counts over the saleable area (`area·FSI·saleable_ratio`). A user override mix
re-runs the revenue computation for side-by-side comparison.

---

## 3 · Launch Pricing & Escalation (`models/launch_pricing.py`)

Comparables: same micro-market, within 5km, launched within 36 months. For each
comparable project, plot mean **units/month vs mean price/sqft**.

Demand curve (≥5 points): `units_per_month = intercept + slope · price`
(OLS via scikit-learn `LinearRegression`; slope expected negative).

Optimal price = argmax over a price grid of `price · velocity(price)` subject to:
- month-1 velocity ≥ cash-flow minimum,
- time-to-sellout = `total_units / velocity ≤ max_months`.

**Sparse data (<5 points):** no regression — show raw points + manual
interpolation and flag, never false precision (brief 4.3).

Escalation schedule: Phase 1 launch, +4% at M3, +9% at M6, +15% at M12, each
gated by an absorption trigger. Upside-vs-instinct compares model price/velocity
to a gut price and reports net revenue impact.

---

## 4 · Phased Inventory Release Planner (`models/phasing.py`)

Saleability per unit (weights configurable):
```
saleability = 0.25·floor + 0.20·facing + 0.20·amenity + 0.20·config + 0.15·price
```
- floor: mid-floors score highest (most liquid); top floors lower velocity but premium.
- facing: E/NE/N premium; config: smaller units more liquid; price: relative to median.

Tiers: **phase1** (score ≥0.85, launch immediately to set anchor), **mid**
(release when Phase-1 ≥15 units/mo for 2 consecutive months), **premium** (top
floor / premium facing / large config — **hold until ≥40% absorption**, then
release at **12–18% premium**, brief 2.4).

Cash-flow alignment maps each phase's expected revenue against the construction
drawdown milestones. Competitor-response logic recommends accelerate/hold/adjust
based on the event type and current Phase-1 velocity.

---

## ML price model & cross-check (`models/price_model.py`, brief 5.2)

The comparable-average is a *local lookup*. Alongside it we train a
gradient-boosted model (**XGBoost** when `libomp` is present, else scikit-learn
`GradientBoostingRegressor` — same family, always available) on every real
transaction in the warehouse:

```
price_per_sqft ~ f(lat, lng, config, unit_size, absorption%, infra_score, micro_market)
```

It reports **cross-validated R² and MAE** (5-fold) so reliability is explicit —
on the bundled real data this reaches **R² ≈ 0.68, MAE ≈ ₹1,500/sqft**, with
location the dominant feature (~57% importance), which matches real-estate
intuition. The valuation engine surfaces the model's predicted price next to the
comparable average: **close agreement raises confidence; a large gap is a flag
to investigate** (often it means the parcel's micro-market differs from the
broader city the model averages over). The model never silently overrides the
comparable estimate — it is an independent second opinion.

## Trust / confidence score (`models/trust.py`)

Every module attaches a **TrustScore (0–1, banded HIGH/MEDIUM/LOW)** so no number
is presented with false authority. It blends three honest signals:
1. **Sample size** — how many real comparables backed the answer (saturates ~30).
2. **Dispersion** — how spread-out the comparable prices are (tight = trustworthy;
   a wide spread means a heterogeneous market where any single number is fragile).
3. **Model fit** — the cross-validated R² where a model was fitted.

The score comes with plain-English reasons (e.g. *"33 comparables — solid base;
prices vary ±36% — heterogeneous market; strong fit R²=0.68"*) shown directly in
the dashboard. **This is how the user knows whether a price is usable.** A weak
demand-curve fit therefore lowers the trust band rather than hiding behind a
confident-looking number.

## 5 · Competitive Monitoring (`models/monitoring.py`)

Scans the warehouse and raises alerts:
- **new_filing** — competitor project launched within 3km of a GPL project.
- **price_change** — listed price moved ≥5% between two most-recent listings.
- **absorption** — project crossed 80% sold (tightening) or stalled <30% (overhang).
- **gov** — new infrastructure announcement (LLM-categorised at ingestion).

Each alert is persisted and delivered via email + WhatsApp (console fallback
when unconfigured).
