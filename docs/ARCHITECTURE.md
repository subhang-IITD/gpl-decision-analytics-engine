# Architecture & Tech Stack

## System overview

```mermaid
flowchart TB
    subgraph EXT["External Data Sources (Fetch — §3.1)"]
        RERA[RERA Portals\nKA/MH/UP/TN]
        PE[PropEquity API / Excel]
        PORT[MagicBricks / 99acres]
        GM[Google Maps Distance Matrix]
        JOBS[Naukri / LinkedIn]
        NEWS[News RSS]
        GOV[BMRCL / NHAI / Gazette]
    end

    subgraph FEED["Internal Inputs (Feed — §3.2)"]
        BD[BD: parcel, FSI, notes]
        FIN[Finance: costs, margin]
        SF[Salesforce / CSV: history]
        PROJ[Projects: drawdown]
    end

    subgraph INGEST["Ingestion Layer (ingestion/)"]
        SCRAPE[Scrapers\nPlaywright/requests]
        APIS[API Clients\nPropEquity/Maps/SFDC]
        XLS[PropEquity Excel loader]
        LLM[Pluggable LLM\nOllama / Claude / regex]
    end

    subgraph WH["Data Warehouse (db/) — Postgres/RDS or SQLite"]
        TABLES[(projects, transactions,\nabsorption, POIs, listings,\nnews, gov, parcels,\nhistorical_sales, alerts)]
    end

    subgraph MODELS["Model Layer (models/)"]
        M1[1 · Land Valuation\nresidual + Monte Carlo]
        M2[2 · Product Mix\nLP optimisation]
        M3[3 · Launch Pricing\ndemand-curve regression]
        M4[4 · Phasing\nsaleability scoring]
        M5[5 · Monitoring\nsignals + alerts]
    end

    subgraph SERVE["Serving Layer"]
        API[FastAPI\n/api/v1/*]
        UI[Streamlit Dashboard]
        ALERT[Email + WhatsApp]
    end

    ORCH[Apache Airflow\nscheduled DAGs §3.1]

    EXT --> SCRAPE & APIS & XLS
    SCRAPE & APIS & XLS --> WH
    NEWS & GOV --> LLM --> WH
    FEED --> WH
    WH --> M1 & M2 & M3 & M4 & M5
    M1 & M2 & M3 & M4 & M5 --> API --> UI
    M5 --> ALERT
    ORCH --> INGEST
    ORCH --> M5
```

## Layered design

1. **Ingestion** (`ingestion/`) — scrapers (`scrapers/`), API clients (`apis/`),
   the PropEquity Excel loader (`propequity_excel.py`), and the pluggable LLM
   provider (`llm/`). Every adapter is key/flag-driven and degrades to the
   warehouse when a source is unavailable, so the system is always runnable.
2. **Warehouse** (`db/`) — one SQLAlchemy schema (`schema.py`) over Postgres
   (production / AWS RDS) or SQLite (local). Swapped purely via `DATABASE_URL`.
3. **Models** (`models/`) — the five sub-modules, plus shared market-data access
   (`market_data.py`) and alerting (`alerting.py`). Pure Python/NumPy/SciPy/
   scikit-learn; no I/O beyond the warehouse.
4. **Serving** — FastAPI (`api/`) exposes every module as a validated REST
   endpoint; Streamlit (`dashboard/`) is the GPL-facing UI calling the model
   layer directly.
5. **Orchestration** — Airflow DAGs (`airflow/dags/`) run ingestion and
   monitoring on the Section-3.1 schedules and alert the admin on failure.

## Technology stack (vs brief §5.2)

| Layer | Chosen | Brief recommendation | Note |
|---|---|---|---|
| Warehouse | PostgreSQL (RDS) / SQLite local | Snowflake **or** Postgres | Postgres chosen for MVP cost (brief permits). Snowflake-ready via `DATABASE_URL`. |
| Structured ingestion | Custom API clients | Fivetran/Airbyte | Lightweight, no per-row cost; Airbyte can wrap these later. |
| Scraping | requests + Playwright | Scrapy/Playwright | Playwright for JS portals; requests for static RERA. |
| Modelling | NumPy, SciPy, scikit-learn | same | Interpretable (LinearRegression, linprog, MC). |
| LLM | Ollama (preferred) / Claude / regex | Self-hosted Llama/Mistral **or** Claude | Pluggable; default offline regex. |
| Orchestration | Apache Airflow | Airflow / Step Functions | Self-hosted DAGs. |
| Backend | FastAPI | FastAPI | As recommended. |
| Frontend | Streamlit | Streamlit (MVP) | As recommended; React is the later production option. |
| Alerting | SendGrid + Interakt/Gupshup | same | Console fallback when unconfigured. |
| Hosting | AWS EC2 + RDS + S3 | AWS/Azure | See DEPLOYMENT.md. |

## Performance (brief §5.3)

- Land valuation incl. 10k Monte Carlo runs completes in **well under 90s**
  (NumPy-vectorised; ~sub-second on the bundled datasets).
- Pre-computed dashboard views load under 3s (cached micro-market lists).
- Airflow handles unattended refresh; failures alert the admin within SLA.
- Stateless FastAPI scales horizontally for 20+ concurrent users.
