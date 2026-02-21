from __future__ import annotations

import feedparser

from src.scrapers.base import BaseRegulatoryScraper


class FCAScraper(BaseRegulatoryScraper):
    BASE_URL = "https://www.fca.org.uk"
    RSS_FEED = "https://www.fca.org.uk/news/rss.xml"

    def __init__(self):
        super().__init__(base_url=self.BASE_URL)

    def scan(self, days_back: int = 7) -> list[dict]:
        feed = feedparser.parse(self.RSS_FEED)
        items: list[dict] = []

        for entry in feed.entries:
            title = entry.get("title", "")
            if not any(k in title.lower() for k in ["policy", "consultation", "statement", "regulation"]):
                continue
            items.append(
                {
                    "regulator": "FCA",
                    "title": title,
                    "link": entry.get("link"),
                    "summary": entry.get("summary", ""),
                    "document_type": "guidance",
                }
            )

        return self.dedupe(items)
