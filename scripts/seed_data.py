"""Generate a realistic synthetic warehouse for Whitefield, Bengaluru.

This exists so the entire engine is demonstrable end-to-end without live API
keys or paid subscriptions. The data is statistically realistic (price bands,
absorption curves, infra layout for Whitefield) but entirely synthetic -- no
real RERA records. When GPL connects real sources, the ingestion adapters
write into these same tables and the seed becomes unnecessary.

Run:  python -m scripts.seed_data
"""
from __future__ import annotations

import datetime as dt
import math
import random

from config.defaults import DEFAULT_COST_ASSUMPTIONS, DEFAULT_INFRA_WEIGHTS
from db.schema import (
    AbsorptionSnapshot,
    DrawdownSchedule,
    GovAnnouncement,
    HistoricalSale,
    JobSignal,
    Listing,
    MicroMarket,
    MicroMarketConfig,
    NewsItem,
    PointOfInterest,
    Project,
    ProjectStatus,
    ReraTransaction,
)
from db.session import get_session, init_db

RNG = random.Random(42)  # deterministic seed -> reproducible demo

WHITEFIELD = {"name": "Whitefield, Bengaluru", "city": "Bengaluru", "lat": 12.9698, "lng": 77.7500, "state": "Karnataka"}

CONFIG_BASE_PSF = {"2BHK": 7200, "3BHK": 7600, "3.5BHK": 8100, "4BHK": 8800}
CONFIG_SQFT = {"2BHK": 1100, "3BHK": 1550, "3.5BHK": 1850, "4BHK": 2400}
FACINGS = ["N", "S", "E", "W", "NE", "NW", "SE", "SW"]

COMPETITORS = [
    "Prestige Group", "Brigade Enterprises", "Sobha Ltd", "Puravankara",
    "Salarpuria Sattva", "Mahindra Lifespaces", "Shriram Properties",
]

POIS = [
    ("metro", "Whitefield (Kadugodi) Metro", 12.9959, 77.7588, False),
    ("metro", "Hopefarm Channasandra Metro", 12.9870, 77.7560, False),
    ("metro", "Proposed Whitefield-Hoskote Extn", 12.9740, 77.7800, True),
    ("it_park", "ITPL / ITPB", 12.9856, 77.7367, False),
    ("it_park", "EPIP Zone", 12.9790, 77.7180, False),
    ("it_park", "Brookefield Tech Park", 12.9670, 77.7170, False),
    ("highway", "Old Madras Road (NH-75)", 13.0000, 77.7100, False),
    ("highway", "Outer Ring Road junction", 12.9550, 77.7010, False),
    ("school", "Vibgyor High Whitefield", 12.9720, 77.7480, False),
    ("school", "Gopalan International School", 12.9610, 77.7420, False),
    ("hospital", "Manipal Hospital Whitefield", 12.9725, 77.7510, False),
    ("hospital", "Columbia Asia Whitefield", 12.9698, 77.7430, False),
]


def _jitter(value: float, spread: float) -> float:
    return value + RNG.uniform(-spread, spread)


def _months_ago(months: int) -> dt.date:
    return (dt.date.today() - dt.timedelta(days=int(months * 30.4))).replace(day=15)


