# Deploying the Dashboard to Streamlit Community Cloud

The repo ships a bundled, read-only demo database (`_data/demo.db`) containing
**real PropEquity market data** (Chennai, Coimbatore, Bengaluru) and **no
GPL-internal records**, so the deployed app boots with data and zero setup.

## Steps

1. Push this repo to GitHub (private is fine; connect the Streamlit app to it).
2. Go to <https://share.streamlit.io> → **New app** → pick this repo/branch.
3. Set **Main file path** to:
   ```
   dashboard/app.py
   ```
4. Under **Advanced settings → Python dependencies file**, point it at the lean
   cloud requirements (avoids heavy playwright/scrapy/xgboost builds):
   ```
   requirements-cloud.txt
   ```
   *(If the UI only accepts the default name, rename `requirements-cloud.txt` to
   `requirements.txt` on a deploy branch.)*
5. Deploy. The app reads `_data/demo.db` automatically (see
   `config/settings.py:_default_db_url`).

## What works on the demo
- All five modules (valuation, mix, pricing, phasing, monitoring) on the bundled
  market data.
- The ML price model runs via the scikit-learn fallback (XGBoost is skipped on
  cloud — same model family).

## What is intentionally off on the demo
- Live scraping (no proxies on cloud) — `GPL_LIVE_SCRAPING` stays `false`.
- Email/WhatsApp delivery (no keys) — alerts show in-app.
- GPL CRM data — excluded from the demo DB by design.

## Production note
For GPL's real deployment, do **not** use the demo DB. Point `DATABASE_URL` at
GPL's RDS Postgres and ingest live data — see `docs/DEPLOYMENT.md`.
