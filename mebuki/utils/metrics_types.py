"""
財務指標 TypedDict 定義

calculator.py が組み立て、analyzer.py の _apply_* が段階的に拡充する
データ構造を型で表現する。
"""

from typing import TypedDict


class IBDComponent(TypedDict, total=False):
    label: str
    current: float | None
    prior: float | None


class MetricSource(TypedDict, total=False):
    source: str
    method: str
    docID: str | None
    unit: str
    label: str
    rf: float
    rf_source: str


class RawData(TypedDict, total=False):
    CurPerType: str
    CurFYSt: str
    CurFYEn: str | None
    DiscDate: str
    Sales: float | None
    OP: float | None
    NP: float | None
    Eq: float | None
    CFO: float | None
    CFI: float | None
    EPS: float | None
    BPS: float | None
    AvgSh: float | None
    DivTotalAnn: float | None
    PayoutRatioAnn: float | None
    CashEq: float | None
    DivAnn: float | None
    NxFDivAnn: float | None


class CalculatedData(TypedDict, total=False):
    # ── source metadata ──
    MetricSources: dict[str, MetricSource]
    # ── calculator.py: _calculate_base_values ──
    Sales: float | None
    OP: float | None
    NP: float | None
    Eq: float | None
    CFO: float | None
    CFI: float | None
    CashEq: float | None
    PayoutRatio: float | None
    CFC: float | None
    # ── calculator.py: _calculate_profitability_metrics ──
    ROE: float | None
    CFCVR: float | None
    # ── calculator.py: 株式分割調整 ──
    AdjustmentRatio: float | None
    AdjustedEPS: float | None
    AdjustedBPS: float | None
    # ── analyzer.py: _apply_gross_profit ──
    GrossProfit: float | None
    GrossProfitMargin: float | None
    GrossProfitMethod: str
    # ── analyzer.py: _apply_ibd ──
    InterestBearingDebt: float | None
    IBDComponents: list[IBDComponent]
    IBDAccountingStandard: str
    ROIC: float | None
    # ── analyzer.py: _apply_interest_expense ──
    InterestExpense: float | None
    # ── analyzer.py: _apply_tax ──
    PretaxIncome: float | None
    IncomeTax: float | None
    EffectiveTaxRate: float | None
    # ── analyzer.py: _apply_operating_profit / _apply_net_revenue ──
    OperatingMargin: float | None
    OPLabel: str
    SalesLabel: str
    # ── analyzer.py: _apply_employees ──
    Employees: int | None
    # ── analyzer.py: _apply_depreciation ──
    DepreciationAmortization: float | None
    # ── analyzer.py: _apply_ibd / half_year_data_service.py ──
    DocID: str | None
    # ── wacc.py: calculate_wacc ──
    CostOfEquity: float | None
    CostOfDebt: float | None
    WACC: float | None
    WACCLabel: str | None


class YearEntry(TypedDict):
    fy_end: str | None
    FinancialPeriod: str
    RawData: RawData
    CalculatedData: CalculatedData


class MetricsResult(TypedDict, total=False):
    code: str | None
    latest_fy_end: str | None
    analysis_years: int
    available_years: int
    years: list[YearEntry]
    latest_fcf: float | None
    latest_roe: float | None
    latest_eps: float | None
    latest_sales: float | None
    data_availability: str
    data_availability_message: str
    data_valid: bool
    validation_message: str | None
