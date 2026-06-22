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

from collections import defaultdict
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
        out.extend(facts)
    return out


def _dedupe_latest_filed(facts: list[dict]) -> dict[tuple, dict]:
    """Collapse duplicate (start,end,fy,fp) facts to the one from the most
    recent filing (by accession number, which is monotonically increasing)."""
    best: dict[tuple, dict] = {}
    for fact in facts:
        key = (fact.get("start"), fact["end"], fact.get("fy"), fact.get("fp"))
        prev = best.get(key)
        if prev is None or fact.get("accn", "") >= prev.get("accn", ""):
            best[key] = fact
    return best


def _parse_date(s: str | None):
    if not s:
        return None
    y, m, d = s.split("-")
    return date(int(y), int(m), int(d))


def extract_line_item_series(company_facts: dict, item: LineItem) -> dict[PeriodKey, float]:
    """Return {PeriodKey: value} for a single line item, trying each tag in
    priority order and only filling periods not already covered."""
    is_instant = item.statement == INSTANT_STATEMENT
    result: dict[PeriodKey, float] = {}

    for tag in item.tags:
        raw_facts = _facts_for(company_facts, tag)
        deduped = _dedupe_latest_filed(raw_facts)

        for fact in deduped.values():
            fp = fact.get("fp")  # "Q1","Q2","Q3","FY"
            fy = fact.get("fy")
            form = fact.get("form", "")
            if fy is None or fp is None:
                continue
            end = _parse_date(fact["end"])
            start = _parse_date(fact.get("start")) if fact.get("start") else None

            if is_instant:
                period = PeriodKey(fy, fp, end)
                if period not in result:
                    result[period] = fact["val"]
                continue

            if start is None:
                continue
            span_days = (end - start).days
            if fp == "FY" and 350 <= span_days <= 380:
                period = PeriodKey(fy, "FY", end)
                result.setdefault(period, fact["val"])
            elif fp in ("Q1", "Q2", "Q3", "Q4") and 80 <= span_days <= 100:
                period = PeriodKey(fy, fp, end)
                result.setdefault(period, fact["val"])
            elif fp in ("Q1", "Q2", "Q3", "Q4") and span_days > 100:
                # Cumulative YTD fact (e.g. 6-mo, 9-mo) -- stashed under a
                # synthetic period so the Q4-derivation step below can use it.
                ytd_period = PeriodKey(fy, f"{fp}_YTD", end)
                result.setdefault(ytd_period, fact["val"])

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

    return {pk: v for pk, v in result.items() if not pk.fiscal_period.endswith("_YTD")}


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
    out: dict[str, dict[PeriodKey, float]] = {}
    for item in ALL_LINE_ITEMS:
        series = extract_line_item_series(company_facts, item)
        series = derive_missing_quarters(series, item)
        out[item.label] = series
    out = fill_computed_gaps(out)
    return out


def collect_all_periods(all_series: dict[str, dict[PeriodKey, float]]) -> list[PeriodKey]:
    seen: dict[tuple, PeriodKey] = {}
    for series in all_series.values():
        for pk in series:
            seen[(pk.fiscal_year, pk.fiscal_period)] = pk
    return sorted(seen.values(), key=lambda pk: pk.sort_key())
