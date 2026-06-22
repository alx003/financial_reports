#!/usr/bin/env python3
"""Fetch latest SEC data and refresh tracked Excel/CSV outputs.

This is the automation-friendly entry point for the repo. It pulls fresh
companyfacts data from SEC EDGAR, extracts the configured rolling quarterly
window, and writes the refreshed workbook/CSV back to the output paths in
config/pipeline.yml. Re-running it after a new 10-Q/10-K is filed adds the
new quarter to the right side of the financial statement grids and rolls the
dashboard trend window forward.

Usage:
    python scripts/update_reports.py
    python scripts/update_reports.py --ticker FDX
    python scripts/update_reports.py --years 5 --no-backup
"""
from __future__ import annotations

import argparse
import shutil
import sys
from datetime import datetime
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from financial_reports.edgar_client import EdgarClient
from financial_reports.period_extraction import (
    PeriodKey,
    collect_all_periods,
    extract_all_series,
    filter_series_to_periods,
)
from financial_reports.report_writer import write_csv, write_workbook

REPO_ROOT = Path(__file__).resolve().parents[1]
UNITS_NOTE = "USD and shares in millions; EPS as reported"


def _latest_quarter(periods: list[PeriodKey]) -> PeriodKey | None:
    quarters = [p for p in periods if p.fiscal_period in ("Q1", "Q2", "Q3", "Q4")]
    return max(quarters, key=lambda p: p.sort_key()) if quarters else None


def _backup_file(path: Path, backup_dir: Path) -> Path | None:
    if not path.exists():
        return None
    backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = backup_dir / f"{path.stem}_{stamp}{path.suffix}"
    shutil.copy2(path, backup_path)
    return backup_path


def _selected_companies(config: dict, ticker: str | None) -> list[dict]:
    companies = config["companies"]
    if ticker is None:
        return companies
    selected = [c for c in companies if c["ticker"].upper() == ticker.upper()]
    if not selected:
        raise SystemExit(f"Ticker {ticker!r} not found in config.")
    return selected


def refresh_company(
    client: EdgarClient,
    company: dict,
    excel_dir: Path,
    csv_dir: Path,
    quarter_years: int,
    make_backup: bool,
    backup_dir: Path,
    dry_run: bool,
) -> None:
    ticker = company["ticker"].upper()
    name = company["name"]
    cik = company["cik"]
    recent_quarters = quarter_years * 4 if quarter_years else None

    print(f"[{ticker}] fetching SEC companyfacts for CIK {cik}...")
    facts = client.get_company_facts(cik)

    print(f"[{ticker}] extracting latest {quarter_years} years of quarterly data...")
    all_series = extract_all_series(facts)
    periods = collect_all_periods(all_series, recent_quarters=recent_quarters)
    all_series = filter_series_to_periods(all_series, periods)
    latest = _latest_quarter(periods)

    data_points = sum(len(series) for series in all_series.values())
    latest_label = latest.label if latest is not None else "no quarter found"
    print(f"[{ticker}] prepared {len(periods)} periods, {data_points} data points; latest {latest_label}.")

    xlsx_path = excel_dir / f"{ticker}_financial_statements.xlsx"
    csv_path = csv_dir / f"{ticker}_financial_statements.csv"
    if dry_run:
        print(f"[{ticker}] dry run only; would write {xlsx_path} and {csv_path}.")
        return

    if make_backup:
        backup = _backup_file(xlsx_path, backup_dir)
        if backup is not None:
            print(f"[{ticker}] backup saved to {backup.relative_to(REPO_ROOT)}")

    write_workbook(all_series, periods, ticker, name, xlsx_path, units_note=UNITS_NOTE)
    write_csv(all_series, periods, csv_path)
    print(f"[{ticker}] refreshed {xlsx_path.relative_to(REPO_ROOT)}")
    print(f"[{ticker}] refreshed {csv_path.relative_to(REPO_ROOT)}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Refresh financial report workbook/CSV outputs.")
    parser.add_argument("--config", default="config/pipeline.yml")
    parser.add_argument("--ticker", default=None, help="Only refresh one ticker from the config")
    parser.add_argument("--years", type=int, default=None,
                        help="Rolling number of quarterly years to keep in outputs")
    parser.add_argument("--no-backup", action="store_true",
                        help="Do not copy the existing workbook before overwriting it")
    parser.add_argument("--backup-dir", default="backups",
                        help="Directory for timestamped workbook backups")
    parser.add_argument("--dry-run", action="store_true",
                        help="Fetch and extract data, but do not write output files")
    args = parser.parse_args()

    config_path = REPO_ROOT / args.config
    config = yaml.safe_load(config_path.read_text())
    quarter_years = args.years or config.get("output", {}).get("quarter_years", 5)

    client = EdgarClient(user_agent=config["sec"]["user_agent"])
    excel_dir = REPO_ROOT / config["output"]["excel_dir"]
    csv_dir = REPO_ROOT / config["output"]["csv_dir"]
    backup_dir = REPO_ROOT / args.backup_dir

    for company in _selected_companies(config, args.ticker):
        refresh_company(
            client=client,
            company=company,
            excel_dir=excel_dir,
            csv_dir=csv_dir,
            quarter_years=quarter_years,
            make_backup=not args.no_backup,
            backup_dir=backup_dir,
            dry_run=args.dry_run,
        )


if __name__ == "__main__":
    main()
