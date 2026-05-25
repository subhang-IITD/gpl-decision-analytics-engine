import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from dashboard.common import micro_market_picker
from models.land_valuation import SQFT_PER_ACRE, value_parcel

st.title("1 · Land Valuation Engine")
st.caption("Justifiable land price across base / bull / bear scenarios with Monte Carlo confidence bands.")

with st.sidebar:
    mm = micro_market_picker("lv_mm")
    st.subheader("Parcel")
    lat = st.number_input("Latitude", value=float(mm["lat"]), format="%.5f")
    lng = st.number_input("Longitude", value=float(mm["lng"]), format="%.5f")
    area = st.number_input("Area (acres)", value=3.0, min_value=0.1, step=0.5)
    fsi = st.number_input("FSI", value=2.5, min_value=0.1, max_value=6.0, step=0.25)
    radius = st.slider("Comparable radius (km)", 1.0, 10.0, 3.0, 0.5)
    st.subheader("Cost assumptions (override)")
    constr = st.number_input("Construction Rs./sqft", value=2800.0, step=100.0)
    margin = st.slider("Min margin (% of GDV)", 0.05, 0.50, 0.20, 0.01)
    run = st.button("Run valuation", type="primary")

if run:
    with st.spinner("Running residual model + 10,000 Monte Carlo simulations..."):
        res = value_parcel(lat, lng, area, fsi,
                           cost_overrides={"construction_cost_per_sqft": constr, "min_margin_pct_of_gdv": margin},
                           radius_km=radius)

    if res.data_quality_flag:
        st.warning(res.data_quality_flag)

    # Trust banner -- tells the user how reliable this answer is
    t = res.trust
    band_color = {"HIGH": "🟢", "MEDIUM": "🟡", "LOW": "🔴"}.get(t.get("band"), "⚪")
    st.subheader(f"{band_color} Confidence: {t.get('band')} ({t.get('score')})")
    for reason in t.get("reasons", []):
        st.write("•", reason)
    mc = res.model_cross_check
    if mc.get("predicted_psf_3bhk"):
        st.info(
            f"**ML cross-check** ({mc['backend']}, CV R²={mc['cv_r2']}, MAE Rs.{mc['cv_mae_psf']:,.0f}): "
            f"independent model predicts Rs.{mc['predicted_psf_3bhk']:,.0f}/sqft for a 3BHK "
            f"({mc['vs_comparable_avg_pct']:+.1f}% vs the comparable average). "
            f"Close agreement = higher confidence; a large gap = investigate before acting."
        )

    land_sqft = area * SQFT_PER_ACRE
    c1, c2, c3 = st.columns(3)
    for col, name in zip((c1, c2, c3), ("base", "bull", "bear")):
        sc = res.scenarios[name]
        psf = sc.residual.max_land_price_psf_land
        col.metric(f"{name.title()} — Rs./sqft (land)", f"{psf:,.0f}",
                   help=sc.label)
        col.caption(f"≈ Rs.{psf * land_sqft / 1e7:,.1f} Cr total")

    st.subheader("Monte Carlo confidence (price the market supports)")
    fig = go.Figure()
    for name in ("base", "bull", "bear"):
        cp = res.scenarios[name].mc_confidence_prices
        fig.add_trace(go.Bar(name=name.title(), x=list(cp.keys()), y=list(cp.values())))
    fig.update_layout(barmode="group", xaxis_title="Confidence level", yaxis_title="Rs./sqft (land area)", height=380)
    st.plotly_chart(fig, use_container_width=True)

    st.subheader("Why — explainability")
    for line in res.explanation:
        st.write("•", line)

    with st.expander("Residual value line items (base case)"):
        st.json({k: v for k, v in res.scenarios["base"].residual.__dict__.items()})
    with st.expander("Infrastructure proximity score breakdown"):
        st.write(f"**Infra score: {res.infra_score:.2f}**")
        st.dataframe(pd.DataFrame(res.infra_breakdown).T)
    with st.expander("Demand intensity components"):
        st.write(f"**Demand intensity: {res.demand_intensity:.2f}**")
        st.json(res.demand_components)
    with st.expander("Scenario assumptions & conditions"):
        for name in ("base", "bull", "bear"):
            sc = res.scenarios[name]
            st.markdown(f"**{name.title()} — {sc.label}**")
            for a in sc.assumptions:
                st.write("  -", a)
            st.caption("Conditions to materialise: " + "; ".join(sc.conditions_to_materialise))
else:
    st.info("Set parcel parameters in the sidebar and click **Run valuation**.")
