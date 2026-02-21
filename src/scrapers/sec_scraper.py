from __future__ import annotations

import time
from datetime import datetime, timedelta
from typing import Any

import feedparser
from bs4 import BeautifulSoup
from loguru import logger

from src.scrapers.base import BaseRegulatoryScraper


class SECRegulatoryScanner(BaseRegulatoryScraper):
    BASE_URL = "https://www.sec.gov"
    RSS_FEED = "https://www.sec.gov/news/pressreleases.rss"
    RULES_PAGE = "https://www.sec.gov/rules"

    def __init__(self, user_agent: str):
        super().__init__(base_url=self.BASE_URL, user_agent=user_agent)

    def scan_rss_feed(self, days_back: int = 7) -> list[dict[str, Any]]:
        cutoff_date = datetime.utcnow() - timedelta(days=days_back)
        feed = feedparser.parse(self.RSS_FEED)

        new_items: list[dict[str, Any]] = []
        for entry in feed.entries:
            published = datetime(*entry.published_parsed[:6]) if getattr(entry, "published_parsed", None) else None
            if published and published < cutoff_date:
                continue

            title = entry.get("title", "")
            if not any(k in title.lower() for k in ["rule", "guidance", "amend", "adopt", "regulation"]):
                continue

            new_items.append(
                {
                    "regulator": "SEC",
                    "title": title,
                    "link": entry.get("link"),
                    "published": published,
                    "summary": entry.get("summary", ""),
                    "document_type": self._classify_rule_type(title),
                }
            )

        logger.info("SEC RSS scan found {} candidate items", len(new_items))
        return new_items

    def scrape_rules_page(self, limit: int = 50) -> list[dict[str, Any]]:
        response = self.get(self.RULES_PAGE)
        if not response:
            return []

        soup = BeautifulSoup(response.content, "html.parser")

        rules: list[dict[str, Any]] = []
        for link in soup.select("a"):
            href = (link.get("href") or "").strip()
            text = link.get_text(" ", strip=True)
            if not href or not text:
                continue

            looks_regulatory = any(k in text.lower() for k in ["rule", "release", "guidance", "interpretive"])
            if not looks_regulatory:
                continue

            if href.startswith("/"):
                href = f"{self.BASE_URL}{href}"

            rules.append(
                {
                    "regulator": "SEC",
                    "title": text,
                    "link": href,
                    "date": None,
                    "document_type": self._classify_rule_type(text),
                }
            )

            if len(rules) >= limit:
                break
            time.sleep(0.05)

        logger.info("SEC rules-page scan found {} candidate items", len(rules))
        return rules

    def fetch_full_document(self, url: str) -> dict[str, Any]:
        response = self.get(url)
        if not response:
            return {"full_text": "", "pdf_url": None, "scraped_at": datetime.utcnow()}

        soup = BeautifulSoup(response.content, "html.parser")
        content = soup.find("div", {"id": "main-content"}) or soup.find("article") or soup.find("main")
        full_text = content.get_text("\n", strip=True) if content else soup.get_text("\n", strip=True)

        pdf_url = None
        pdf_anchor = soup.find("a", href=lambda href: href and href.lower().endswith(".pdf"))
        if pdf_anchor:
            href = pdf_anchor.get("href")
            if href:
                pdf_url = f"{self.BASE_URL}{href}" if href.startswith("/") else href

        return {"full_text": full_text, "pdf_url": pdf_url, "scraped_at": datetime.utcnow()}

    @staticmethod
    def _classify_rule_type(title: str) -> str:
        t = title.lower()
        if "proposed" in t:
            return "proposed_rule"
        if "final" in t or "adopt" in t:
            return "final_rule"
        if "guidance" in t or "interpret" in t:
            return "guidance"
        if "amend" in t:
            return "amendment"
        return "notice"
