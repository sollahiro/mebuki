"""
XBRL 抽出結果の TypedDict 定義
"""

from typing import NotRequired, TypedDict

XbrlTagElements = dict[str, dict[str, float]]


class MetricComponent(TypedDict):
    label: str
    tag: str | None
    current: float | None
    prior: float | None


class GrossProfitResult(TypedDict):
    current: float | None
    prior: float | None
    method: str
    accounting_standard: str
    components: list[MetricComponent]
    docID: NotRequired[str]
    reason: NotRequired[str]
    current_sales: NotRequired[float | None]
    prior_sales: NotRequired[float | None]


class OperatingProfitResult(TypedDict):
    current: float | None
    prior: float | None
    method: str
    label: str
    accounting_standard: str
    reason: NotRequired[str]


class InterestBearingDebtResult(TypedDict):
    current: float | None
    prior: float | None
    method: str
    accounting_standard: str
    components: list[MetricComponent]
    reason: NotRequired[str]


class BalanceSheetResult(TypedDict):
    current_assets: float | None
    non_current_assets: float | None
    current_liabilities: float | None
    non_current_liabilities: float | None
    net_assets: float | None
    accounting_standard: str
    method: str
    components: list[MetricComponent]
    reason: NotRequired[str]


class InterestExpenseResult(TypedDict):
    current: float | None
    prior: float | None
    method: str
    accounting_standard: str
    reason: NotRequired[str]


class TaxExpenseResult(TypedDict):
    pretax_income: float | None
    income_tax: float | None
    effective_tax_rate: float | None
    prior_pretax_income: float | None
    prior_income_tax: float | None
    prior_effective_tax_rate: float | None
    accounting_standard: str
    method: str
    reason: NotRequired[str]


class EmployeesResult(TypedDict):
    current: float | None
    prior: float | None
    method: str
    scope: str


class NetRevenueResult(TypedDict):
    net_revenue: float | None
    net_revenue_prior: float | None
    business_profit: float | None
    business_profit_prior: float | None
    found: bool


class CashFlowPeriod(TypedDict):
    current: float | None
    prior: float | None


class CashFlowResult(TypedDict):
    cfo: CashFlowPeriod
    cfi: CashFlowPeriod
    accounting_standard: str


class DepreciationResult(TypedDict):
    current: float | None
    prior: float | None
    accounting_standard: str
    method: str
    reason: NotRequired[str]


class OrderBookResult(TypedDict):
    order_intake: float | None
    order_backlog: float | None
    order_intake_prior: float | None
    order_backlog_prior: float | None
    method: str
    docID: NotRequired[str]
    reason: NotRequired[str]


class HalfYearEdinetEntry(TypedDict):
    gp: GrossProfitResult
    cf: CashFlowResult
    ibd: InterestBearingDebtResult
