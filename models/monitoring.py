"""Sub-module 5: Competitive Monitoring (brief 2.5).

Scans the warehouse for decision-relevant changes and raises alerts:
  - new RERA filing within radius of an active GPL project
  - competitor listed-price change > 5%
  - absorption signal: project crosses 80% sold (tightening) or stalls (overhang)
  - government infrastructure announcements (LLM-parsed, already in warehouse)

Each alert is persisted (Alert table) and delivered via the alerting layer.
Designed to be run on a schedule by the Airflow monitoring DAG.
"""
from __future__ import annotations

import datetime as dt

from sqlalchemy import select

from config.defaults import (
    ABSORPTION_TIGHTENING_PCT,
    NEW_FILING_RADIUS_KM,
    PRICE_CHANGE_ALERT_PCT,
)
from db.schema import Alert, AlertSeverity, GovAnnouncement, Listing, Project
from db.session import get_session
from ingestion.apis.google_maps import haversine_m
from models.alerting import deliver


def _raise(session, kind: str, severity: AlertSeverity, mm_id: int | None, message: str, payload: dict) -> Alert:
    alert = Alert(kind=kind, severity=severity, micro_market_id=mm_id, message=message, payload=payload)
    session.add(alert)
    return alert


def scan(deliver_alerts: bool = True, lookback_days: int = 30) -> list[dict]:
    raised: list[dict] = []
    cutoff = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=lookback_days)
    with get_session() as s:
        projects = s.execute(select(Project)).scalars().all()
        gpl = [p for p in projects if p.is_gpl]
        listings = s.execute(select(Listing)).scalars().all()
        gov = s.execute(select(GovAnnouncement)).scalars().all()

        # 1) New filings near active GPL projects
        for comp in projects:
            if comp.is_gpl or not comp.launch_date:
                continue
            ld = comp.launch_date.date() if isinstance(comp.launch_date, dt.datetime) else comp.launch_date
            if (dt.date.today() - ld).days > lookback_days:
                continue
            for g in gpl:
                if haversine_m(g.lat, g.lng, comp.lat, comp.lng) / 1000.0 <= NEW_FILING_RADIUS_KM:
                    msg = f"New project '{comp.name}' ({comp.developer}) filed within {NEW_FILING_RADIUS_KM}km of GPL '{g.name}'."
                    _raise(s, "new_filing", AlertSeverity.warning, comp.micro_market_id, msg,
                           {"competitor": comp.name, "gpl_project": g.name})
                    raised.append({"kind": "new_filing", "message": msg})
                    break

        # 2) Competitor price changes > 5% (compare two most recent listings per project)
        by_proj: dict[int, list[Listing]] = {}
        for l in listings:
            by_proj.setdefault(l.project_id, []).append(l)
        for pid, ls in by_proj.items():
            ls.sort(key=lambda x: x.scraped_at or dt.datetime.min, reverse=True)
            if len(ls) >= 2 and ls[1].listed_price_per_sqft:
                change = (ls[0].listed_price_per_sqft - ls[1].listed_price_per_sqft) / ls[1].listed_price_per_sqft
                if abs(change) >= PRICE_CHANGE_ALERT_PCT:
                    proj = next((p for p in projects if p.id == pid), None)
                    msg = f"Listed price for '{proj.name if proj else pid}' changed {change:+.1%} (Rs.{ls[1].listed_price_per_sqft:,.0f} -> Rs.{ls[0].listed_price_per_sqft:,.0f})."
                    _raise(s, "price_change", AlertSeverity.warning, proj.micro_market_id if proj else None, msg,
                           {"change_pct": round(change, 4)})
                    raised.append({"kind": "price_change", "message": msg})

        # 3) Absorption signals
        for p in projects:
            pct = p.pct_sold
            if pct is None:
                continue
            if pct >= ABSORPTION_TIGHTENING_PCT:
                msg = f"'{p.name}' crossed {pct:.0%} sold -> supply tightening in {p.micro_market.name if p.micro_market else 'market'}."
                _raise(s, "absorption", AlertSeverity.info, p.micro_market_id, msg, {"pct_sold": round(pct, 3)})
                raised.append({"kind": "absorption", "message": msg})
            elif pct < 0.30 and p.status and p.status.value == "stalled":
                msg = f"'{p.name}' appears stalled at {pct:.0%} sold -> supply-overhang risk."
                _raise(s, "absorption", AlertSeverity.warning, p.micro_market_id, msg, {"pct_sold": round(pct, 3)})
                raised.append({"kind": "absorption", "message": msg})

        # 4) Government announcements (already LLM-parsed at ingestion)
        for g in gov:
            ann = g.announced_at
            if ann and ann.tzinfo is None:
                ann = ann.replace(tzinfo=dt.timezone.utc)
            if ann and ann >= cutoff:
                msg = f"Gov announcement [{g.category}]: {g.title} -- {g.extracted_signal or ''}"
                _raise(s, "gov", AlertSeverity.info, g.micro_market_id, msg, {"category": g.category})
                raised.append({"kind": "gov", "message": msg})

    if deliver_alerts and raised:
        summary = f"GPL Engine: {len(raised)} new competitive signal(s).\n\n" + "\n".join(f"- {r['message']}" for r in raised)
        deliver(summary, subject=f"[GPL Engine] {len(raised)} competitive alerts", whatsapp=True)

    return raised
