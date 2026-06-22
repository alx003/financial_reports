"""Turn raw SEC companyfacts JSON into clean per-period values for the
standard financial-statement line items defined in metric_map.py.

Handles the two messy realities of XBRL data:
  1. Duplicate facts -- the same fact gets re-reported across multiple
     filings (e.g. a 10-K restates prior quarters). We keep the value
     from the most-recently-filed accession number for a given period.
  2. Quarter derivation -- EDGAR gives cumulative duration facts (e.g.
     9-month YTD as of Q3) but not standalone quarters for flow items
     reported in 10-Ks. We derive Q4 = FY - (Q1+Q2+Q3) for flow items,
     and pull quarters directly from 10-Qs where available.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date

from .metric_map import ALL_LINE_ITEMS, COMPUTED_LINE_ITEMS, INSTANT_STATEMENT, LineItem


@dataclass(frozen=True)
class PeriodKey:
    """A reporting period: a fiscal-year-quarter label plus its end date,
    used as the column identity in the output workbook."""
    fiscal_year: int
    fiscal_period: str  # "Q1" | "Q2" | "Q3" | "Q4" | "FY"
    end_date: date

    @property
    def label(self) -> str:
        return f"{self.fiscal_period} {self.fiscal_year}"

    def sort_key(self) -> tuple:
        order = {"Q1": 1, "Q2": 2, "Q3": 3, "Q4": 4, "FY": 5}
        return (self.fiscal_year, order.get(self.fiscal_period, 9), self.end_date)


def _facts_for(company_facts: dict, tag: str) -> list[dict]:
    units = company_facts.get("facts", {}).get("us-gaap", {}).get(tag, {}).get("units", {})
    out: list[dict] = []
    for unit_name, facts in units.items():
        if unit_name not in ("USD", "USD/shares", "shares", "pure"):
            continue
        for fact in facts:
            fact_with_unit = dict(fact)
            fact_with_unit["_unit"] = unit_name
            out.append(fact_with_unit)
    return out


def _display_value(fact: dict) -> float:
    """Normalize large statement values to the workbook's millions convention."""
    value = fact["val"]
    if fact.get("_unit") in ("USD", "shares"):
        return value / 1_000_000
    return value


def _parse_date(s: str | None):
    if not s:
        return None
    y, m, d = s.split("-")
    return date(int(y), int(m), int(d))


def _infer_fiscal_year_end_month(company_facts: dict) -> int:
    """Infer the filer's fiscal year-end month from full-year duration facts."""
    months: Counter[int] = Counter()
    facts = company_facts.get("facts", {}).get("us-gaap", {})
    for concept in facts.values():
        for unit_facts in concept.get("units", {}).values():
            for fact in unit_facts:
                if fact.get("fp") != "FY" or "start" not in fact or "end" not in fact:
                    continue
                start = _parse_date(fact.get("start"))
                end = _parse_date(fact.get("end"))
                if start is None or end is None:
                    continue
                if 350 <= (end - start).days <= 380:
                    months[end.month] += 1
    return months.most_common(1)[0][0] if months else 12


def _fiscal_year_for_end(end: date, fiscal_year_end_month: int) -> int:
    return end.year if end.month <= fiscal_year_end_month else end.year + 1


def _quarter_for_end(end: date, fiscal_year_end_month: int) -> str | None:
    month_offset = (end.month - fiscal_year_end_month) % 12
    return {3: "Q1", 6: "Q2", 9: "Q3", 0: "Q4"}.get(month_offset)


def _period_from_fact(fact: dict, is_instant: bool,
                      fiscal_year_end_month: int) -> PeriodKey | None:
    """Classify a fact using the actual period dates, not the filing's fy/fp.

    SEC companyfacts reuses the filing's fy/fp on comparative facts. For
    example, a FY2026 10-Q can re-report a FY2025 quarter while still carrying
    fy=2026/fp=Q3. Deriving the fiscal year/quarter from the period end date
    prevents old comparative values from being mislabeled as current periods.
    """
    end = _parse_date(fact.get("end"))
    if end is None:
        return None
    fiscal_year = _fiscal_year_for_end(end, fiscal_year_end_month)
    quarter = _quarter_for_end(end, fiscal_year_end_month)
    if quarter is None:
        return None

    fp = fact.get("fp")
    if is_instant:
        if fp == "FY" and quarter == "Q4":
            return PeriodKey(fiscal_year, "FY", end)
        if fp in ("Q1", "Q2", "Q3", "Q4") and fp == quarter:
            return PeriodKey(fiscal_year, quarter, end)
        return None

    start = _parse_date(fact.get("start")) if fact.get("start") else None
    if start is None:
        return None
    span_days = (end - start).days
    if 350 <= span_days <= 380 and quarter == "Q4":
        return PeriodKey(fiscal_year, "FY", end)
    if 80 <= span_days <= 100:
        return PeriodKey(fiscal_year, quarter, end)
    if 100 < span_days < 350:
        return PeriodKey(fiscal_year, f"{quarter}_YTD", end)
    return None