def seed() -> None:
    init_db()
    with get_session() as s:
        if s.query(MicroMarket).filter_by(name=WHITEFIELD["name"]).first():
            print("Whitefield already seeded; skipping. (Delete _data/gpl.db to reseed.)")
            return

        mm = MicroMarket(
            name=WHITEFIELD["name"], city=WHITEFIELD["city"],
            center_lat=WHITEFIELD["lat"], center_lng=WHITEFIELD["lng"],
            rera_state=WHITEFIELD["state"],
        )
        s.add(mm)
        s.flush()

        s.add(MicroMarketConfig(
            micro_market_id=mm.id,
            infra_weights=dict(DEFAULT_INFRA_WEIGHTS),
            cost_assumptions=dict(DEFAULT_COST_ASSUMPTIONS),
            min_margin_pct_of_gdv=DEFAULT_COST_ASSUMPTIONS["min_margin_pct_of_gdv"],
        ))

        for cat, name, lat, lng, planned in POIS:
            s.add(PointOfInterest(category=cat, name=name, lat=lat, lng=lng, planned=planned))

        # Job-market signal: 24 months, gentle upward trend (Whitefield IT growth)
        for m in range(24, 0, -1):
            base = 4200 + (24 - m) * 90
            s.add(JobSignal(
                micro_market_id=mm.id, as_of=_months_ago(m),
                active_postings=int(_jitter(base, 300)), employer_category="IT/ITES",
            ))

        # 14 comparable projects with transactions + absorption series
        n_projects = 14
        for i in range(n_projects):
            dev = RNG.choice(COMPETITORS)
            launch_m = RNG.randint(6, 34)
            total = RNG.choice([180, 240, 320, 420, 560])
            # absorption fraction grows with age, capped
            age = launch_m
            frac = min(0.95, 0.18 + age * 0.025 + RNG.uniform(-0.05, 0.08))
            sold = int(total * frac)
            status = ProjectStatus.completed if frac > 0.9 else ProjectStatus.ongoing
            if frac < 0.30 and age > 18:
                status = ProjectStatus.stalled
            plat, plng = _jitter(mm.center_lat, 0.020), _jitter(mm.center_lng, 0.022)
            proj = Project(
                rera_id=f"PRM/KA/RERA/1251/446/PR/{220000 + i}",
                name=f"{dev.split()[0]} {RNG.choice(['Meadows','Heights','Lakefront','Avenue','Élan','Crest','Vista'])}",
                developer=dev, is_gpl=False, micro_market_id=mm.id,
                lat=plat, lng=plng, launch_date=_months_ago(launch_m),
                status=status, total_units=total, units_sold=sold, source="propequity",
            )
            s.add(proj)
            s.flush()

            # price level per project (psf), correlated with config + small premium
            proj_premium = _jitter(1.0, 0.07)
            for _ in range(RNG.randint(18, 40)):
                cfg = RNG.choices(list(CONFIG_BASE_PSF), weights=[0.30, 0.42, 0.20, 0.08])[0]
                psf = CONFIG_BASE_PSF[cfg] * proj_premium * _jitter(1.0, 0.05)
                sqft = _jitter(CONFIG_SQFT[cfg], 80)
                txn_m = RNG.randint(0, min(launch_m, 24))
                s.add(ReraTransaction(
                    project_id=proj.id, config_type=cfg, carpet_sqft=round(sqft, 1),
                    price_per_sqft=round(psf, 1), price_total=round(psf * sqft, 0),
                    floor=RNG.randint(1, 22), facing=RNG.choice(FACINGS),
                    txn_date=_months_ago(txn_m), lat=_jitter(plat, 0.002), lng=_jitter(plng, 0.002),
                    source="rera",
                ))

            # absorption snapshots (monthly), demand curve input
            cum = 0
            for m_idx in range(min(launch_m, 24)):
                # higher price project -> slower velocity (downward demand curve)
                vel_base = 18 * (2.0 - proj_premium)
                in_month = max(0, int(_jitter(vel_base, 5)))
                cum = min(total, cum + in_month)
                s.add(AbsorptionSnapshot(
                    project_id=proj.id, as_of=_months_ago(launch_m - m_idx),
                    units_sold_cumulative=cum, units_sold_in_month=in_month,
                    avg_price_per_sqft=round(CONFIG_BASE_PSF["3BHK"] * proj_premium, 1),
                ))

            # live listings on portals
            for portal in ("magicbricks", "99acres"):
                cfg = RNG.choice(list(CONFIG_BASE_PSF))
                s.add(Listing(
                    project_id=proj.id, portal=portal, config_type=cfg,
                    listed_price_per_sqft=round(CONFIG_BASE_PSF[cfg] * proj_premium * _jitter(1.0, 0.03), 1),
                    available_units=max(0, total - sold),
                ))

        # GPL historical sales (feed source) -- 6 past GPL projects
        for i in range(6):
            cfg = RNG.choice(list(CONFIG_BASE_PSF))
            planned = RNG.choice([200, 280, 360])
            s.add(HistoricalSale(
                project_name=f"Godrej {RNG.choice(['Park','Woodscape','Reserve','Splendour','Aria'])} {i+1}",
                micro_market_id=mm.id, config_type=cfg,
                planned_units=planned, sold_units=int(planned * _jitter(0.88, 0.08)),
                launch_price_per_sqft=round(CONFIG_BASE_PSF[cfg] * _jitter(0.97, 0.03), 1),
                realised_price_per_sqft=round(CONFIG_BASE_PSF[cfg] * _jitter(1.06, 0.04), 1),
                months_to_50pct=round(_jitter(7.5, 2.0), 1), phase=RNG.randint(1, 3),
                source="csv",
            ))

        # Gov announcements & news (LLM-parsed sources)
        s.add(GovAnnouncement(
            source="BMRCL", title="Namma Metro Phase 2B Whitefield extension approved",
            category="metro", micro_market_id=mm.id,
            announced_at=dt.datetime.now() - dt.timedelta(days=40),
            extracted_signal="New metro corridor within 3km; positive demand catalyst (bull-case enabler).",
        ))
        s.add(NewsItem(
            source="ET Realty", title="Whitefield office absorption hits 2-year high",
            url="https://example.com/et-whitefield", micro_market_id=mm.id,
            published_at=dt.datetime.now() - dt.timedelta(days=10),
            relevance="high", extracted_signal="Office demand up -> residential demand tailwind.",
        ))

        print(f"Seeded Whitefield: {n_projects} projects, "
              f"{s.query(ReraTransaction).count()} transactions, "
              f"{len(POIS)} POIs, 6 GPL historical projects.")


if __name__ == "__main__":
    seed()
