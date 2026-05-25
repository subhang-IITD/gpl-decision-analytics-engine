import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import pandas as pd
import streamlit as st
from sqlalchemy import select

from db.schema import Alert
from db.session import get_session
from models.monitoring import scan

st.title("5 · Competitive Monitoring")
st.caption("New filings, price moves >5%, absorption signals, government infrastructure announcements.")

col1, col2 = st.columns([1, 3])
with col1:
    deliver = st.checkbox("Deliver via email/WhatsApp", value=False,
                          help="Without keys configured, alerts print to the server console.")
    lookback = st.slider("Look-back (days)", 7, 365, 90)
    if st.button("Run scan", type="primary"):
        with st.spinner("Scanning warehouse for decision-relevant changes..."):
            raised = scan(deliver_alerts=deliver, lookback_days=lookback)
        st.success(f"{len(raised)} signal(s) raised.")

with get_session() as s:
    alerts = s.execute(select(Alert).order_by(Alert.created_at.desc()).limit(300)).scalars().all()
    rows = [{"kind": a.kind, "severity": a.severity.value, "message": a.message,
             "created": a.created_at} for a in alerts]

if rows:
    df = pd.DataFrame(rows)
    st.subheader("Alert feed")
    kinds = st.multiselect("Filter by kind", sorted(df["kind"].unique()), default=list(df["kind"].unique()))
    st.dataframe(df[df["kind"].isin(kinds)], use_container_width=True, height=500)
    st.bar_chart(df["kind"].value_counts())
else:
    st.info("No alerts yet. Click **Run scan**.")
