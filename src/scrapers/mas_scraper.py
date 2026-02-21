from __future__ import annotations

import feedparser

from src.scrapers.base import BaseRegulatoryScraper


class MASScraper(BaseRegulatoryScraper):
    BASE_URL = "https://www.mas.gov.sg"
    RSS_FEED = "https://www.mas.gov.sg/rss/mas"

    def __init__(self):
        super().__init__(base_url=self.BASE_URL)

    def scan(self, days_back: int = 7) -> list[dict]:
        feed = feedparser.parse(self.RSS_FEED)
        items: list[dict] = []

        for entry in feed.entries:
            title = entry.get("title", "")
            if not any(k in title.lower() for k in ["notice", "guideline", "regulation"]):
                continue
            items.append(
                {
                    "regulator": "MAS",
                    "title": title,
                    "link": entry.get("link"),
                    "summary": entry.get("summary", ""),
                    "document_type": "notice",
                }
            )

        return self.dedupe(items)
