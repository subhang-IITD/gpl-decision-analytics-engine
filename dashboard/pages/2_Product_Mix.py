import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import pandas as pd
import plotly.express as px
import streamlit as st

from dashboard.common import micro_market_picker
from models.product_mix import optimise_mix

st.title("2 · Product Mix Optimiser")
st.caption("Revenue-maximising configuration mix under the FSI constraint, informed by real absorption.")

with st.sidebar:
    mm = micro_market_picker("pm_mm")
    lat = st.number_input("Latitude", value=float(mm["lat"]), format="%.5f", key="pm_lat")
    lng = st.number_input("Longitude", value=float(mm["lng"]), format="%.5f", key="pm_lng")
    area = st.number_input("Area (acres)", value=3.0, min_value=0.1, step=0.5, key="pm_area")
    fsi = st.number_input("FSI", value=2.5, min_value=0.1, max_value=6.0, step=0.25, key="pm_fsi")
    saleable = st.slider("Saleable ratio", 0.6, 0.9, 0.78, 0.01)
    use_override = st.checkbox("Override mix (compare custom)")
    override = None
    if use_override:
        st.caption("Enter share % per config (need not sum to 100; normalised).")
        override = {
            "2BHK": st.number_input("2BHK %", 0.0, 100.0, 20.0),
            "3BHK": st.number_input("3BHK %", 0.0, 100.0, 50.0),
            "3.5BHK": st.number_input("3.5BHK %", 0.0, 100.0, 20.0),
            "4BHK": st.number_input("4BHK %", 0.0, 100.0, 10.0),
        }
    run = st.button("Optimise mix", type="primary")

if run:
    res = optimise_mix(lat, lng, area, fsi, saleable_ratio=saleable, override_mix=override)
    c1, c2 = st.columns(2)
    c1.metric("Blended realisation Rs./sqft", f"{res.blended_psf:,.0f}")
    c2.metric("Total projected revenue", f"Rs.{res.total_revenue/1e7:,.1f} Cr")

    df = pd.DataFrame([{
        "Config": m.config_type, "Units": m.unit_count, "% of units": round(m.pct_of_units * 100, 1),
        "Unit sqft": m.unit_sqft, "Avg Rs./sqft": m.avg_psf, "Revenue (Cr)": round(m.projected_revenue / 1e7, 1),
    } for m in res.recommended_mix])
    st.subheader("Recommended mix")
    st.dataframe(df, use_container_width=True)
    st.plotly_chart(px.pie(df, names="Config", values="Units", title="Recommended unit mix"), use_container_width=True)

    st.subheader("Delta vs micro-market average mix")
    delta_df = pd.DataFrame([{"Config": k, "Delta (recommended - market)": round(v * 100, 1)}
                             for k, v in res.delta_vs_market.items()])
    st.bar_chart(delta_df.set_index("Config"))

    with st.expander("Demand–supply gap by configuration"):
        st.dataframe(pd.DataFrame([d.__dict__ for d in res.demand_by_config]))
    st.subheader("Why")
    for line in res.explanation:
        st.write("•", line)
else:
    st.info("Configure the parcel and click **Optimise mix**.")
