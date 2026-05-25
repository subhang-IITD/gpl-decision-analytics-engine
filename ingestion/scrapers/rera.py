"""RERA portal scrapers (brief 3.1).

Karnataka (RERA Karnataka) and Maharashtra (MahaRERA) expose structured project
registries; UP-RERA and TN-RERA are scraped. Weekly refresh. Each state portal
has a different layout, so one adapter per state keeps selectors isolated.

Project registration records feed the `projects` and `rera_transactions` tables
and drive the new-filing competitive alert.
"""
from __future__ import annotations

from ingestion.scrapers.base import BaseScraper, ScrapeResult

RERA_PORTALS = {
    "Karnataka": "https://rera.karnataka.gov.in/projectViewDetails",
    "Maharashtra": "https://maharera.maharashtra.gov.in/projects-search-result",
    "UttarPradesh": "https://www.up-rera.in/projects",
    "TamilNadu": "https://rera.tn.gov.in/projects",
}


class ReraScraper(BaseScraper):
    source = "rera"

    def __init__(self, state: str = "Karnataka") -> None:
        super().__init__()
        self.state = state
        self.url = RERA_PORTALS.get(state, RERA_PORTALS["Karnataka"])

    def scrape(self, locality: str = "Whitefield", **_) -> ScrapeResult:
        html = self.fetch(self.url)
        if not html:
            return ScrapeResult(f"rera_{self.state}", ok=False,
                                note="live scraping disabled or blocked; use warehouse/PropEquity")
        return self._parse(html)

    def _parse(self, html: str) -> ScrapeResult:
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(html, "lxml")
        records: list[dict] = []
        # RERA registries render as tables; map the standard columns.
        for row in soup.select("table tbody tr"):
            cells = [c.get_text(strip=True) for c in row.select("td")]
            if len(cells) < 4:
                continue
            records.append({
                "rera_id": cells[0],
                "name": cells[1],
                "developer": cells[2],
                "status": cells[3],
                "source": "rera",
            })
        return ScrapeResult(f"rera_{self.state}", records=records, ok=True,
                            note=f"parsed {len(records)} projects")