def extract_line_item_series(company_facts: dict, item: LineItem,
                             fiscal_year_end_month: int) -> dict[PeriodKey, float]:
    """Return {PeriodKey: value} for a single line item, trying each tag in
    priority order and only filling periods not already covered."""
    is_instant = item.statement == INSTANT_STATEMENT
    result: dict[PeriodKey, float] = {}

    for tag in item.tags:
        raw_facts = _facts_for(company_facts, tag)
        best_for_period: dict[PeriodKey, dict] = {}

        for fact in raw_facts:
            if fact.get("form") not in ("10-Q", "10-K", "20-F", "40-F"):
                continue
            period = _period_from_fact(fact, is_instant, fiscal_year_end_month)
            if period is None:
                continue
            periods = [period]
            if is_instant and period.fiscal_period == "FY":
                periods.append(PeriodKey(period.fiscal_year, "Q4", period.end_date))
            for period_key in periods:
                prev = best_for_period.get(period_key)
                if prev is None or (
                    fact.get("filed", ""), fact.get("accn", "")
                ) >= (
                    prev.get("filed", ""), prev.get("accn", "")
                ):
                    best_for_period[period_key] = fact

        for period, fact in best_for_period.items():
            result.setdefault(period, _display_value(fact))

    return result


def derive_missing_quarters(series: dict[PeriodKey, float], item: LineItem) -> dict[PeriodKey, float]:
    """For flow (non-instant) items: if a standalone quarter is missing but
    we have YTD cumulative facts, derive it. Q4 = FY - (Q1+Q2+Q3) is the
    most common case since 10-Ks rarely restate a standalone Q4."""
    if item.statement == INSTANT_STATEMENT:
        return series

    by_fy: dict[int, dict[str, float]] = defaultdict(dict)
    for pk, val in series.items():
        by_fy[pk.fiscal_year][pk.fiscal_period] = val

    result = dict(series)
    for fy, periods in by_fy.items():
        fy_val = periods.get("FY")
        q1, q2, q3 = periods.get("Q1"), periods.get("Q2"), periods.get("Q3")
        q3_ytd = periods.get("Q3_YTD")
        if "Q4" not in periods and fy_val is not None:
            ytd_thru_q3 = q3_ytd if q3_ytd is not None else (
                (q1 + q2 + q3) if all(v is not None for v in (q1, q2, q3)) else None
            )
            if ytd_thru_q3 is not None:
                end_candidates = [pk.end_date for pk in series
                                   if pk.fiscal_year == fy and pk.fiscal_period == "FY"]
                if end_candidates:
                    result[PeriodKey(fy, "Q4", end_candidates[0])] = fy_val - ytd_thru_q3
        if "Q2" not in periods and "Q2_YTD" in periods and q1 is not None:
            ytd2 = periods["Q2_YTD"]
            end_candidates = [pk.end_date for pk in series
                               if pk.fiscal_year == fy and pk.fiscal_period == "Q2_YTD"]
            if end_candidates:
                result[PeriodKey(fy, "Q2", end_candidates[0])] = ytd2 - q1
        if "Q3" not in periods and "Q3_YTD" in periods and "Q2_YTD" in periods:
            ytd3 = periods["Q3_YTD"]
            ytd2 = periods["Q2_YTD"]
            end_candidates = [pk.end_date for pk in series
                               if pk.fiscal_year == fy and pk.fiscal_period == "Q3_YTD"]
            if end_candidates:
                result[PeriodKey(fy, "Q3", end_candidates[0])] = ytd3 - ytd2

    # Any remaining synthetic *_YTD keys could not be converted to a
    # standalone quarter (no prior-quarter or FY data to subtract). Rather
    # than discard this data -- it's real, filed data, just cumulative
    # rather than a single quarter -- keep it as its own period type
    # (e.g. "Q3_YTD") so it still appears in the output instead of vanishing
    # silently. This is the normal presentation for some filers' cash flow
    # statements (FedEx's 10-Qs, for example, only ever report cash flow
    # on a year-to-date basis, never as a standalone quarter).
    return result


