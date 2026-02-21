from __future__ import annotations

import feedparser

from src.scrapers.base import BaseRegulatoryScraper


class FINRAScraper(BaseRegulatoryScraper):
    BASE_URL = "https://www.finra.org"
    RSS_FEED = "https://www.finra.org/rss"

    def __init__(self):
        super().__init__(base_url=self.BASE_URL)

    def scan(self, days_back: int = 7) -> list[dict]:
        items: list[dict] = []
        feed = feedparser.parse(self.RSS_FEED)
        for entry in feed.entries:
            title = entry.get("title", "")
            if "rule" not in title.lower() and "guidance" not in title.lower():
                continue
            items.append(
                {
                    "regulator": "FINRA",
                    "title": title,
                    "link": entry.get("link"),
                    "summary": entry.get("summary", ""),
                    "document_type": "notice",
                }
            )
        return self.dedupe(items)
