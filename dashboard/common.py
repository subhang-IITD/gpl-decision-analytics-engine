"""Shared dashboard helpers."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import streamlit as st
from sqlalchemy import select

from db.schema import MicroMarket
from db.session import get_session


@st.cache_data(ttl=300)
def list_micro_markets() -> list[dict]:
    with get_session() as s:
        mms = s.execute(select(MicroMarket).order_by(MicroMarket.city, MicroMarket.name)).scalars().all()
        return [{"id": m.id, "name": m.name, "city": m.city, "lat": m.center_lat, "lng": m.center_lng} for m in mms]


def micro_market_picker(key: str = "mm") -> dict:
    """Sidebar picker returning the selected micro-market dict (with lat/lng)."""
    mms = list_micro_markets()
    if not mms:
        st.warning("No micro-markets loaded. Run ingestion first (Admin page).")
        st.stop()
    labels = [f"{m['name']} ({m['city']})" for m in mms]
    idx = st.selectbox("Micro-market", range(len(mms)), format_func=lambda i: labels[i], key=key)
    return mms[idx]
