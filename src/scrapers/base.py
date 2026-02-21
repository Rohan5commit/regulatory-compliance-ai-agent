from __future__ import annotations

from datetime import datetime
from email.utils import parsedate_to_datetime
from typing import Any

import requests
from loguru import logger


class BaseRegulatoryScraper:
    def __init__(self, base_url: str, user_agent: str | None = None):
        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": user_agent or "RegulatoryComplianceBot/1.0 (contact@example.com)",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            }
        )

    def get(self, url: str, timeout: int = 30) -> requests.Response | None:
        try:
            response = self.session.get(url, timeout=timeout)
            response.raise_for_status()
            return response
        except Exception as exc:
            logger.warning("Scraper request failed for {}: {}", url, exc)
            return None

    @staticmethod
    def normalize_date(value: str | None) -> datetime | None:
        if not value:
            return None
        try:
            return parsedate_to_datetime(value)
        except Exception:
            pass

        for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%B %d, %Y", "%d %B %Y"):
            try:
                return datetime.strptime(value.strip(), fmt)
            except Exception:
                continue
        return None

    @staticmethod
    def dedupe(items: list[dict[str, Any]], key: str = "link") -> list[dict[str, Any]]:
        deduped: dict[str, dict[str, Any]] = {}
        for item in items:
            k = item.get(key)
            if not k:
                continue
            deduped[str(k)] = item
        return list(deduped.values())
