import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import pandas as pd
import streamlit as st
from sqlalchemy import func, select

from config import get_settings
from db.schema import MicroMarket, PipelineRun, Project, ReraTransaction
from db.session import get_session

st.title("Admin · Data & Pipeline Health")
settings = get_settings()

st.subheader("Environment")
st.json({
    "database": "SQLite (local)" if settings.db.is_sqlite else "Postgres (remote)",
    "llm_provider": settings.llm.provider,
    "live_scraping": settings.scraper.live_scraping_enabled,
    "propequity_key": bool(settings.keys.propequity_api_key),
    "google_maps_key": bool(settings.keys.google_maps_api_key),
    "salesforce": bool(settings.keys.salesforce_token),
    "sendgrid": bool(settings.alerting.sendgrid_api_key),
    "whatsapp": bool(settings.alerting.whatsapp_api_key),
})

with get_session() as s:
    n_proj = s.scalar(select(func.count()).select_from(Project))
    n_txn = s.scalar(select(func.count()).select_from(ReraTransaction))
    mms = s.execute(select(MicroMarket)).scalars().all()
    runs = s.execute(select(PipelineRun).order_by(PipelineRun.started_at.desc()).limit(50)).scalars().all()
    mm_rows = [{"name": m.name, "city": m.city, "lat": m.center_lat, "lng": m.center_lng,
                "projects": s.scalar(select(func.count()).select_from(Project).where(Project.micro_market_id == m.id))}
               for m in mms]

c1, c2, c3 = st.columns(3)
c1.metric("Projects", f"{n_proj:,}")
c2.metric("Transactions", f"{n_txn:,}")
c3.metric("Micro-markets", f"{len(mms):,}")

st.subheader("Micro-markets")
st.dataframe(pd.DataFrame(mm_rows), use_container_width=True)

st.subheader("Pipeline run history")
if runs:
    st.dataframe(pd.DataFrame([{"pipeline": r.pipeline, "status": r.status,
                                "records": r.records_ingested, "detail": r.detail,
                                "started": r.started_at} for r in runs]), use_container_width=True)
else:
    st.info("No pipeline runs logged yet. Trigger ingestion via Airflow or `python -m ingestion.runner`.")

st.subheader("Ingest Excel workbook")
st.caption("PropEquity market data (project rows) OR GPL internal booking export (report.xlsx).")
kind = st.radio("File type", ["PropEquity market data", "GPL booking export (internal)"], horizontal=True)
upl = st.file_uploader("Excel (.xlsx)", type=["xlsx"])
if upl and st.button("Ingest uploaded file"):
    tmp = Path("_data") / upl.name
    tmp.write_bytes(upl.getbuffer())
    with st.spinner("Ingesting..."):
        if kind.startswith("PropEquity"):
            from ingestion.propequity_excel import ingest_workbook
            stats = ingest_workbook(str(tmp))
        else:
            from ingestion.gpl_sales_excel import ingest_gpl_bookings
            stats = ingest_gpl_bookings(str(tmp))
        # new data -> retrain the price model
        from models.price_model import get_price_model
        get_price_model(force_retrain=True)
    st.success(f"Ingested: {stats}")
