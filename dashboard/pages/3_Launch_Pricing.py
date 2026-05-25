import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from dashboard.common import micro_market_picker
from models.launch_pricing import optimal_launch_price, simulate_price

st.title("3 · Launch Pricing & Escalation")
st.caption("Demand-curve regression -> optimal launch price under cash-flow & sellout constraints.")

with st.sidebar:
    mm = micro_market_picker("lp_mm")
    lat = st.number_input("Latitude", value=float(mm["lat"]), format="%.5f", key="lp_lat")
    lng = st.number_input("Longitude", value=float(mm["lng"]), format="%.5f", key="lp_lng")
    units = st.number_input("Total units", value=200, min_value=1, step=10)
    m1 = st.number_input("Min units by Month 1", value=8.0)
    m3 = st.number_input("Min units by Month 3", value=25.0)
    m6 = st.number_input("Min units by Month 6", value=50.0)
    max_sell = st.number_input("Max months to sellout", value=36.0)
    instinct = st.number_input("Instinct price (optional)", value=0.0)
    run = st.button("Compute optimal price", type="primary")

if run:
    res = optimal_launch_price(lat, lng, int(units), m1, m3, m6, max_sell,
                               instinct or None)
    if res.sparse_data:
        st.warning("Sparse comparable data — showing raw points + interpolation, not a fitted curve.")
    t = res.trust
    band_color = {"HIGH": "🟢", "MEDIUM": "🟡", "LOW": "🔴"}.get(t.get("band"), "⚪")
    st.subheader(f"{band_color} Confidence: {t.get('band')} ({t.get('score')})")
    for reason in t.get("reasons", []):
        st.write("•", reason)

    c1, c2, c3 = st.columns(3)
    c1.metric("Optimal launch Rs./sqft", f"{res.optimal_launch_psf:,.0f}")
    c2.metric("Projected velocity (units/mo)", f"{res.projected_velocity:.1f}")
    c3.metric("Months to sellout", f"{res.months_to_sellout}")

    st.subheader("Demand curve")
    pts = res.demand_points
    fig = go.Figure()
    if pts:
        fig.add_trace(go.Scatter(x=[p.price_per_sqft for p in pts], y=[p.units_per_month for p in pts],
                                 mode="markers", name="Comparables",
                                 text=[p.project for p in pts]))
    if res.regression.get("status") == "ok" and pts:
        from models.launch_pricing import fit_demand_curve
        prices_arr = np.array([p.price_per_sqft for p in pts])
        vels_arr = np.array([p.units_per_month for p in pts])
        curve = fit_demand_curve(prices_arr, vels_arr)
        xs = np.linspace(prices_arr.min(), prices_arr.max(), 80)
        ys = curve.predict(xs)
        fig.add_trace(go.Scatter(x=xs, y=ys, mode="lines",
                                 name=f"{res.regression['form']} fit (R²={res.regression['r2']})"))
        fig.add_vline(x=res.optimal_launch_psf, line_dash="dash", annotation_text="Optimal")
    fig.update_layout(xaxis_title="Price Rs./sqft", yaxis_title="Units/month", height=400)
    st.plotly_chart(fig, use_container_width=True)

    st.subheader("Phased escalation schedule")
    st.dataframe(pd.DataFrame([p.__dict__ for p in res.phased_schedule]), use_container_width=True)

    st.subheader("Upside vs instinct price")
    st.json(res.upside_vs_instinct)

    st.subheader("Scenario test")
    test_price = st.slider("Test a launch price", 3000, 25000, int(res.optimal_launch_psf), 100)
    st.json(simulate_price(lat, lng, int(units), float(test_price)))

    st.subheader("Why")
    for line in res.explanation:
        st.write("•", line)
else:
    st.info("Set parameters and click **Compute optimal price**.")
