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
    LineItem("Inventory, Net", ("InventoryNet",), "balance_sheet"),
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
