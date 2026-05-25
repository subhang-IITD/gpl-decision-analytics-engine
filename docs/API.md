# API Documentation

FastAPI service in `api/main.py`. Interactive OpenAPI docs are auto-generated at
`http://<host>:8000/docs` (Swagger) and `/redoc`. All inputs are validated;
impossible values return HTTP **422** with a clear message (brief §5.1).

```bash
uvicorn api.main:app --host 0.0.0.0 --port 8000
```

## Endpoints

### `GET /health`
Liveness probe → `{"status": "ok"}`.

### `POST /api/v1/land-valuation`
Request:
```json
{
  "lat": 12.9010, "lng": 80.2279,
  "area_acres": 3.0, "fsi": 2.5, "radius_km": 3.0,
  "cost_overrides": {
    "construction_cost_per_sqft": 2800,
    "min_margin_pct_of_gdv": 0.20
  }
}
```
Response (abridged): `micro_market`, `comparables_count`, `infra_score`,
`demand_intensity`, `scenarios.{base,bull,bear}` each with `residual` line items,
`assumptions`, `conditions_to_materialise`, `mc_confidence_prices` (80/50/20%),
`data_quality_flag`, `explanation[]`.

Validation: FSI ∈ (0, 6], area ∈ (0, 500], margin ∈ [0, 0.9].

### `POST /api/v1/product-mix`
Body = parcel + `saleable_ratio` + optional `override_mix` (`{"2BHK": 20, ...}`).
Returns `recommended_mix[]`, `blended_psf`, `total_revenue`, `delta_vs_market`,
`demand_by_config[]`, `explanation[]`.

### `POST /api/v1/launch-pricing`
```json
{ "lat": 12.9, "lng": 80.2, "total_units": 200,
  "min_units_m1": 8, "min_units_m3": 25, "min_units_m6": 50,
  "max_months_to_sellout": 36, "instinct_price": 7000 }
```
Returns `optimal_launch_psf`, `projected_velocity`, `months_to_sellout`,
`regression`, `demand_points[]`, `phased_schedule[]`, `upside_vs_instinct`,
`sparse_data`.

### `POST /api/v1/launch-pricing/simulate`
Body `{lat, lng, total_units, price}` → projected velocity, sellout, revenue.

### `POST /api/v1/phasing`
Body `{units: [{unit_id, config_type, floor, facing, base_psf, amenity_facing}], launch_psf, drawdown}`.
Returns scored units, three phases with triggers, cash-flow alignment.

### `POST /api/v1/phasing/competitor-response`
Body `{event, phase1_absorption_per_month}` → accelerate/hold/adjust recommendation.

### `POST /api/v1/monitoring/scan?deliver_alerts=false`
Runs the competitive scan; returns raised alerts. `deliver_alerts=true` also
sends email/WhatsApp.

## Example

```bash
curl -X POST http://localhost:8000/api/v1/land-valuation \
  -H 'Content-Type: application/json' \
  -d '{"lat":12.9010,"lng":80.2279,"area_acres":3.0,"fsi":2.5}'
```
