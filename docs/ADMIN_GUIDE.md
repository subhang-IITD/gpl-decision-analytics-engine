# Admin Guide

For the GPL engineer/analyst maintaining the engine: adding micro-markets,
updating scrapers, ingesting data, configuring weights, and monitoring health.

---

## Adding a new micro-market

Micro-markets are created automatically when you ingest a PropEquity workbook
that contains them. To add geocodes (so proximity scoring is accurate rather
than city-centroid):

1. Open `ingestion/propequity_excel.py`.
2. Add an entry to `MICROMARKET_GEOCODES`:
   ```python
   "Whitefield (Bengaluru)": (12.9698, 77.7500),
   ```
3. Re-ingest, or update the row in the `micro_markets` table directly.

Per-micro-market **infra weights** and **cost assumptions** live in
`micro_market_configs` (JSON columns). Edit them via SQL or extend the Admin
page. Defaults come from `config/defaults.py`.

> Example: Whitefield is IT-park-driven → raise `it_park` weight; Thane is
> highway-driven → raise `highway`. Weights should sum to ~1.0.

---

## Ingesting data

### PropEquity Excel (current source)
```bash
python -m ingestion.propequity_excel "path/to/Dataset.xlsx"
```
Or use the **Admin → Ingest PropEquity workbook** uploader in the dashboard.
The loader maps the project rows + quarterly absorption/price blocks into the
warehouse. Header row is row 6; if PropEquity changes the layout, adjust
`HEADER_ROW` and the column-name lookups in `ingest_workbook`.

### Live sources (scrapers / APIs)
```bash
python -m ingestion.runner          # runs portals, RERA, news/gov
```
Enable live scraping with `GPL_LIVE_SCRAPING=true`. Set API keys in `.env`.
Each run logs to the `pipeline_runs` table (visible on the Admin page).

---

## Updating scraper configurations

Selectors are isolated per source so markup changes are easy to fix:

| Source | File | What to update |
|---|---|---|
| MagicBricks | `ingestion/scrapers/portals.py` → `MagicBricksScraper._parse` | CSS selectors for listing cards |
| 99acres | `ingestion/scrapers/portals.py` → `NinetyNineAcresScraper._parse` | CSS selectors |
| RERA (per state) | `ingestion/scrapers/rera.py` → `RERA_PORTALS`, `_parse` | URL + table columns |
| News RSS | `ingestion/scrapers/news_gov.py` → `NEWS_FEEDS` | feed URLs |
| Gov sites | `ingestion/scrapers/news_gov.py` → `GOV_SOURCES` | URLs |

MagicBricks/99acres are Cloudflare-protected: production needs Playwright
(`pip install playwright && playwright install chromium`) and rotating proxies.
Scrape off-peak with randomised delays. The base scraper already sets a browser
UA and throttle.

---

## LLM configuration (brief §5.1)

`GPL_LLM_PROVIDER`:
- `regex` — offline keyword extraction (default; no model needed).
- `ollama` — self-hosted Llama 3/Mistral. Set `OLLAMA_HOST`, `OLLAMA_MODEL`.
  **Preferred** — no data leaves GPL.
- `anthropic` — Claude API. Requires `ANTHROPIC_API_KEY`. Only isolated text
  snippets are sent; never internal financial data.

If the configured backend is unavailable, the layer auto-falls back to regex and
notes it in the output — pipelines never crash.

---

## Pipeline health monitoring (brief §5.3)

- The **Admin** page shows recent `pipeline_runs` (status, record counts, detail).
- Airflow DAGs (`airflow/dags/ingestion_dags.py`) call the alerting layer on any
  task failure → email + WhatsApp to `GPL_ADMIN_EMAIL` within the retry window.
- To run the competitive scan manually: `python -c "from models.monitoring import scan; print(len(scan()))"`.

---

## Backups & rotation
- Back up the warehouse (RDS automated snapshots, or copy the SQLite file).
- Rotate API keys in AWS Secrets Manager; the app reads them from env at start,
  so rotation = update secret + restart the service.

## Running tests
```bash
pytest -q
```
Tests use an isolated SQLite DB seeded in `tests/conftest.py`; they never touch
production data or the network.
