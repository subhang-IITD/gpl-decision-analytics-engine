# Deployment Guide

The engine runs entirely within **GPL's own AWS (or Azure) environment** — it is
not a SaaS and no GPL data is stored on developer servers (brief §5.1).

## Local / evaluation

```bash
cd gpl_engine
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python -m ingestion.propequity_excel "<propequity .xlsx files>"
streamlit run dashboard/app.py        # UI
uvicorn api.main:app --reload         # API
```
No keys required: SQLite warehouse + regex LLM + real PropEquity data.

## AWS production architecture

```
Route53 ─► ALB ─► EC2 (FastAPI via uvicorn/gunicorn)  ─┐
                   EC2 (Streamlit)                      ├─► RDS PostgreSQL (warehouse, AES-256 at rest)
                   EC2/MWAA (Airflow scheduler)        ─┘
                   S3 (PropEquity Excel drops, backups)
                   (optional) EC2 GPU / ECS — Ollama self-hosted LLM
```

### Steps
1. **RDS PostgreSQL** — create instance; enable encryption at rest (AES-256).
   Set `DATABASE_URL=postgresql+psycopg://user:pass@host:5432/gpl`.
2. **Schema + data** — `python -c "from db.session import init_db; init_db()"`,
   then import PropEquity workbooks (or enable the PropEquity API key).
3. **API** — run behind gunicorn:
   `gunicorn api.main:app -k uvicorn.workers.UvicornWorker -w 4 -b 0.0.0.0:8000`.
   Front with an ALB; terminate TLS 1.3 at the ALB (brief §5.1 in-transit).
4. **Dashboard** — `streamlit run dashboard/app.py --server.port 8501` behind
   the ALB (path or subdomain).
5. **Airflow** — deploy `airflow/dags/ingestion_dags.py` to MWAA or a self-hosted
   scheduler. Set the same env vars so DAGs reach the warehouse and alerting.
6. **Secrets** — store keys in AWS Secrets Manager / SSM Parameter Store and
   inject as env vars. Never commit `.env`.

## Environment variables

See `.env.example`. Key ones:

| Var | Purpose |
|---|---|
| `DATABASE_URL` | RDS Postgres connection (unset → local SQLite) |
| `GPL_LLM_PROVIDER` | `ollama` (preferred) / `anthropic` / `regex` |
| `OLLAMA_HOST`, `OLLAMA_MODEL` | self-hosted LLM endpoint |
| `ANTHROPIC_API_KEY` | only if using Claude (data-minimised) |
| `PROPEQUITY_API_KEY` | PropEquity REST access |
| `GOOGLE_MAPS_API_KEY` | road distances for infra score |
| `SALESFORCE_TOKEN`, `SALESFORCE_INSTANCE_URL` | historical sales (read-only) |
| `SENDGRID_API_KEY`, `WHATSAPP_API_KEY` | alert delivery |
| `GPL_LIVE_SCRAPING` | `true` to enable live portal/RERA scraping |

## Security checklist (brief §5.1)
- [ ] TLS 1.3 at the load balancer (in transit).
- [ ] RDS encryption at rest (AES-256).
- [ ] Secrets in Secrets Manager, not in code or `.env` in the repo.
- [ ] `GPL_LLM_PROVIDER=ollama` for full data residency, or document exactly
      what snippets go to Claude and obtain GPL approval.
- [ ] Internal data (costs, margins, Salesforce) confirmed never sent to any LLM.
- [ ] Security group restricts DB to app subnets only.

## Scaling (brief §5.3)
- FastAPI is stateless → scale EC2 horizontally behind the ALB for 20+ users.
- Heavy Monte Carlo is vectorised and completes well under the 90s budget.
- Add an RDS read replica if dashboard read load grows.
