"""Listed-price scrapers for MagicBricks / 99acres / NoBroker (brief 3.1).

These portals are JavaScript-rendered, so production uses fetch_rendered()
(Playwright). The parse_* methods target the listing-card structure each portal
exposes; selectors are isolated here so the admin can update them when a portal
changes its markup (see docs/ADMIN_GUIDE.md). Daily refresh.
"""
from __future__ import annotations

import re

from ingestion.scrapers.base import BaseScraper, ScrapeResult


class MagicBricksScraper(BaseScraper):
    source = "magicbricks"
    requires_js = True
    SEARCH_URL = "https://www.magicbricks.com/property-for-sale/residential-real-estate?proptype=Multistorey-Apartment&cityName={city}&Locality={locality}"

    def scrape(self, city: str = "Bangalore", locality: str = "Whitefield", **_) -> ScrapeResult:
        html = self.fetch_rendered(self.SEARCH_URL.format(city=city, locality=locality))
        if not html:
            return ScrapeResult(self.source, ok=False, note="live scraping disabled or blocked; use warehouse")
        return self._parse(html)

    def _parse(self, html: str) -> ScrapeResult:
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(html, "lxml")
        records: list[dict] = []
        for card in soup.select("div.mb-srp__card"):
            name = card.select_one(".mb-srp__card--title")
            psf = card.select_one(".mb-srp__card__price--size")
            cfg = card.select_one(".mb-srp__card--title")
            if not (name and psf):
                continue
            m = re.search(r"([\d,]+)", psf.get_text())
            records.append({
                "portal": self.source,
                "project_name": name.get_text(strip=True),
                "config_type": _infer_config(cfg.get_text() if cfg else ""),
                "listed_price_per_sqft": float(m.group(1).replace(",", "")) if m else None,
            })
        return ScrapeResult(self.source, records=records, ok=True, note=f"parsed {len(records)} cards")


class NinetyNineAcresScraper(BaseScraper):
    source = "99acres"
    requires_js = True
    SEARCH_URL = "https://www.99acres.com/search/property/buy/{locality}-{city}?city=20&preference=S"

    def scrape(self, city: str = "bangalore", locality: str = "whitefield", **_) -> ScrapeResult:
        html = self.fetch_rendered(self.SEARCH_URL.format(city=city, locality=locality))
        if not html:
            return ScrapeResult(self.source, ok=False, note="live scraping disabled or blocked; use warehouse")
        return self._parse(html)

    def _parse(self, html: str) -> ScrapeResult:
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(html, "lxml")
        records: list[dict] = []
        for card in soup.select("section.tupleNew__contentWrap, div.srpTuple__tupleDetails"):
            title = card.select_one("a.tupleNew__propertyHeading, h2")
            psf = card.find(string=re.compile(r"per sqft|/sqft", re.I))
            if not title:
                continue
            m = re.search(r"([\d,]+)", psf) if psf else None
            records.append({
                "portal": self.source,
                "project_name": title.get_text(strip=True),
                "config_type": _infer_config(title.get_text()),
                "listed_price_per_sqft": float(m.group(1).replace(",", "")) if m else None,
            })
        return ScrapeResult(self.source, records=records, ok=True, note=f"parsed {len(records)} cards")


def _infer_config(text: str) -> str:
    t = text.lower()
    if "3.5" in t:
        return "3.5BHK"
    for n in ("4", "3", "2"):
        if f"{n} bhk" in t or f"{n}bhk" in t:
            return f"{n}BHK"
    return "3BHK"
