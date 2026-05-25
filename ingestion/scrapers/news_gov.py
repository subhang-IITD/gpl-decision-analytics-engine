"""News (RSS) and government-announcement scrapers (brief 3.1).

News: RSS feeds (ET Realty, ToI Real Estate, Housing.com News) read via
feedparser, then LLM-classified for micro-market relevance. Daily.

Gov: BMRCL / NHAI / gazette pages scraped, then LLM-parsed to extract
infrastructure signals (metro corridor approvals, SEZ/IT-park notifications).
Weekly. Both route their text through the pluggable LLM provider -- snippet
only, never internal data.
"""
from __future__ import annotations

from ingestion.llm import get_llm_provider
from ingestion.scrapers.base import BaseScraper, ScrapeResult

NEWS_FEEDS = {
    "ET Realty": "https://realty.economictimes.indiatimes.com/rss/topstories",
    "Housing News": "https://housing.com/news/feed/",
}

GOV_SOURCES = {
    "BMRCL": "https://english.bmrc.co.in/press-release/",
    "NHAI": "https://nhai.gov.in/tenders",
}


class NewsScraper(BaseScraper):
    source = "news"

    def scrape(self, micro_market: str = "Whitefield", **_) -> ScrapeResult:
        if not self.live:
            return ScrapeResult(self.source, ok=False, note="live scraping disabled; use warehouse")
        import feedparser

        llm = get_llm_provider()
        records: list[dict] = []
        for src, url in NEWS_FEEDS.items():
            try:
                feed = feedparser.parse(url)
            except Exception:
                continue
            for entry in feed.entries[:25]:
                text = f"{entry.get('title','')} {entry.get('summary','')}"
                if micro_market.lower() not in text.lower():
                    continue
                extracted = llm.extract(text, task="news_classification")
                records.append({
                    "source": src,
                    "title": entry.get("title", ""),
                    "url": entry.get("link", ""),
                    "relevance": extracted.relevance,
                    "extracted_signal": extracted.summary,
                })
        return ScrapeResult(self.source, records=records, ok=True, note=f"{len(records)} relevant items")


class GovAnnouncementScraper(BaseScraper):
    source = "gov"

    def scrape(self, micro_market: str = "Whitefield", **_) -> ScrapeResult:
        if not self.live:
            return ScrapeResult(self.source, ok=False, note="live scraping disabled; use warehouse")
        from bs4 import BeautifulSoup

        llm = get_llm_provider()
        records: list[dict] = []
        for src, url in GOV_SOURCES.items():
            html = self.fetch(url)
            if not html:
                continue
            soup = BeautifulSoup(html, "lxml")
            for item in soup.select("a, li")[:60]:
                text = item.get_text(strip=True)
                if len(text) < 25:
                    continue
                extracted = llm.extract(text, task="gov_announcement")
                if "infrastructure_mentions" not in extracted.signals:
                    continue
                cats = extracted.signals["infrastructure_mentions"]
                records.append({
                    "source": src,
                    "title": text[:300],
                    "url": item.get("href") if item.name == "a" else url,
                    "category": cats[0] if cats else None,
                    "extracted_signal": extracted.summary,
                })
        return ScrapeResult(self.source, records=records, ok=True, note=f"{len(records)} announcements")
