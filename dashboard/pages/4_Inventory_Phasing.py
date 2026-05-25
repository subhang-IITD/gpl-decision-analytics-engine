import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import random

import pandas as pd
import streamlit as st

from models.phasing import Unit, competitor_response, plan_phasing

st.title("4 · Phased Inventory Release Planner")
st.caption("Saleability-scored release sequence; premium hold strategy; cash-flow-aligned triggers.")

with st.sidebar:
    st.subheader("Generate inventory")
    floors = st.number_input("Floors", value=20, min_value=1)
    per_floor = st.number_input("Units per floor", value=4, min_value=1)
    launch_psf = st.number_input("Launch Rs./sqft", value=7546.0, step=100.0)
    seed = st.number_input("Random seed", value=1)
    run = st.button("Plan phasing", type="primary")

if run:
    rng = random.Random(int(seed))
    facings = ["E", "W", "N", "S", "NE", "NW", "SE", "SW"]
    configs = ["2BHK", "3BHK", "3.5BHK", "4BHK"]
    units = []
    for f in range(1, int(floors) + 1):
        for u in range(int(per_floor)):
            units.append(Unit(
                unit_id=f"U{f:02d}-{u+1}", config_type=rng.choice(configs),
                floor=f, facing=rng.choice(facings),
                base_psf=launch_psf + f * 50 + rng.randint(-200, 200),
                amenity_facing=(f <= 4),
            ))
    drawdown = [{"phase": 1, "amount_inr": 2.0e8}, {"phase": 2, "amount_inr": 3.0e8}, {"phase": 3, "amount_inr": 2.5e8}]
    res = plan_phasing(units, launch_psf, drawdown)

    st.subheader("Release phases")
    for ph in res.phases:
        with st.container(border=True):
            st.markdown(f"**Phase {ph.phase} — {ph.tier}** · {ph.count} units · Rs.{ph.recommended_psf:,.0f}/sqft")
            st.caption(f"Trigger: {ph.release_trigger}")

    st.subheader("Cash-flow alignment vs drawdown")
    st.dataframe(pd.DataFrame(res.cashflow_alignment), use_container_width=True)

    st.subheader("Unit saleability scores (top 20)")
    df = pd.DataFrame([u.__dict__ for u in res.scored_units]).sort_values("saleability", ascending=False)
    st.dataframe(df.head(20), use_container_width=True)

    st.subheader("Competitor response")
    event = st.text_input("Competitor event", "Competitor launched a new project 2km away")
    vel = st.number_input("Current Phase-1 velocity (units/mo)", value=16.0)
    st.json(competitor_response(event, vel))

    st.subheader("Why")
    for line in res.explanation:
        st.write("•", line)
else:
    st.info("Set inventory parameters and click **Plan phasing**.")
