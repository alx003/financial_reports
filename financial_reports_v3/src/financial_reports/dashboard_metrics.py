"""Dashboard trend-chart metric definitions.

Mirrors the Langenberg & Co. BA model's Dashboard section: a set of derived
ratios/metrics (margins, coverage, turnover, etc.) computed quarter-by-
quarter from the raw financial-statement line items in metric_map.py, shown
as a 16-quarter rolling trend with L10/L5/L3 averages alongside it.

Each metric is a function of the period's raw line-item series rather than
its own XBRL tag, since these are computed ratios, not filed facts. A
metric silently returns None for a period if any required input is missing
-- it is never estimated or interpolated.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from .period_extraction import PeriodKey

MetricFunc = Callable[[dict[str, dict[PeriodKey, float]], PeriodKey], float | None]


@dataclass(frozen=True)
class DashboardMetric:
    label: str
    section: str  # which Dashboard sub-table this belongs to
    func: MetricFunc
    is_percent: bool = False
    indent: int = 0


def _get(all_series: dict[str, dict[PeriodKey, float]], label: str, pk: PeriodKey) -> float | None:
    return all_series.get(label, {}).get(pk)


def _safe_div(a: float | None, b: float | None) -> float | None:
    if a is None or b is None or b == 0:
        return None
    return a / b


# ---------------------------------------------------------------------------
# SALES ANALYSIS
# ---------------------------------------------------------------------------

def _revenue_yoy(all_series, pk: PeriodKey) -> float | None:
    prior = PeriodKey(pk.fiscal_year - 1, pk.fiscal_period, pk.end_date)
    cur = _get(all_series, "Revenue", pk)
    prior_series = all_series.get("Revenue", {})
    prior_val = next((v for k, v in prior_series.items()
                       if k.fiscal_year == prior.fiscal_year and k.fiscal_period == prior.fiscal_period), None)
    if cur is None or prior_val in (None, 0):
        return None
    return (cur / prior_val) - 1


# ---------------------------------------------------------------------------
# INCOME STATEMENT ANALYSIS (margins)
# ---------------------------------------------------------------------------

def _operating_margin(all_series, pk: PeriodKey) -> float | None:
    return _safe_div(_get(all_series, "Operating Income", pk), _get(all_series, "Revenue", pk))


def _net_margin(all_series, pk: PeriodKey) -> float | None:
    return _safe_div(_get(all_series, "Net Income", pk), _get(all_series, "Revenue", pk))


def _sga_pct_revenue(all_series, pk: PeriodKey) -> float | None:
    return _safe_div(_get(all_series, "  Selling, General & Administrative", pk),
                      _get(all_series, "Revenue", pk))


# ---------------------------------------------------------------------------
# EARNINGS QUALITY
# ---------------------------------------------------------------------------

def _adj_eps_yoy(all_series, pk: PeriodKey) -> float | None:
    cur = _get(all_series, "EPS - Diluted", pk)
    prior_series = all_series.get("EPS - Diluted", {})
    prior_val = next((v for k, v in prior_series.items()
                       if k.fiscal_year == pk.fiscal_year - 1 and k.fiscal_period == pk.fiscal_period), None)
    if cur is None or prior_val in (None, 0):
        return None
    return (cur / prior_val) - 1


def _fcf_pct_net_income(all_series, pk: PeriodKey) -> float | None:
    ocf = _get(all_series, "Net Cash from Operating Activities", pk)
    capex = _get(all_series, "Capital Expenditures", pk)
    ni = _get(all_series, "Net Income", pk)
    if ocf is None or capex is None or ni in (None, 0):
        return None
    fcf = ocf - abs(capex)
    return fcf / ni


# ---------------------------------------------------------------------------
# FINANCIAL STRENGTH
# ---------------------------------------------------------------------------

def _current_ratio(all_series, pk: PeriodKey) -> float | None:
    return _safe_div(_get(all_series, "Total Current Assets", pk), _get(all_series, "Total Current Liabilities", pk))


def _net_debt_to_assets(all_series, pk: PeriodKey) -> float | None:
    ltd = _get(all_series, "Long-Term Debt, Net", pk) or 0
    cur_d = _get(all_series, "Current Portion of Long-Term Debt", pk) or 0
    cash = _get(all_series, "Cash & Cash Equivalents", pk)
    assets = _get(all_series, "Total Assets", pk)
    if cash is None or assets in (None, 0):
        return None
    return ((ltd + cur_d) - cash) / assets


# ---------------------------------------------------------------------------
# CASH GENERATION
# ---------------------------------------------------------------------------

def _ocf_pct_revenue(all_series, pk: PeriodKey) -> float | None:
    return _safe_div(_get(all_series, "Net Cash from Operating Activities", pk), _get(all_series, "Revenue", pk))


def _fcf_pct_revenue(all_series, pk: PeriodKey) -> float | None:
    ocf = _get(all_series, "Net Cash from Operating Activities", pk)
    capex = _get(all_series, "Capital Expenditures", pk)
    rev = _get(all_series, "Revenue", pk)
    if ocf is None or capex is None or rev in (None, 0):
        return None
    return (ocf - abs(capex)) / rev


# ---------------------------------------------------------------------------
# CASH DEPLOYMENT
# ---------------------------------------------------------------------------

def _capex(all_series, pk: PeriodKey) -> float | None:
    v = _get(all_series, "Capital Expenditures", pk)
    return -abs(v) if v is not None else None


def _dividends(all_series, pk: PeriodKey) -> float | None:
    v = _get(all_series, "Dividends Paid", pk)
    return -abs(v) if v is not None else None


def _buybacks(all_series, pk: PeriodKey) -> float | None:
    v = _get(all_series, "Share Repurchases", pk)
    return -abs(v) if v is not None else None


DASHBOARD_METRICS: tuple[DashboardMetric, ...] = (
    # Sales Analysis
    DashboardMetric("Revenue Δ, y/y", "Sales Analysis", _revenue_yoy, is_percent=True),
    # Income Statement Analysis
    DashboardMetric("Operating margin", "Income Statement Analysis", _operating_margin, is_percent=True),
    DashboardMetric("Net margin", "Income Statement Analysis", _net_margin, is_percent=True),
    DashboardMetric("SG&A / revenue", "Income Statement Analysis", _sga_pct_revenue, is_percent=True),
    # Earnings Quality
    DashboardMetric("Adj. EPS Δ, y/y", "Earnings Quality", _adj_eps_yoy, is_percent=True),
    DashboardMetric("FCF / % Net Income", "Earnings Quality", _fcf_pct_net_income, is_percent=True),
    # Financial Strength
    DashboardMetric("Current ratio", "Financial Strength", _current_ratio),
    DashboardMetric("Net debt / total assets", "Financial Strength", _net_debt_to_assets, is_percent=True),
    # Cash Generation
    DashboardMetric("OCF / revenue", "Cash Generation", _ocf_pct_revenue, is_percent=True),
    DashboardMetric("FCF / revenue", "Cash Generation", _fcf_pct_revenue, is_percent=True),
    # Cash Deployment
    DashboardMetric("Capital expenditures", "Cash Deployment", _capex),
    DashboardMetric("Dividends paid", "Cash Deployment", _dividends),
    DashboardMetric("Share repurchases", "Cash Deployment", _buybacks),
)

DASHBOARD_SECTIONS: tuple[str, ...] = (
    "Sales Analysis",
    "Income Statement Analysis",
    "Earnings Quality",
    "Financial Strength",
    "Cash Generation",
    "Cash Deployment",
)
