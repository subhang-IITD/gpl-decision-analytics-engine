"""Live news RSS scraper (brief 3.1) -- genuinely runnable.

Real estate RSS feeds block bare feedparser, so we fetch with a browser
User-Agent via requests, then parse with feedparser. Each item is classified by
the pluggable LLM for micro-market relevance and written to the warehouse.

Verified working against ET Realty (returns real articles). Run:
    python -m ingestion.scrapers.news_rss
"""
from __future__ import annotations

import datetime as dt

import feedparser
import requests

from db.schema import NewsItem, PipelineRun
from db.session import get_session
from ingestion.llm import get_llm_provider

FEEDS = {
    "ET Realty": "https://realty.economictimes.indiatimes.com/rss/topstories",
    "Housing News": "https://housing.com/news/feed/",
    "ToI Real Estate": "https://timesofindia.indiatimes.com/rssfeeds/54829575.cms",
}
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"


def fetch_news(micro_markets: list[str] | None = None, persist: bool = True) -> dict:
    """Fetch + classify news. If micro_markets given, only keep matching items."""
    llm = get_llm_provider()
    kept, scanned, notes = 0, 0, []
    started = dt.datetime.now(dt.timezone.utc)

    for source, url in FEEDS.items():
        try:
            resp = requests.get(url, headers={"User-Agent": UA}, timeout=20)
            resp.raise_for_status()
            feed = feedparser.parse(resp.content)
        except Exception as exc:
            notes.append(f"{source}: fetch failed ({exc})")
            continue
        scanned += len(feed.entries)
        for entry in feed.entries[:40]:
            title = entry.get("title", "")
            summary = entry.get("summary", "")
            text = f"{title} {summary}"
            mm_match = None
            if micro_markets:
                mm_match = next((m for m in micro_markets if m.split("(")[0].strip().lower() in text.lower()), None)
                if not mm_match:
                    continue
            extracted = llm.extract(text, task="news_classification")
            if persist:
                with get_session() as s:
                    s.add(NewsItem(
                        source=source, title=title[:400], url=entry.get("link", "")[:600],
                        published_at=_parse_published(entry),
                        relevance=extracted.relevance, extracted_signal=extracted.summary[:1000],
                    ))
            kept += 1
        notes.append(f"{source}: {len(feed.entries)} items")

    if persist:
        with get_session() as s:
            s.add(PipelineRun(pipeline="news_rss_daily", status="success" if kept else "partial",
                              records_ingested=kept, detail="; ".join(notes),
                              started_at=started, finished_at=dt.datetime.now(dt.timezone.utc)))
    return {"scanned": scanned, "kept": kept, "detail": notes}


def _parse_published(entry) -> dt.datetime | None:
    if getattr(entry, "published_parsed", None):
        import time
        return dt.datetime.fromtimestamp(time.mktime(entry.published_parsed))
    return None


if __name__ == "__main__":
    print(fetch_news(persist=True))
