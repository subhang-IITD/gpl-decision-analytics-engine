# Airbyte Connector Configuration (brief 5.2)

Airbyte handles the **structured / REST-API** ingestion sources. Web scraping
stays in our Python/Playwright layer (Airbyte is not a scraper). This document
tells GPL's ops team exactly how to wire each source so data lands in the same
warehouse the models read.

> **Prerequisite:** a Docker-capable host (GPL AWS, not a laptop). Bring the
> stack up with `docker compose -f airbyte/docker-compose.yml up -d`, then open
> the UI at `http://<host>:8000`.

## Destination (set up once)

**Destination → Postgres** — point at the same warehouse the engine uses:
| Field | Value |
|---|---|
| Host | your RDS endpoint |
| Port | 5432 |
| DB Name | `gpl` |
| Schema | `airbyte_raw` (we map into model tables via a normalization step) |
| Username / Password | from AWS Secrets Manager |

After sync, a small SQL/dbt step copies `airbyte_raw.*` into the engine tables
(`projects`, `rera_transactions`, `absorption_snapshots`). A starter mapping is
in `airbyte/normalize.sql`.

## Sources

### 1. PropEquity (REST API) — **primary**
- Connector: **Source → HTTP / REST (Airbyte "Custom API" or "File" for Excel drops)**.
- Auth: Bearer token (`PROPEQUITY_API_KEY`).
- Base URL: from your PropEquity subscription docs.
- Streams to enable: `projects`, `transactions`, `absorption`.
- Sync frequency: **Weekly** (matches brief §3.1).
- Until the live API is provisioned, GPL can drop PropEquity **Excel exports**
  into S3 and use our `ingestion/propequity_excel.py` loader — no Airbyte needed
  for that path.

### 2. Google Sheets / CSV (GPL internal feeds)
- Connector: **Source → Google Sheets** or **File (S3)**.
- Use for: cost-assumption sheets, historical-sales CSVs, drawdown schedules.
- Sync: on change.

### 3. Salesforce (historical sales, read-only)
- Connector: **Source → Salesforce** (built-in).
- OAuth, **read-only** permission set.
- Stream: `GPL_Project_Performance__c`.
- Sync: weekly. (Brief §5.1: this internal data never touches an LLM.)

## What stays OUTSIDE Airbyte (handled by our Python layer)
| Source | Why | Where |
|---|---|---|
| RERA portals | HTML/scrape, per-state layouts | `ingestion/scrapers/rera.py` |
| MagicBricks / 99acres | JS-rendered, Cloudflare | `ingestion/scrapers/portals_playwright.py` |
| News RSS | needs LLM classification | `ingestion/scrapers/news_rss.py` |
| Gov announcements | needs LLM parsing | `ingestion/scrapers/news_gov.py` |

These run on the Airflow schedule (`airflow/dags/ingestion_dags.py`).

## Why Airbyte (vs Fivetran)
Open-source, **no per-row pricing**, self-hostable inside GPL's environment — so
it satisfies the brief's data-residency requirement. Fivetran would send data
through Fivetran's servers and bill per row; rejected for both cost and §5.1.
