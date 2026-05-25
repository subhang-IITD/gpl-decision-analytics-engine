"""Test fixtures: build an isolated SQLite warehouse seeded from a small,
deterministic synthetic dataset so tests never depend on the real PropEquity
files or network. Production code is unchanged; only DATABASE_URL is redirected.
"""
import os
import tempfile

import pytest

# Point the engine at a throwaway DB before any model import reads settings.
_TMP = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
os.environ["DATABASE_URL"] = f"sqlite:///{_TMP.name}"
os.environ["GPL_LLM_PROVIDER"] = "regex"


@pytest.fixture(scope="session", autouse=True)
def _seed():
    import datetime as dt

    from config.defaults import DEFAULT_COST_ASSUMPTIONS, DEFAULT_INFRA_WEIGHTS
    from db.schema import (AbsorptionSnapshot, MicroMarket, MicroMarketConfig,
                           PointOfInterest, Project, ProjectStatus, ReraTransaction)
    from db.session import get_session, init_db

    init_db()
    with get_session() as s:
        mm = MicroMarket(name="TestMarket", city="TestCity", center_lat=12.97,
                         center_lng=80.22, rera_state="TamilNadu")
        s.add(mm); s.flush()
        s.add(MicroMarketConfig(micro_market_id=mm.id, infra_weights=dict(DEFAULT_INFRA_WEIGHTS),
                                cost_assumptions=dict(DEFAULT_COST_ASSUMPTIONS),
                                min_margin_pct_of_gdv=0.20))
        for cat, dlat in [("metro", 0.002), ("it_park", 0.004), ("highway", 0.01),
                          ("school", 0.003), ("hospital", 0.003)]:
            s.add(PointOfInterest(category=cat, name=f"{cat}-1", lat=12.97 + dlat, lng=80.22))
        configs = ["2BHK", "3BHK", "3.5BHK", "4BHK"]
        for i in range(10):
            premium = 1.0 + (i - 5) * 0.02
            p = Project(name=f"Proj{i}", developer="Dev", is_gpl=(i == 0),
                        micro_market_id=mm.id, lat=12.97 + i * 0.001, lng=80.22 + i * 0.001,
                        launch_date=dt.date.today() - dt.timedelta(days=300),
                        status=ProjectStatus.ongoing, total_units=200, units_sold=120 + i * 5,
                        source="test")
            s.add(p); s.flush()
            for j in range(8):
                cfg = configs[j % 4]
                psf = 7500 * premium + j * 30
                s.add(ReraTransaction(project_id=p.id, config_type=cfg, carpet_sqft=1200 + j * 50,
                                      price_per_sqft=psf, price_total=psf * 1200,
                                      txn_date=dt.date.today() - dt.timedelta(days=j * 30),
                                      lat=p.lat, lng=p.lng, source="test"))
            for m in range(12):
                s.add(AbsorptionSnapshot(project_id=p.id, as_of=dt.date.today() - dt.timedelta(days=m * 30),
                                         units_sold_cumulative=10 * (12 - m), units_sold_in_month=max(1, 15 - i),
                                         avg_price_per_sqft=7500 * premium))
    yield
