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

## What it produces

- `outputs/FDX_financial_statements.xlsx` -- single sheet, all three
  statements stacked vertically (Income Statement → Balance Sheet → Cash
  Flow Statement), broker-style quarter/FY column layout.
- `dataset/FDX_financial_statements.csv` -- long-form CSV (one row per
  line item x period) for pandas/BI ingestion.

## Why only standard statements

SEC EDGAR's XBRL data includes both whole-company GAAP facts and
dimensional facts disaggregated by business segment, geography, or product
line (these use a separate `dimensions`/`segments` axis in the XBRL fact
object). This pipeline deliberately only reads top-level, non-dimensional
`us-gaap` facts -- the figures that appear on the face of the standard
financial statements in a 10-K/10-Q -- and ignores everything tagged with a
segment axis. See `metric_map.py` for the exact tag list.

## Quick start

```bash
pip install -r requirements.txt

# Update config/pipeline.yml -> sec.user_agent with a real contact email
# before running (SEC EDGAR requires this).

python scripts/run_pipeline.py --config config/pipeline.yml
# or, for a single ticker:
python scripts/run_pipeline.py --config config/pipeline.yml --ticker FDX
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

`.github/workflows/update-fdx-reports.yml` runs the pipeline weekly
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
outputs/                         # generated .xlsx (git-tracked, refreshed by CI)
dataset/                         # generated .csv (git-tracked, refreshed by CI)
.github/workflows/               # scheduled scrape-and-commit workflow
```

## Notes

- Units are exactly as reported in the XBRL filing (raw dollars, not
  thousands/millions) -- check the header note in the Excel output and the
  EDGAR filing itself if normalizing.
- This is independent of, but designed to sit alongside,
  [`us-company-sec-dataset`](https://github.com/alx003/us-company-sec-dataset),
  which covers a broader multi-company research database; this repo is
  scoped specifically to producing chart-ready, broker-style statement
  exports for a small set of tickers.
