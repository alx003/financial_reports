#!/usr/bin/env python3
"""Run the full scrape -> extract -> report pipeline for the companies
listed in config/pipeline.yml.

Usage:
    python scripts/run_pipeline.py
    python scripts/run_pipeline.py --config config/pipeline.yml --ticker FDX
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from financial_reports.edgar_client import EdgarClient
from financial_reports.period_extraction import (
    collect_all_periods,
    extract_all_series,
    filter_series_to_periods,
)
from financial_reports.report_writer import write_csv, write_workbook

REPO_ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="config/pipeline.yml")
    parser.add_argument("--ticker", default=None, help="Only run a single ticker from the config")
    parser.add_argument("--years", type=int, default=None,
                        help="Number of recent quarterly years to include in outputs")
    args = parser.parse_args()

    config_path = REPO_ROOT / args.config
    config = yaml.safe_load(config_path.read_text())

    client = EdgarClient(user_agent=config["sec"]["user_agent"])
    companies = config["companies"]
    if args.ticker:
        companies = [c for c in companies if c["ticker"].upper() == args.ticker.upper()]
        if not companies:
            raise SystemExit(f"Ticker {args.ticker!r} not found in {args.config}")

    excel_dir = REPO_ROOT / config["output"]["excel_dir"]
    csv_dir = REPO_ROOT / config["output"]["csv_dir"]
    quarter_years = args.years or config.get("output", {}).get("quarter_years", 5)
    recent_quarters = quarter_years * 4 if quarter_years else None

    for company in companies:
        ticker = company["ticker"]
        name = company["name"]
        cik = company["cik"]
        print(f"[{ticker}] fetching company facts for CIK {cik}...")
        facts = client.get_company_facts(cik)

        print(f"[{ticker}] extracting standard financial-statement line items...")
        all_series = extract_all_series(facts)
        periods = collect_all_periods(all_series, recent_quarters=recent_quarters)
        all_series = filter_series_to_periods(all_series, periods)
        print(f"[{ticker}] found {len(periods)} reporting periods, "
              f"{sum(len(s) for s in all_series.values())} data points")

        empty_items = sorted(label for label, series in all_series.items() if not series)
        if empty_items:
            print(f"[{ticker}] WARNING: {len(empty_items)} line items had zero matching "
                  f"facts (filer may not report this concept, or may use a non-standard/"
                  f"custom XBRL tag not in metric_map.py -- check the filing directly "
                  f"before assuming the data doesn't exist):")
            for label in empty_items:
                print(f"    - {label}")

        xlsx_path = excel_dir / f"{ticker}_financial_statements.xlsx"
        csv_path = csv_dir / f"{ticker}_financial_statements.csv"
        write_workbook(
            all_series,
            periods,
            ticker,
            name,
            xlsx_path,
            units_note="USD and shares in millions; EPS as reported",
        )
        write_csv(all_series, periods, csv_path)
        print(f"[{ticker}] wrote {xlsx_path.relative_to(REPO_ROOT)} and {csv_path.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main()
