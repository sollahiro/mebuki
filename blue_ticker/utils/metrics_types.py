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


class BalanceSheetComponent(TypedDict, total=False):
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
    SalesLabel: str | None
    Sales: float | None
    OP: float | None
    NP: float | None
    NetAssets: float | None
    CFO: float | None
    CFI: float | None
    EPS: float | None
    BPS: float | None
    ShOutFY: float | None
    DivTotalAnn: float | None
    PayoutRatioAnn: float | None
    CashEq: float | None
    Div2Q: float | None
    DivAnn: float | None
    _xbrl_source: bool


class CalculatedData(TypedDict, total=False):
    # ── source metadata ──
    MetricSources: dict[str, MetricSource]
    # ── calculator.py: _calculate_base_values ──
    PayoutRatio: float | None
    CFC: float | None
    # ── calculator.py: _calculate_profitability_metrics ──
    ROE: float | None
    CFCVR: float | None
    # ── analyzer.py: _apply_gross_profit ──
    GrossProfit: float | None
    GrossProfitMargin: float | None
    GrossProfitMethod: str
    GrossProfitLabel: str
    # ── analyzer.py: _apply_ibd ──
    InterestBearingDebt: float | None
    IBDComponents: list[IBDComponent]
    IBDAccountingStandard: str
    ROIC: float | None
    # ── analyzer.py: _apply_balance_sheet ──
    TotalAssets: float | None
    CurrentAssets: float | None
    NonCurrentAssets: float | None
    CurrentLiabilities: float | None
    NonCurrentLiabilities: float | None
    NetAssets: float | None
    BalanceSheetComponents: list[BalanceSheetComponent]
    BalanceSheetAccountingStandard: str
    # ── analyzer.py: _apply_interest_expense ──
    InterestExpense: float | None
    # ── analyzer.py: _apply_tax ──
    PretaxIncome: float | None
    IncomeTax: float | None
    EffectiveTaxRate: float | None
    # ── analyzer.py: _apply_operating_profit / _apply_net_revenue ──
    OperatingMargin: float | None
    OPLabel: str
    # ── operating_profit_change.py: 営業利益前年差分解 ──
    SellingGeneralAdministrativeExpenses: float | None
    OperatingProfitChange: float | None
    SalesChangeImpact: float | None
    GrossMarginChangeImpact: float | None
    SGAChangeImpact: float | None
    OperatingProfitChangeReconciliationDiff: float | None
    # ── analyzer.py: _apply_employees ──
    Employees: int | None
    # ── analyzer.py: _apply_depreciation ──
    DepreciationAmortization: float | None
    # ── analyzer.py: _apply_order_book ──
    OrderIntake: float | None
    OrderBacklog: float | None
    # ── analyzer.py: _apply_ibd / half_year_data_service.py ──
    DocID: str | None
    AmendmentDocID: str | None
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


class RawXbrlExtraction(TypedDict, total=False):
    """XBRLから直接抽出した年度別の生値。金額は円単位で保持する。"""

    doc_id: str
    amendment_doc_id: str
    gross_profit: float | None
    gross_profit_method: str
    gross_profit_label: str | None
    operating_profit: float | None
    operating_profit_method: str
    operating_profit_label: str
    selling_general_administrative_expenses: float | None
    selling_general_administrative_expenses_method: str
    sales: float | None
    sales_label: str | None
    net_revenue: float | None
    business_profit: float | None
    interest_bearing_debt: float | None
    ibd_components: list[IBDComponent]
    ibd_method: str
    ibd_accounting_standard: str
    total_assets: float | None
    current_assets: float | None
    non_current_assets: float | None
    current_liabilities: float | None
    non_current_liabilities: float | None
    net_assets: float | None
    balance_sheet_components: list[BalanceSheetComponent]
    balance_sheet_method: str
    balance_sheet_accounting_standard: str
    interest_expense: float | None
    interest_expense_method: str
    pretax_income: float | None
    income_tax: float | None
    effective_tax_rate: float | None
    tax_method: str
    employees: int | None
    employees_method: str
    employees_scope: str
    depreciation_amortization: float | None
    depreciation_method: str
    order_intake: float | None
    order_backlog: float | None
    order_book_method: str


class MetricsResult(TypedDict, total=False):
    code: str | None
    latest_fy_end: str | None
    analysis_years: int
    available_years: int
    years: list[YearEntry]
    data_availability: str
    data_availability_message: str
    data_valid: bool
    validation_message: str | None
