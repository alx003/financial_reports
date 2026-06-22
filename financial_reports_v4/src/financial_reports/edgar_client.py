"""Thin client for SEC EDGAR's XBRL companyfacts and submissions APIs.

Only the standard, consolidated financial-statement facts are pulled here
(top-level us-gaap tags with no dimensional/segment breakdown). The
companyfacts endpoint returns every fact a filer has ever reported,
including segment-level disaggregations under custom axes -- we never touch
those; metric_map.py only references whole-company GAAP concepts.
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

import requests

COMPANY_FACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik:010d}.json"
SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik:010d}.json"
TICKER_MAP_URL = "https://www.sec.gov/files/company_tickers.json"

REQUEST_DELAY_SECONDS = 0.15  # stay well under SEC's 10 req/sec limit


@dataclass
class EdgarClient:
    user_agent: str
    session: requests.Session | None = None

    def __post_init__(self) -> None:
        if not self.user_agent or "@" not in self.user_agent:
            raise ValueError(
                "A descriptive User-Agent with a contact email is required by SEC "
                "EDGAR. Set sec.user_agent in config/pipeline.yml."
            )
        self.session = self.session or requests.Session()
        self.session.headers.update(
            {"User-Agent": self.user_agent, "Accept-Encoding": "gzip, deflate"}
        )

    def _get_json(self, url: str) -> dict[str, Any]:
        resp = self.session.get(url, timeout=30)
        time.sleep(REQUEST_DELAY_SECONDS)
        resp.raise_for_status()
        return resp.json()

    def get_cik_for_ticker(self, ticker: str) -> int:
        data = self._get_json(TICKER_MAP_URL)
        ticker = ticker.upper()
        for row in data.values():
            if row.get("ticker", "").upper() == ticker:
                return int(row["cik_str"])
        raise ValueError(f"Ticker {ticker!r} not found in SEC ticker map.")

    def get_company_facts(self, cik: int) -> dict[str, Any]:
        return self._get_json(COMPANY_FACTS_URL.format(cik=cik))

    def get_submissions(self, cik: int) -> dict[str, Any]:
        return self._get_json(SUBMISSIONS_URL.format(cik=cik))
