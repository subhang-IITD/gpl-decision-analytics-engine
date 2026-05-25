# Mermaid Source (fallback)

The submission uses pre-rendered PNGs (`architecture.png`, `data_flow.png`,
`valuation_pipeline.png`). If you prefer to regenerate them in Mermaid
(e.g. mermaid.live), here is the equivalent source.

## 1. System architecture

```mermaid
flowchart TB
    subgraph SRC["Data Sources"]
        PE[PropEquity Excel/API]
        RERA[RERA portals]
        PORT[MagicBricks / 99acres]
        NEWS[News / Gov]
        CRM[GPL CRM internal]
    end
    subgraph ING["Ingestion"]
        SCR[Scrapers Scrapy/Playwright + API clients + Excel loaders]
        LLM[Pluggable LLM<br/>Ollama / Claude / regex]
        ORCH[Airflow / Airbyte]
    end
    WH[(Data Warehouse<br/>PostgreSQL/RDS or SQLite)]
    subgraph MOD["Models"]
        M1[1 Land Valuation]
        M2[2 Product Mix]
        M3[3 Launch Pricing]
        M4[4 Phasing]
        M5[5 Monitoring]
    end
    API[FastAPI /api/v1/*]
    UI[Streamlit Dashboard]
    AL[Email + WhatsApp Alerts]

    PE & RERA & PORT --> SCR --> WH
    NEWS --> LLM --> WH
    CRM --> WH
    ORCH --> WH
    WH --> M1 & M2 & M3 & M4 & M5
    M1 --> API
    M3 --> UI
    M5 --> AL
```

## 2. Data flow

```mermaid
flowchart LR
    F1[FETCH auto:<br/>PropEquity, RERA, portals, news, maps] --> WH[(Warehouse)]
    F2[FEED GPL input:<br/>parcel, costs, margin, CRM bookings] --> WH
    WH --> P[Models + ML price model + trust score]
    P --> O[Outputs: price ranges, mix, alerts]
```

## 3. Land-valuation pipeline

```mermaid
flowchart LR
    A[Parcel input<br/>lat, lng, FSI, area, costs] --> B[Find comparables<br/>radius + recency + similarity]
    B --> C[Demand intensity<br/>+ infra score]
    C --> D[Residual land value<br/>base/bull/bear]
    D --> E[Monte Carlo 10k sims<br/>80/50/20% bands]
    E --> F[ML cross-check + Trust score<br/>explainable output]
```
