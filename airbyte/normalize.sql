-- Starter normalization: map Airbyte raw landing tables into the engine schema.
-- Run after each Airbyte sync (schedule via Airflow or dbt). Adjust column names
-- to match the actual PropEquity/Salesforce stream fields your connector emits.

-- PropEquity projects -> projects
INSERT INTO projects (rera_id, name, developer, is_gpl, lat, lng, launch_date,
                      status, total_units, units_sold, source, fetched_at)
SELECT
    raw.rera_number,
    raw.project_name,
    raw.developer_name,
    (lower(raw.developer_name) LIKE '%godrej%'),
    raw.latitude, raw.longitude,
    raw.launch_date::date,
    CASE WHEN lower(raw.current_status) LIKE '%sold%' THEN 'completed' ELSE 'ongoing' END,
    raw.launched_units::int,
    (raw.launched_units::int - COALESCE(raw.unsold_units::int, 0)),
    'propequity',
    now()
FROM airbyte_raw._airbyte_raw_projects raw
ON CONFLICT DO NOTHING;

-- PropEquity transactions -> rera_transactions
INSERT INTO rera_transactions (project_id, config_type, carpet_sqft, price_total,
                               price_per_sqft, txn_date, lat, lng, source)
SELECT
    p.id, raw.config_type, raw.unit_size_sqft::float,
    raw.price_per_sqft::float * raw.unit_size_sqft::float,
    raw.price_per_sqft::float, raw.txn_date::date, p.lat, p.lng, 'propequity'
FROM airbyte_raw._airbyte_raw_transactions raw
JOIN projects p ON p.rera_id = raw.rera_number
ON CONFLICT DO NOTHING;

-- After loading, retrain the price model:  python -c "from models.price_model import get_price_model; get_price_model(force_retrain=True)"
