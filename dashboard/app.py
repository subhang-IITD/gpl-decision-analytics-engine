"""GPL Decision Analytics Engine -- Streamlit dashboard (brief 5.2).

Run:  streamlit run dashboard/app.py

Multi-page app: Land Valuation, Product Mix, Launch Pricing, Phasing,
Competitive Monitoring, Admin. The dashboard calls the model layer directly so
it runs standalone; the same models sit behind the FastAPI service for
programmatic access.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import streamlit as st

from db.session import init_db

st.set_page_config(page_title="GPL Decision Analytics Engine", page_icon="🏗️", layout="wide")
init_db()

st.title("GPL Decision Analytics Engine")
st.caption("AI-powered land valuation, product mix, pricing, inventory phasing & competitive monitoring")

st.markdown(
    """
This internal decision-support tool gives GPL's BD, Sales Strategy and senior
management an **evidence-backed second opinion** on four high-stakes decisions.
Every output is explainable and traces to the underlying data and assumptions.

**Use the sidebar to open a module:**

| Module | Question it answers |
|---|---|
| **1 · Land Valuation** | What price can we justifiably pay for this parcel? (base / bull / bear + Monte Carlo) |
| **2 · Product Mix** | What configuration mix maximises revenue under the FSI constraint? |
| **3 · Launch Pricing** | What launch price + escalation schedule maximises revenue vs velocity? |
| **4 · Inventory Phasing** | Which units to release first, and when to release premium stock? |
| **5 · Competitive Monitoring** | What changed in the micro-market that we must react to? |
| **Admin** | Data sources, micro-markets, pipeline health |

The model does **not** replace human judgement — it replaces gut-based
negotiation with scenario analysis.
"""
)

with st.sidebar:
    st.header("About")
    st.write("Data currently loaded from **real PropEquity** project datasets (Chennai, Coimbatore).")
    from sqlalchemy import func, select
    from db.schema import Project, ReraTransaction, MicroMarket
    from db.session import get_session
    with get_session() as s:
        n_proj = s.scalar(select(func.count()).select_from(Project))
        n_txn = s.scalar(select(func.count()).select_from(ReraTransaction))
        n_mm = s.scalar(select(func.count()).select_from(MicroMarket))
    st.metric("Projects", f"{n_proj:,}")
    st.metric("Transactions", f"{n_txn:,}")
    st.metric("Micro-markets", f"{n_mm:,}")
