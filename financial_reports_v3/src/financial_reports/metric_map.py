"""Curated map of standard, whole-company financial-statement line items.

Each entry maps a broker-report line item to one or more us-gaap XBRL tags,
in priority order (first tag found wins for a given period). These are all
consolidated, entity-wide concepts as reported on the face of the Income
Statement, Balance Sheet, and Cash Flow Statement -- i.e. exactly what shows
up in the standard 10-K/10-Q filings. Segment/business-unit breakdowns use
separate dimensional XBRL members (an "Axis"/"Member" pair) and are not
referenced anywhere in this map, so they never enter the output.

Tags are deliberately generic (not FedEx-specific) so this map works for any
filer; a given company will simply not populate rows for tags it doesn't use.

In addition to filed-tag lookups, COMPUTED_LINE_ITEMS defines a small set of
line items that are *purely arithmetic* identities of other rows in the same
statement (e.g. Net Change in Cash = OCF + Investing CF + Financing CF + FX
effect). These are only used to fill a gap when the filer's own total tag is
missing -- a filed value always wins over a computed one -- and only when
every required input for that specific period is itself present. No
estimation, interpolation, or judgment-based derivation is performed here.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class LineItem:
    label: str
    tags: tuple[str, ...]
    statement: str  # "income_statement" | "balance_sheet" | "cash_flow"
    is_subtotal: bool = False
    indent: int = 0


@dataclass(frozen=True)
class ComputedLineItem:
    """A line item whose value is an arithmetic identity of other line
    items' labels, used only to backfill a period where the filer's own
    tag for that concept is missing. `terms` is a tuple of
    (line_item_label, sign, required) triples, e.g.
    (("Total Assets", 1, True), ("Total Stockholders' Equity", -1, True))
    for Total Liabilities.

    `required=True` terms must have an explicit value for the period or the
    whole computation is skipped (left blank) -- these are core line items
    essentially every filer reports every period (e.g. Net Income, Total
    Assets, Capital Expenditures). `required=False` terms are treated as 0
    when absent for that period -- these are episodic items that simply
    don't get filed as a separate XBRL fact in a quarter where nothing
    happened (e.g. Proceeds from Debt Issuance, Acquisitions). This
    distinction is deliberate: treating an absent *required* term as zero
    would silently misstate a real gap as "nothing happened" when it may
    just be unreported; treating an absent *optional* term as zero reflects
    how these items are actually filed in practice.
    """
    label: str
    terms: tuple[tuple[str, int, bool], ...]


INCOME_STATEMENT: tuple[LineItem, ...] = (
    LineItem("Revenue", ("Revenues", "RevenueFromContractWithCustomerExcludingAssessedTax",
                          "RevenueFromContractWithCustomerIncludingAssessedTax",
                          "SalesRevenueNet"), "income_statement"),
    LineItem("Cost of Revenue / Operating Expenses", ("CostsAndExpenses", "CostOfRevenue",
                                                        "CostOfGoodsAndServicesSold"), "income_statement"),
    LineItem("  Salaries, Wages & Benefits", ("SalariesWagesAndOfficersCompensation",
                                               "LaborAndRelatedExpense"), "income_statement", False, 1),
    LineItem("  Purchased Transportation", ("CostOfServices",), "income_statement", False, 1),
    LineItem("  Depreciation & Amortization", ("DepreciationDepletionAndAmortization",
                                                "DepreciationAmortizationAndAccretionNet",
                                                "Depreciation"), "income_statement", False, 1),
    LineItem("  Fuel", ("FuelCosts",), "income_statement", False, 1),
    LineItem("  Maintenance & Repairs", ("MaintenanceCosts", "RepairsAndMaintenanceCosts"),
             "income_statement", False, 1),
    LineItem("  Selling, General & Administrative", ("SellingGeneralAndAdministrativeExpense",
                                                       "GeneralAndAdministrativeExpense",
                                                       "SellingAndMarketingExpense"), "income_statement", False, 1),
    LineItem("  Other Operating Expense", ("OtherCostAndExpenseOperating",), "income_statement", False, 1),
    LineItem("Operating Income", ("OperatingIncomeLoss",), "income_statement", True),
    LineItem("Interest Expense", ("InterestExpense", "InterestExpenseDebt", "InterestIncomeExpenseNet"),
             "income_statement"),
    LineItem("Interest Income", ("InvestmentIncomeInterest",), "income_statement"),
    LineItem("Other Non-Operating Income (Expense)", ("OtherNonoperatingIncomeExpense",
                                                        "NonoperatingIncomeExpense"), "income_statement"),
    LineItem("Pretax Income",
             ("IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest",
              "IncomeLossFromContinuingOperationsBeforeIncomeTaxesMinorityInterestAndIncomeLossFromEquityMethodInvestments"),
             "income_statement", True),
    LineItem("Income Tax Expense (Benefit)", ("IncomeTaxExpenseBenefit",), "income_statement"),
    LineItem("Equity Method Investment Income", ("IncomeLossFromEquityMethodInvestments",),
             "income_statement"),
    LineItem("Net Income from Continuing Operations", ("IncomeLossFromContinuingOperations",),
             "income_statement", True),
    LineItem("Income from Discontinued Operations", ("IncomeLossFromDiscontinuedOperationsNetOfTax",),
             "income_statement"),
    LineItem("Net Income Attributable to Noncontrolling Interest",
             ("NetIncomeLossAttributableToNoncontrollingInterest",), "income_statement"),
    LineItem("Net Income", ("NetIncomeLoss", "ProfitLoss"), "income_statement", True),
    LineItem("EPS - Basic", ("EarningsPerShareBasic",), "income_statement"),
    LineItem("EPS - Diluted", ("EarningsPerShareDiluted",), "income_statement"),
    LineItem("Weighted Avg Shares - Basic", ("WeightedAverageNumberOfSharesOutstandingBasic",),
             "income_statement"),
    LineItem("Weighted Avg Shares - Diluted", ("WeightedAverageNumberOfDilutedSharesOutstanding",),
             "income_statement"),
)

BALANCE_SHEET: tuple[LineItem, ...] = (
    LineItem("Cash & Cash Equivalents", ("CashAndCashEquivalentsAtCarryingValue",
                                          "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents"),
             "balance_sheet"),
    LineItem("Short-Term Investments", ("ShortTermInvestments",), "balance_sheet"),
    LineItem("Accounts Receivable, Net", ("AccountsReceivableNetCurrent", "ReceivablesNetCurrent"),
             "balance_sheet"),
    # NOTE: FedEx does not report a standard "Inventory" line -- it reports
    # "Spare parts, supplies and fuel, less allowances" instead, which is
    # likely tagged with a company-specific (non us-gaap) XBRL element.
    # SparePartsSuppliesAndFuelNet/OtherInventorySupplies below are
    # best-guess fallback tag names, NOT verified against a live EDGAR
    # companyfacts response (this pipeline's test environment can't reach
    # data.sec.gov). Run scripts/run_pipeline.py and check the "WARNING:
    # zero matching facts" output for this line item; if it still comes up
    # empty, inspect the real companyfacts JSON for FedEx's actual tag name
    # and add it here.
    LineItem("Inventory, Net / Spare Parts, Supplies & Fuel",
             ("InventoryNet", "SparePartsSuppliesAndFuelNet", "OtherInventorySupplies"),
             "balance_sheet"),
    LineItem("Prepaid Expenses & Other Current Assets", ("PrepaidExpenseAndOtherAssetsCurrent",
                                                           "OtherAssetsCurrent"), "balance_sheet"),
    LineItem("Total Current Assets", ("AssetsCurrent",), "balance_sheet", True),
    LineItem("Property, Plant & Equipment, Net", ("PropertyPlantAndEquipmentNet",), "balance_sheet"),
    LineItem("Operating Lease Right-of-Use Assets", ("OperatingLeaseRightOfUseAsset",), "balance_sheet"),
    LineItem("Goodwill", ("Goodwill",), "balance_sheet"),
    LineItem("Intangible Assets, Net", ("IntangibleAssetsNetExcludingGoodwill", "FiniteLivedIntangibleAssetsNet"),
             "balance_sheet"),
    LineItem("Deferred Income Tax Assets", ("DeferredIncomeTaxAssetsNet",), "balance_sheet"),
    LineItem("Other Long-Term Assets", ("OtherAssetsNoncurrent",), "balance_sheet"),
    LineItem("Total Assets", ("Assets",), "balance_sheet", True),
    LineItem("Current Portion of Long-Term Debt", ("LongTermDebtCurrent", "DebtCurrent"), "balance_sheet"),
    LineItem("Accounts Payable", ("AccountsPayableCurrent", "AccountsPayableAndAccruedLiabilitiesCurrent"),
             "balance_sheet"),
    LineItem("Accrued Salaries & Employee Benefits", ("EmployeeRelatedLiabilitiesCurrent",), "balance_sheet"),
    LineItem("Current Operating Lease Liabilities", ("OperatingLeaseLiabilityCurrent",), "balance_sheet"),
    LineItem("Other Current Liabilities", ("OtherLiabilitiesCurrent",), "balance_sheet"),
    LineItem("Total Current Liabilities", ("LiabilitiesCurrent",), "balance_sheet", True),
    LineItem("Long-Term Debt, Net", ("LongTermDebtNoncurrent",), "balance_sheet"),
    LineItem("Noncurrent Operating Lease Liabilities", ("OperatingLeaseLiabilityNoncurrent",), "balance_sheet"),
    LineItem("Pension & Postretirement Liabilities", ("DefinedBenefitPensionPlanLiabilitiesNoncurrent",
                                                        "PensionAndOtherPostretirementDefinedBenefitPlansLiabilitiesNoncurrent"),
             "balance_sheet"),
    LineItem("Deferred Income Tax Liabilities", ("DeferredIncomeTaxLiabilitiesNet",), "balance_sheet"),
    LineItem("Other Long-Term Liabilities", ("OtherLiabilitiesNoncurrent",), "balance_sheet"),
    LineItem("Total Liabilities", ("Liabilities",), "balance_sheet", True),
    LineItem("Common Stock", ("CommonStockValue",), "balance_sheet"),
    LineItem("Additional Paid-In Capital", ("AdditionalPaidInCapital", "AdditionalPaidInCapitalCommonStock"),
             "balance_sheet"),
    LineItem("Retained Earnings", ("RetainedEarningsAccumulatedDeficit",), "balance_sheet"),
    LineItem("Treasury Stock", ("TreasuryStockValue", "TreasuryStockCommonValue"), "balance_sheet"),
    LineItem("Accumulated Other Comprehensive Income (Loss)",
             ("AccumulatedOtherComprehensiveIncomeLossNetOfTax",), "balance_sheet"),
    LineItem("Noncontrolling Interest", ("MinorityInterest",), "balance_sheet"),
    LineItem("Total Stockholders' Equity",
             ("StockholdersEquity", "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest"),
             "balance_sheet", True),
    LineItem("Total Liabilities & Stockholders' Equity", ("LiabilitiesAndStockholdersEquity",),
             "balance_sheet", True),
)

CASH_FLOW: tuple[LineItem, ...] = (
    LineItem("Net Income", ("NetIncomeLoss", "ProfitLoss"), "cash_flow"),
    LineItem("Depreciation & Amortization", ("DepreciationDepletionAndAmortization",
                                              "DepreciationAmortizationAndAccretionNet",
                                              "Depreciation"), "cash_flow"),
    LineItem("Stock-Based Compensation", ("ShareBasedCompensation",), "cash_flow"),
    LineItem("Deferred Income Taxes", ("DeferredIncomeTaxExpenseBenefit",), "cash_flow"),
    LineItem("Asset Impairment Charges", ("AssetImpairmentCharges",), "cash_flow"),
    LineItem("(Gain) Loss on Sale of Assets", ("GainLossOnDispositionOfAssets1",
                                                "GainLossOnSaleOfPropertyPlantEquipment"), "cash_flow"),
    LineItem("Change in Receivables", ("IncreaseDecreaseInAccountsReceivable",), "cash_flow"),
    LineItem("Change in Inventory", ("IncreaseDecreaseInInventories",), "cash_flow"),
    LineItem("Change in Accounts Payable", ("IncreaseDecreaseInAccountsPayable",), "cash_flow"),
    LineItem("Change in Accrued/Other Liabilities", ("IncreaseDecreaseInAccruedLiabilities",
                                                       "IncreaseDecreaseInOtherOperatingCapitalNet"), "cash_flow"),
    LineItem("Other Operating Activities", ("OtherOperatingActivitiesCashFlowStatement",), "cash_flow"),
    LineItem("Net Cash from Operating Activities",
             ("NetCashProvidedByUsedInOperatingActivities",
              "NetCashProvidedByUsedInOperatingActivitiesContinuingOperations"), "cash_flow", True),
    LineItem("Capital Expenditures", ("PaymentsToAcquirePropertyPlantAndEquipment",), "cash_flow"),
    LineItem("Proceeds from Asset Sales", ("ProceedsFromSaleOfPropertyPlantAndEquipment",), "cash_flow"),
    LineItem("Acquisitions, Net of Cash Acquired", ("PaymentsToAcquireBusinessesNetOfCashAcquired",), "cash_flow"),
    LineItem("Purchases of Investments", ("PaymentsToAcquireInvestments",), "cash_flow"),
    LineItem("Sales/Maturities of Investments",
             ("ProceedsFromSaleMaturityAndCollectionsOfInvestments",), "cash_flow"),
    LineItem("Other Investing Activities", ("PaymentsForProceedsFromOtherInvestingActivities",), "cash_flow"),
    LineItem("Net Cash from Investing Activities",
             ("NetCashProvidedByUsedInInvestingActivities",
              "NetCashProvidedByUsedInInvestingActivitiesContinuingOperations"), "cash_flow", True),
    LineItem("Proceeds from Debt Issuance", ("ProceedsFromIssuanceOfLongTermDebt",), "cash_flow"),
    LineItem("Repayments of Debt", ("RepaymentsOfLongTermDebt",), "cash_flow"),
    LineItem("Dividends Paid", ("PaymentsOfDividends", "PaymentsOfDividendsCommonStock"), "cash_flow"),
    LineItem("Share Repurchases", ("PaymentsForRepurchaseOfCommonStock",), "cash_flow"),
    LineItem("Proceeds from Stock Issuance", ("ProceedsFromIssuanceOfCommonStock",), "cash_flow"),
    LineItem("Other Financing Activities", ("ProceedsFromPaymentsForOtherFinancingActivities",), "cash_flow"),
    LineItem("Net Cash from Financing Activities",
             ("NetCashProvidedByUsedInFinancingActivities",
              "NetCashProvidedByUsedInFinancingActivitiesContinuingOperations"), "cash_flow", True),
    LineItem("Effect of Exchange Rate on Cash",
             ("EffectOfExchangeRateOnCashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents",
              "EffectOfExchangeRateOnCashAndCashEquivalents"), "cash_flow"),
    LineItem("Net Change in Cash",
             ("CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalentsPeriodIncreaseDecreaseIncludingExchangeRateEffect",
              "CashAndCashEquivalentsPeriodIncreaseDecrease"), "cash_flow", True),
)

ALL_LINE_ITEMS: tuple[LineItem, ...] = INCOME_STATEMENT + BALANCE_SHEET + CASH_FLOW

# Statement key whose facts are point-in-time balances (matched by period END
# date only) rather than period flows (matched by START+END date span).
INSTANT_STATEMENT = "balance_sheet"

# Purely arithmetic identities used to backfill a period only when the
# filer's own tag for that exact concept is missing AND every REQUIRED
# input is present for that period (OPTIONAL inputs default to 0 if absent
# -- see ComputedLineItem docstring for the required-vs-optional rationale).
# A filed value always takes priority over a computed one. Each is a
# textbook accounting identity, not an estimate -- e.g. the balance sheet
# must always balance (Assets = Liabilities + Equity), and total cash flow
# components must sum to the change in cash.
REQ, OPT = True, False  # readability aliases for the `required` flag below

COMPUTED_LINE_ITEMS: tuple[ComputedLineItem, ...] = (
    # --- Income Statement ---
    # Revenue and the aggregate expense line are both core, always-filed
    # figures -- if either is missing, don't guess at Operating Income.
    ComputedLineItem("Operating Income", (
        ("Revenue", 1, REQ), ("Cost of Revenue / Operating Expenses", -1, REQ),
    )),
    # Interest income/expense and other non-operating items are routinely
    # zero/unreported for companies with simple capital structures -- but
    # Operating Income itself is core.
    ComputedLineItem("Pretax Income", (
        ("Operating Income", 1, REQ), ("Interest Income", 1, OPT), ("Interest Expense", -1, OPT),
        ("Other Non-Operating Income (Expense)", 1, OPT),
    )),
    # Equity method investment income is genuinely episodic (most companies
    # don't have equity-method investees); tax expense is core.
    ComputedLineItem("Net Income from Continuing Operations", (
        ("Pretax Income", 1, REQ), ("Income Tax Expense (Benefit)", -1, REQ),
        ("Equity Method Investment Income", 1, OPT),
    )),
    # Discontinued operations and NCI are episodic/zero for most companies
    # most periods.
    ComputedLineItem("Net Income", (
        ("Net Income from Continuing Operations", 1, REQ),
        ("Income from Discontinued Operations", 1, OPT),
        ("Net Income Attributable to Noncontrolling Interest", -1, OPT),
    )),
    # --- Balance Sheet: the fundamental accounting identity, both
    # directions. Both Total Assets and the other side of the identity are
    # core, always-filed totals -- required on both terms.
    ComputedLineItem("Total Liabilities", (
        ("Total Assets", 1, REQ), ("Total Stockholders' Equity", -1, REQ),
    )),
    ComputedLineItem("Total Stockholders' Equity", (
        ("Total Assets", 1, REQ), ("Total Liabilities", -1, REQ),
    )),
    ComputedLineItem("Total Liabilities & Stockholders' Equity", (
        ("Total Assets", 1, REQ),
    )),
    # Cash and receivables are core current-asset lines for nearly every
    # filer; short-term investments, inventory(-equivalent), and prepaids
    # are common but not universal -- optional.
    ComputedLineItem("Total Current Assets", (
        ("Cash & Cash Equivalents", 1, REQ), ("Short-Term Investments", 1, OPT),
        ("Accounts Receivable, Net", 1, REQ),
        ("Inventory, Net / Spare Parts, Supplies & Fuel", 1, OPT),
        ("Prepaid Expenses & Other Current Assets", 1, OPT),
    )),
    # Accounts payable is a core current-liability line; the rest are
    # common but filer-dependent (lease liabilities only apply to filers
    # with operating leases, current debt only if any is due within a
    # year, etc.) -- optional.
    ComputedLineItem("Total Current Liabilities", (
        ("Current Portion of Long-Term Debt", 1, OPT), ("Accounts Payable", 1, REQ),
        ("Accrued Salaries & Employee Benefits", 1, OPT),
        ("Current Operating Lease Liabilities", 1, OPT), ("Other Current Liabilities", 1, OPT),
    )),
    # --- Cash Flow Statement ---
    # Capex is reported by virtually every operating company every period;
    # the rest (asset sales, M&A, investment purchases/sales) are episodic.
    ComputedLineItem("Net Cash from Investing Activities", (
        ("Capital Expenditures", -1, REQ), ("Proceeds from Asset Sales", 1, OPT),
        ("Acquisitions, Net of Cash Acquired", -1, OPT), ("Purchases of Investments", -1, OPT),
        ("Sales/Maturities of Investments", 1, OPT), ("Other Investing Activities", 1, OPT),
    )),
    # Debt issuance/repayment, dividends, and buybacks are all genuinely
    # episodic at the individual-quarter level (a company may pay no
    # dividend, raise no debt, and buy back no stock in a given quarter) --
    # none of these are reliably present every period, so all are optional.
    # This means the fallback only fires when there's at least one filed
    # financing-activity sub-item for the period; if a filer reports zero
    # financing activity sub-items at all for a period, this stays blank
    # rather than asserting $0 financing activity.
    ComputedLineItem("Net Cash from Financing Activities", (
        ("Proceeds from Debt Issuance", 1, OPT), ("Repayments of Debt", -1, OPT),
        ("Dividends Paid", -1, OPT), ("Share Repurchases", -1, OPT),
        ("Proceeds from Stock Issuance", 1, OPT), ("Other Financing Activities", 1, OPT),
    )),
    # Operating cash flow is core; FX effect is genuinely optional (only
    # applies to filers with material foreign operations).
    ComputedLineItem("Net Change in Cash", (
        ("Net Cash from Operating Activities", 1, REQ),
        ("Net Cash from Investing Activities", 1, REQ),
        ("Net Cash from Financing Activities", 1, REQ),
        ("Effect of Exchange Rate on Cash", 1, OPT),
    )),
)
