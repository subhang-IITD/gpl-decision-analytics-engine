# GPL Decision Analytics Engine

AI-powered **land valuation, product-mix optimisation, launch pricing, inventory
phasing, and competitive monitoring** for Godrej Properties Limited (GPL).

An internal decision-support tool that gives BD, Sales Strategy, and senior
management an **evidence-backed second opinion** — replacing gut-based
negotiation with scenario analysis. Every output is explainable and traces to
the underlying data and assumptions.

---

## What's inside (maps to the brief)

| Brief § | Sub-module | Code |
|---|---|---|
| 2.1 / 4.1 / 4.2 / 4.4 | **1 · Land Valuation Engine** (residual value, 3 scenarios, Monte Carlo) | `models/land_valuation.py` |
| 2.2 | **2 · Product Mix Optimiser** (constrained revenue optimisation) | `models/product_mix.py` |
| 2.3 / 4.3 | **3 · Launch Pricing & Escalation** (demand-curve regression) | `models/launch_pricing.py` |
| 2.4 | **4 · Phased Inventory Release Planner** (saleability scoring) | `models/phasing.py` |
| 2.5 | **5 · Competitive Monitoring** + email/WhatsApp alerts | `models/monitoring.py`, `models/alerting.py` |
| 3 | Data warehouse + ingestion (scrapers, APIs, PropEquity Excel, LLM) | `db/`, `ingestion/` |
| 5.2 | FastAPI backend + Streamlit dashboard | `api/`, `dashboard/` |
| 3.1 / 5.3 | Airflow DAGs (scheduled ingestion + failure alerting) | `airflow/dags/` |

## Documentation (handover deliverables)

| Deliverable | File |
|---|---|
| Architecture diagram + tech stack | [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) |
| Data dictionary (every field, source, refresh) | [docs/DATA_DICTIONARY.md](docs/DATA_DICTIONARY.md) |
| Model logic (formulas per sub-module) | [docs/MODEL_LOGIC.md](docs/MODEL_LOGIC.md) |
| API documentation | [docs/API.md](docs/API.md) (live OpenAPI at `/docs`) |
| Deployment guide (AWS) | [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) |
| User guide (GPL teams) | [docs/USER_GUIDE.md](docs/USER_GUIDE.md) |
| Admin guide | [docs/ADMIN_GUIDE.md](docs/ADMIN_GUIDE.md) |

---

## Quick start (local, zero infrastructure)

```bash
cd gpl_engine
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Load REAL PropEquity data (place the .xlsx files in the parent folder)
python -m ingestion.propequity_excel \
  "../Top Micromarkets Dataset_Chennai_29Apr26.xlsx" \
  "../Residential Dataset_Coimbatore_15Apr26.xlsx" \
  "../Plotted Projects Details_Coimbatore_15Apr26.xlsx"

# Launch the dashboard
streamlit run dashboard/app.py
#   -> http://localhost:8501

# (optional) Launch the API
uvicorn api.main:app --reload
#   -> http://localhost:8000/docs
```

With **no API keys**, the engine runs fully on the local SQLite warehouse +
real PropEquity data + a regex LLM fallback. Adding keys (Postgres, PropEquity,
Google Maps, Salesforce, SendGrid, WhatsApp, Ollama/Claude) is a pure `.env`
change — see `.env.example` and the deployment guide.

## Data sources

This build ingests **real PropEquity datasets** (Chennai + Coimbatore). No mock
data is used. Other sources (RERA portals, MagicBricks/99acres, Google Maps,
news/gov) are wired with real adapters that activate when keys/live-scraping are
enabled; until then they degrade gracefully to the warehouse. See the data
dictionary for source-by-source detail.

## Tests

```bash
pytest -q     # 19 tests: models, scenarios, Monte Carlo determinism, API validation
```

## Security posture (brief 5.1)

- GPL-internal data (costs, margins, Salesforce) **never** reaches an external LLM.
- The LLM layer receives **isolated text snippets only** (BD notes, news, gov text).
- Self-hosted LLM (Ollama/Llama 3) is the preferred backend; Claude API is optional with data minimisation.
- Deployable entirely within GPL's own AWS/Azure environment; not a SaaS.
# gpl-decision-analytics-engine
