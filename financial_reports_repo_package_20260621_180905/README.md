# financial_reports

Auto-scrapes standard SEC financial statements (Income Statement, Balance
Sheet, Cash Flow Statement -- **not** segment/business-unit data) from SEC
EDGAR's XBRL `companyfacts` API and writes them out in a broker-report-style
layout: quarters grouped under each fiscal year, a blank spacer column, an
FY total column, then a blank spacer column before the next fiscal year --
ready to drop straight into pivot tables or chart ranges.

Currently configured for **FedEx Corporation (FDX)**, CIK `1048911`. Add
more tickers to `config/pipeline.yml` to extend it to other companies; the
metric map (`src/financial_reports/metric_map.py`) uses generic GAAP tags so
it works for any filer without code changes, though line items a given
company doesn't report will simply come back blank.

> **⚠️ Known upcoming change, not yet handled:** FedEx's Board approved (1)
> a change in fiscal year end from May 31 to December 31, and (2) a spin-off
> of FedEx Freight as a separate public company, both expected effective
> **June 1, 2026** (per FedEx's FY2026 Q3 10-Q, filed 2026-03-19). Neither
> the fiscal-period derivation logic in `period_extraction.py` (which
> assumes a stable ~12-month fiscal year) nor the company scope in
> `config/pipeline.yml` (which currently represents FedEx as a single
> consolidated entity) accounts for this yet. Once the transition happens,
> expect a short/stub fiscal period in the data and a discontinuity in
> consolidated figures pre- vs. post-spin-off. Revisit before relying on
> FY2026-2027 boundary data.

## What it produces

- `outputs/FDX_financial_statements.xlsx` -- single sheet with two parts:
  1. **DASHBOARD** -- a 16-quarter rolling trend chart (Sales Analysis,
     Income Statement Analysis, Earnings Quality, Financial Strength, Cash
     Generation, Cash Deployment), with live `L10`/`L5`/`L3` rolling-average
     formulas. Columns immediately to the right of the latest reported
     quarter are deliberately left blank -- not zero, not estimated -- so
     the next quarter's data can be dropped straight in without restructuring
     the sheet. Any metric whose required line items aren't available for a
     given filer/period is left blank rather than guessed.
  2. **Standard financial statements** -- Income Statement → Balance Sheet →
     Cash Flow Statement, stacked vertically, broker-style quarter/FY column
     layout.
- `dataset/FDX_financial_statements.csv` -- long-form CSV (one row per
  line item x period) for pandas/BI ingestion.

This mirrors the Dashboard/Snapshot layout used in Langenberg & Co.'s
single-company research models (see `dashboard_metrics.py` for the metric
definitions and `report_writer.write_dashboard()` for the rendering logic).
When a new quarter is filed, `scripts/update_reports.py` fetches fresh SEC
data, rebuilds the workbook in the same tracked file, moves the rolling
dashboard window one quarter to the right, and places the newest statement
columns on the right side of the output tables.

## Why only standard statements

SEC EDGAR's XBRL data includes both whole-company GAAP facts and
dimensional facts disaggregated by business segment, geography, or product
line (these use a separate `dimensions`/`segments` axis in the XBRL fact
object). This pipeline deliberately only reads top-level, non-dimensional
`us-gaap` facts -- the figures that appear on the face of the standard
financial statements in a 10-K/10-Q -- and ignores everything tagged with a
segment axis. See `metric_map.py` for the exact tag list.

## Why some line items may still be blank for a real run

Two different things can cause a blank cell, and they mean different things:

1. **The pipeline genuinely has no data for that period yet** (e.g. the
   filer hasn't reported that quarter). Expected and correct -- this is
   the "open right edge" behavior described above.
2. **The filer uses a non-standard or custom XBRL tag** for a concept that
   `metric_map.py` only recognizes by its standard `us-gaap` tag name.
   FedEx is a known example: it doesn't report a standard `InventoryNet`
   line at all -- its 10-Ks show **"Spare parts, supplies and fuel, less
   allowances"** instead, which is likely tagged with a FedEx-specific
   custom element, not a generic `us-gaap` one. `metric_map.py` includes
   guessed fallback tag names for this, but they have **not been verified
   against a live SEC EDGAR response** (this development environment can't
   reach `data.sec.gov` directly).

Run `python scripts/update_reports.py` and check the console output: after
each ticker, it now prints a `WARNING` block listing every line item that
matched zero facts. Cross-reference that list against the company's actual
10-K to tell the two cases apart -- and if a real concept is being missed
because of a wrong/missing custom tag name, add the correct tag to
`metric_map.py`.

## Computed fallbacks for standard subtotals

Some standard subtotals (Pretax Income, Net Change in Cash, Total
Liabilities, etc.) are sometimes missing from a filer's own XBRL tags --
either the filer used a different tag than expected, or didn't report an
explicit total at all. Where a subtotal is a **purely arithmetic identity**
of other line items already in the output (e.g. `Net Change in Cash = OCF +
Investing CF + Financing CF + FX effect`, or the balance sheet's
`Assets = Liabilities + Equity`), `metric_map.COMPUTED_LINE_ITEMS` defines
the formula and `period_extraction.fill_computed_gaps()` evaluates it --
but only as a fallback, and only under strict rules:

- **A filed value always wins.** A computed value never overwrites
  something the filer actually reported.
- **Each formula term is marked required or optional.** Required terms
  (e.g. Revenue, Total Assets, Capital Expenditures -- core figures nearly
  every filer reports every period) must have an actual value or the whole
  computation is skipped for that period. Optional terms (e.g. Proceeds
  from Debt Issuance, Acquisitions -- episodic items that legitimately go
  unfiled in a quarter where nothing happened) default to $0 if absent.
- **No estimation or interpolation.** Every computed value is a strict sum
  of other values already present for that exact period -- nothing is
  carried forward, averaged, or guessed.

See `metric_map.py`'s `COMPUTED_LINE_ITEMS` for the full list of formulas
and the reasoning behind each term's required/optional designation.

## Cash flow statement: quarterly derivation

Some filers -- FedEx among them -- report many cash-flow statement figures
on a **year-to-date** basis in 10-Qs. `period_extraction.py` keeps those
YTD facts and derives standalone quarters by subtraction when the necessary
prior period is available: `Q2 = Q2_YTD - Q1`, `Q3 = Q3_YTD - Q2_YTD`, and
`Q4 = FY - Q3_YTD`. Any YTD value that cannot be converted without guessing
stays out of the quarter-by-quarter Excel grid.

By default, the pipeline writes a rolling five-year quarterly window
(`output.quarter_years: 5`), so the workbook and CSV include the latest
20 quarters plus available FY total columns.

## Quick Start

```bash
pip install -r requirements.txt

# Update config/pipeline.yml -> sec.user_agent with a real contact email
# before running (SEC EDGAR requires this).

python scripts/update_reports.py --config config/pipeline.yml
# or, for a single ticker:
python scripts/update_reports.py --config config/pipeline.yml --ticker FDX
```

`scripts/update_reports.py` is the script to keep in git and use for
ongoing refreshes. By default it:

- pulls latest SEC EDGAR companyfacts data,
- extracts the latest five years of quarterly financial statements,
- makes a timestamped backup of the existing workbook in `backups/`,
- overwrites `outputs/<TICKER>_financial_statements.xlsx`, and
- overwrites `dataset/<TICKER>_financial_statements.csv`.

Useful options:

```bash
# Refresh without creating a local backup, useful in CI.
python scripts/update_reports.py --no-backup

# Change the rolling quarterly window.
python scripts/update_reports.py --years 6

# Check whether a new filing would change the output without writing files.
python scripts/update_reports.py --dry-run
```

## How periods are derived

EDGAR's `companyfacts` endpoint reports duration facts as filed --
standalone 3-month figures from 10-Qs, cumulative year-to-date figures
(6-month, 9-month), and full-year figures from 10-Ks. It does **not**
generally provide a standalone Q4. `period_extraction.py` reconciles this:

1. Deduplicates facts that get re-reported across multiple filings (e.g. a
   10-K that restates prior quarters), keeping the most recently filed
   value for each period.
2. Classifies each duration fact by its span length (~90 days = single
   quarter, ~365 days = full year, anything longer = YTD cumulative).
3. Derives missing standalone quarters by subtraction: `Q4 = FY - (Q1+Q2+Q3)`,
   `Q2 = 6-month YTD - Q1`, `Q3 = 9-month YTD - 6-month YTD`.

Balance sheet items are point-in-time balances and are matched directly by
period-end date with no derivation needed.

## GitHub Actions

`.github/workflows/update-fdx-reports.yml` runs the updater weekly
(Mondays, 12:00 UTC) and on manual dispatch, committing refreshed
`outputs/*.xlsx` and `dataset/*.csv` files back to the repo. No secrets are
required -- SEC EDGAR's API is free and unauthenticated, it just requires a
descriptive `User-Agent` header (configured in `config/pipeline.yml`).

## Repo layout

```
config/pipeline.yml              # tickers, CIKs, SEC user-agent, output paths
src/financial_reports/
  edgar_client.py                 # SEC EDGAR API client (companyfacts, submissions)
  metric_map.py                   # standard statement line items -> us-gaap tags
  period_extraction.py            # raw facts -> clean per-period values
  report_writer.py                # broker-style Excel + long-form CSV writer
scripts/run_pipeline.py          # orchestrates fetch -> extract -> write
scripts/update_reports.py        # automation-friendly updater for local/CI refreshes
outputs/                         # generated .xlsx (git-tracked, refreshed by CI)
dataset/                         # generated .csv (git-tracked, refreshed by CI)
.github/workflows/               # scheduled scrape-and-commit workflow
```

## Notes

- USD and share-count facts are normalized to millions in the workbook and
  CSV; EPS and ratio-style facts stay as reported.
- This is independent of, but designed to sit alongside,
  [`us-company-sec-dataset`](https://github.com/alx003/us-company-sec-dataset),
  which covers a broader multi-company research database; this repo is
  scoped specifically to producing chart-ready, broker-style statement
  exports for a small set of tickers.
