from __future__ import annotations

import feedparser

from src.scrapers.base import BaseRegulatoryScraper


class ECBScraper(BaseRegulatoryScraper):
    BASE_URL = "https://www.bankingsupervision.europa.eu"
    RSS_FEED = "https://www.ecb.europa.eu/rss/fxref-usd.html"

    def __init__(self):
        super().__init__(base_url=self.BASE_URL)

    def scan(self, days_back: int = 7) -> list[dict]:
        feed = feedparser.parse(self.RSS_FEED)
        items: list[dict] = []

        for entry in feed.entries:
            title = entry.get("title", "")
            if not any(k in title.lower() for k in ["supervision", "guidance", "bank", "regulation"]):
                continue
            items.append(
                {
                    "regulator": "ECB",
                    "title": title,
                    "link": entry.get("link"),
                    "summary": entry.get("summary", ""),
                    "document_type": "guidance",
                }
            )

        return self.dedupe(items)
