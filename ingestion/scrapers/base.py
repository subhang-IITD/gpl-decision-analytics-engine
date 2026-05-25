"""Shared scraper plumbing.

Every scraper inherits BaseScraper. Live mode (GPL_LIVE_SCRAPING=true) performs
real HTTP fetches with a browser UA and polite throttling. When disabled, or
when a fetch fails / a site blocks us, scrapers return an empty result and the
ingestion runner sources from the warehouse instead. This guarantees the
pipeline is demonstrable in any environment and never hard-crashes on anti-bot
defences -- a documented, honest fallback rather than fake data.

For JavaScript-rendered portals (MagicBricks, 99acres) Playwright is the
production path; see fetch_rendered(). It is an optional dependency so the
base install stays light.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field

from config import get_settings


@dataclass
class ScrapeResult:
    source: str
    records: list[dict] = field(default_factory=list)
    ok: bool = True
    note: str = ""


class BaseScraper:
    source = "base"
    requires_js = False

    def __init__(self) -> None:
        self._cfg = get_settings().scraper

    @property
    def live(self) -> bool:
        return self._cfg.live_scraping_enabled

    def fetch(self, url: str) -> str | None:
        """Static HTML fetch (requests + BeautifulSoup downstream)."""
        if not self.live:
            return None
        try:
            import requests

            resp = requests.get(
                url,
                headers={"User-Agent": self._cfg.user_agent, "Accept-Language": "en-IN,en;q=0.9"},
                timeout=self._cfg.request_timeout_s,
            )
            resp.raise_for_status()
            time.sleep(1.0)  # polite throttle
            return resp.text
        except Exception:
            return None

    def fetch_rendered(self, url: str) -> str | None:
        """JS-rendered fetch via Playwright (optional dependency)."""
        if not self.live:
            return None
        try:
            from playwright.sync_api import sync_playwright

            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page(user_agent=self._cfg.user_agent)
                page.goto(url, timeout=int(self._cfg.request_timeout_s * 1000))
                page.wait_for_load_state("networkidle")
                html = page.content()
                browser.close()
                return html
        except Exception:
            return None

    def scrape(self, **kwargs) -> ScrapeResult:  # pragma: no cover
        raise NotImplementedError