def fill_computed_gaps(all_series: dict[str, dict[PeriodKey, float]],
                        max_passes: int = 5) -> dict[str, dict[PeriodKey, float]]:
    """Backfill gaps using COMPUTED_LINE_ITEMS -- purely arithmetic
    identities (e.g. Net Change in Cash = OCF + Investing + Financing + FX)
    evaluated only where the filed tag for that exact period is missing.

    Each term in a ComputedLineItem is marked required or optional:
      - A REQUIRED term with no value for the period blocks the whole
        computation for that period (left blank) -- these are core line
        items virtually every filer reports every period.
      - An OPTIONAL term with no value for the period is treated as 0 --
        these are episodic items (e.g. debt issuance, M&A, FX effects)
        that legitimately go unfiled in a period where nothing happened,
        not "missing data."
    A filed value is never overwritten by a computed one.

    Runs multiple passes so that one computed item (e.g. Total Liabilities)
    can supply an input for another (e.g. Total Liabilities & Stockholders'
    Equity) without needing to hand-order the dependency graph. Two line
    items can be mutually defined in terms of each other (Total Liabilities
    <-> Total Stockholders' Equity); this naturally resolves in whichever
    pass first has the *other* one of the pair available, and max_passes
    bounds the loop so a genuinely unresolvable gap just stops trying
    rather than looping forever.
    """
    result = {label: dict(series) for label, series in all_series.items()}

    for _ in range(max_passes):
        changed = False
        for computed in COMPUTED_LINE_ITEMS:
            target_series = result.setdefault(computed.label, {})
            all_periods: set[PeriodKey] = set()
            for term_label, _, _ in computed.terms:
                all_periods.update(result.get(term_label, {}).keys())

            for pk in all_periods:
                if pk in target_series:
                    continue  # filed (or already computed) value wins, never overwritten
                values = []
                complete = True
                any_term_present = False
                for term_label, sign, required in computed.terms:
                    v = result.get(term_label, {}).get(pk)
                    if v is None:
                        if required:
                            complete = False
                            break
                        v = 0.0  # optional term, legitimately absent -> treat as 0
                    else:
                        any_term_present = True
                    values.append(sign * v)
                # Require at least one term to have an actual filed/computed
                # value -- otherwise "all optional terms defaulted to 0"
                # would produce a spurious $0 total instead of staying blank.
                if complete and any_term_present:
                    target_series[pk] = sum(values)
                    changed = True
        if not changed:
            break

    return result


def extract_all_series(company_facts: dict) -> dict[str, dict[PeriodKey, float]]:
    """Return {line_item_label: {PeriodKey: value}} for every line item in
    the standard statement map, with computed-identity gaps backfilled."""
    fiscal_year_end_month = _infer_fiscal_year_end_month(company_facts)
    out: dict[str, dict[PeriodKey, float]] = {}
    for item in ALL_LINE_ITEMS:
        series = extract_line_item_series(company_facts, item, fiscal_year_end_month)
        series = derive_missing_quarters(series, item)
        out[item.label] = series
    out = fill_computed_gaps(out)
    return out


def collect_all_periods(all_series: dict[str, dict[PeriodKey, float]],
                        recent_quarters: int | None = None) -> list[PeriodKey]:
    seen: dict[tuple, PeriodKey] = {}
    for series in all_series.values():
        for pk in series:
            seen[(pk.fiscal_year, pk.fiscal_period, pk.end_date)] = pk
    periods = sorted(seen.values(), key=lambda pk: pk.sort_key())
    if recent_quarters is None:
        return periods

    quarters = [p for p in periods if p.fiscal_period in ("Q1", "Q2", "Q3", "Q4")]
    quarters = quarters[-recent_quarters:]
    if not quarters:
        return periods
    quarter_set = set(quarters)
    included_fiscal_years = {p.fiscal_year for p in quarters}
    return [
        p for p in periods
        if p in quarter_set
        or (p.fiscal_period == "FY" and p.fiscal_year in included_fiscal_years)
    ]


def filter_series_to_periods(all_series: dict[str, dict[PeriodKey, float]],
                             periods: list[PeriodKey]) -> dict[str, dict[PeriodKey, float]]:
    wanted = set(periods)
    return {
        label: {pk: val for pk, val in series.items() if pk in wanted}
        for label, series in all_series.items()
    }
