from __future__ import annotations

import asyncio
from typing import Any

from loguru import logger

from src.scrapers.ecb_scraper import ECBScraper
from src.scrapers.fca_scraper import FCAScraper
from src.scrapers.finra_scraper import FINRAScraper
from src.scrapers.mas_scraper import MASScraper
from src.scrapers.sec_scraper import SECRegulatoryScanner


class MultiRegulatorScanner:
    def __init__(self, config: dict[str, str]):
        self.sec_scanner = SECRegulatoryScanner(config.get("SEC_EDGAR_USER_AGENT", "ComplianceBot contact@example.com"))
        self.finra_scanner = FINRAScraper()
        self.mas_scanner = MASScraper()
        self.fca_scanner = FCAScraper()
        self.ecb_scanner = ECBScraper()

        self.active_scanners = ["SEC", "FINRA", "MAS", "FCA", "ECB"]

    async def scan_all_regulators(self, days_back: int = 7) -> dict[str, list[dict[str, Any]]]:
        scanner_tasks: dict[str, asyncio.Future] = {}

        if "SEC" in self.active_scanners:
            scanner_tasks["SEC"] = asyncio.create_task(self._scan_sec(days_back))
        if "FINRA" in self.active_scanners:
            scanner_tasks["FINRA"] = asyncio.create_task(self._run_sync(self.finra_scanner.scan, days_back))
        if "MAS" in self.active_scanners:
            scanner_tasks["MAS"] = asyncio.create_task(self._run_sync(self.mas_scanner.scan, days_back))
        if "FCA" in self.active_scanners:
            scanner_tasks["FCA"] = asyncio.create_task(self._run_sync(self.fca_scanner.scan, days_back))
        if "ECB" in self.active_scanners:
            scanner_tasks["ECB"] = asyncio.create_task(self._run_sync(self.ecb_scanner.scan, days_back))

        results: dict[str, list[dict[str, Any]]] = {}
        for regulator, task in scanner_tasks.items():
            try:
                results[regulator] = await task
            except Exception as exc:
                logger.error("Failed scanning {}: {}", regulator, exc)
                results[regulator] = []

        return results

    async def _scan_sec(self, days_back: int) -> list[dict[str, Any]]:
        rss_items = await self._run_sync(self.sec_scanner.scan_rss_feed, days_back)
        rules_items = await self._run_sync(self.sec_scanner.scrape_rules_page)
        all_items = rss_items + rules_items
        return self.sec_scanner.dedupe(all_items, key="link")

    @staticmethod
    async def _run_sync(func, *args):
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, lambda: func(*args))
