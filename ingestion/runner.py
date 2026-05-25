"""Ingestion orchestration -- one entry point per pipeline.

Each run is logged to the PipelineRun table so the admin dashboard can show
health and the Airflow DAGs can alert on failure (brief 5.3). In live mode the
scrapers/APIs fetch real data; otherwise these are no-ops that leave the seeded
warehouse intact, and the run is logged as 'partial' with an explanatory note.
"""
from __future__ import annotations

import datetime as dt

from db.schema import PipelineRun
from db.session import get_session
from ingestion.apis.propequity import PropEquityClient
from ingestion.scrapers.news_gov import GovAnnouncementScraper, NewsScraper
from ingestion.scrapers.portals import MagicBricksScraper, NinetyNineAcresScraper
from ingestion.scrapers.rera import ReraScraper


def _log(pipeline: str, status: str, n: int, detail: str) -> None:
    with get_session() as s:
        s.add(PipelineRun(
            pipeline=pipeline, status=status, records_ingested=n, detail=detail,
            started_at=dt.datetime.now(dt.timezone.utc),
            finished_at=dt.datetime.now(dt.timezone.utc),
        ))


def run_portals(city: str = "Bangalore", locality: str = "Whitefield") -> dict:
    total, notes = 0, []
    for scraper in (MagicBricksScraper(), NinetyNineAcresScraper()):
        res = scraper.scrape(city=city, locality=locality)
        total += len(res.records)
        notes.append(f"{res.source}: {res.note}")
    status = "success" if total else "partial"
    _log("portals_daily", status, total, "; ".join(notes))
    return {"records": total, "detail": notes, "status": status}


def run_rera(state: str = "Karnataka", locality: str = "Whitefield") -> dict:
    res = ReraScraper(state=state).scrape(locality=locality)
    status = "success" if res.ok and res.records else "partial"
    _log("rera_weekly", status, len(res.records), res.note)
    return {"records": len(res.records), "detail": res.note, "status": status}


def run_propequity(lat: float, lng: float, radius_km: float = 3.0) -> dict:
    client = PropEquityClient()
    rows = client.projects_near(lat, lng, radius_km) if client.live else []
    status = "success" if rows else "partial"
    note = "fetched from PropEquity" if rows else "no key -> warehouse used"
    _log("propequity_weekly", status, len(rows), note)
    return {"records": len(rows), "detail": note, "status": status}


def run_news_and_gov(micro_market: str = "Whitefield") -> dict:
    # live RSS fetch (works with a browser UA); logs its own PipelineRun
    from ingestion.scrapers.news_rss import fetch_news
    res = fetch_news(persist=True)
    return {"records": res["kept"], "detail": res["detail"], "status": "success" if res["kept"] else "partial"}


def run_portals_live(city: str = "Bangalore", locality: str = "Whitefield", proxy: str | None = None) -> dict:
    """Live Playwright scrape of MagicBricks (99acres analogous). Requires
    Playwright + chromium installed; proxy recommended in production."""
    from ingestion.scrapers.portals_playwright import scrape_magicbricks
    res = scrape_magicbricks(city=city, locality=locality, proxy=proxy)
    return {"records": res["records"], "detail": res["note"], "status": "success" if res["ok"] else "partial"}
