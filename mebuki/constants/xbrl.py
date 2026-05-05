from typing import NotRequired, TypedDict


class _XBRLSection(TypedDict):
    title: str
    xbrl_elements: list[str]


class _ComponentDef(TypedDict):
    label: str
    tags: list[str]


class _AggregateIFRSDef(TypedDict):
    tag: str
    covers: list[str]
    label: NotRequired[str]


class _BalanceSheetComponentDef(TypedDict):
    field: str
    label: str
    tags: list[str]


class _BalanceSheetAggregateDef(TypedDict):
    field: str
    label: str
    tags: list[str]


class _BalanceSheetSubtractDef(TypedDict):
    field: str
    label: str
    minuend_tags: list[str]
    subtrahend_tags: list[str]


# Duration（損益計算書・CF）コンテキストパターン
# 年次: CurrentYearDuration / 新形式半期: InterimDuration / 旧形式半期・四半期: CurrentYTDDuration
DURATION_CONTEXT_PATTERNS: list[str] = [
    "CurrentYearDuration",
    "FilingDateDuration",
    "InterimDuration",
    "CurrentYTDDuration",
]

PRIOR_DURATION_CONTEXT_PATTERNS: list[str] = [
    "Prior1YearDuration",
    "PriorYearDuration",
    "Prior1InterimDuration",
    "Prior1YTDDuration",
]

# Instant（貸借対照表）コンテキストパターン
# 四半期・半期報告書にも対応
INSTANT_CONTEXT_PATTERNS: list[str] = [
    "CurrentYearInstant",
    "CurrentQuarterInstant",
    "InterimInstant",
    "FilingDateInstant",
]

PRIOR_INSTANT_CONTEXT_PATTERNS: list[str] = [
    "Prior1YearInstant",
    "PriorYearInstant",
    "Prior1QuarterInstant",
    "Prior1InterimInstant",
]

XBRL_SECTIONS: dict[str, _XBRLSection] = {
    'business_risks': {
        'title': '事業等のリスク',
        'xbrl_elements': ['BusinessRisksTextBlock']
    },
    'mda': {
        'title': '経営者による財政状態、経営成績及びキャッシュ・フローの状況の分析',
        'xbrl_elements': ['ManagementAnalysisOfFinancialPositionOperatingResultsAndCashFlowsTextBlock']
    },
    'capex_overview': {
        'title': '設備投資等の概要',
        'xbrl_elements': ['OverviewOfCapitalExpendituresEtcOwnUsedAssetsLEATextBlock']
    },
    'major_facilities': {
        'title': '主要な設備の状況',
        'xbrl_elements': ['MajorFacilitiesTextBlock']
    },
    'facility_plans': {
        'title': '設備の新設、除却等の計画',
        'xbrl_elements': ['PlannedAdditionsRetirementsEtcOfFacilitiesTextBlock']
    }
}

# 貸借対照表（BS）タグ定義
# analysis/balance_sheet.py で使用

BALANCE_SHEET_COMPONENT_DEFINITIONS: list[_BalanceSheetComponentDef] = [
    {
        "field": "CurrentAssets",
        "label": "流動資産",
        "tags": [
            "CurrentAssets",        # J-GAAP
            "CurrentAssetsIFRS",    # IFRS
            "CurrentAssetsUSGAAP",  # US-GAAP
        ],
    },
    {
        "field": "NonCurrentAssets",
        "label": "固定資産",
        "tags": [
            "NoncurrentAssets",        # J-GAAP
            "NonCurrentAssets",        # 代替表記
            "NonCurrentAssetsIFRS",    # IFRS
            "NonCurrentAssetsUSGAAP",  # US-GAAP
        ],
    },
    {
        "field": "CurrentLiabilities",
        "label": "流動負債",
        "tags": [
            "CurrentLiabilities",        # J-GAAP
            "TotalCurrentLiabilitiesIFRS", # IFRS
            "CurrentLiabilitiesIFRS",    # IFRS
            "CurrentLiabilitiesUSGAAP",  # US-GAAP
        ],
    },
    {
        "field": "NonCurrentLiabilities",
        "label": "固定負債",
        "tags": [
            "NoncurrentLiabilities",        # J-GAAP
            "NonCurrentLiabilities",        # 代替表記
            "NonCurrentLiabilitiesIFRS",    # IFRS
            "LongTermLiabilitiesUSGAAP",    # US-GAAP
            "NonCurrentLiabilitiesUSGAAP",  # US-GAAP 代替
        ],
    },
    {
        "field": "NetAssets",
        "label": "純資産",
        "tags": [
            "NetAssets",                                              # J-GAAP
            "EquityIFRS",                                             # IFRS
            "TotalEquityIFRS",                                        # IFRS 代替
            "EquityAttributableToOwnersOfParentIFRS",                 # IFRS 親会社所有者帰属持分
            "NetAssetsUSGAAP",                                        # US-GAAP
            "TotalEquityUSGAAP",                                      # US-GAAP 代替
            "EquityAttributableToOwnersOfParentUSGAAP",               # US-GAAP 親会社所有者帰属持分
            "EquityAttributableToOwnersOfParentUSGAAPSummaryOfBusinessResults",
        ],
    },
]

BALANCE_SHEET_AGGREGATE_DEFINITIONS: list[_BalanceSheetAggregateDef] = [
    {
        "field": "NonCurrentAssets",
        "label": "投資及び長期債権合計＋有形固定資産合計＋その他の資産合計",
        "tags": [
            "InvestmentsAndLongTermReceivablesUSGAAP",
            "PropertyPlantAndEquipmentNetUSGAAP",
            "PropertyPlantAndEquipmentUSGAAP",
            "OtherAssetsUSGAAP",
        ],
    },
]

BALANCE_SHEET_SUBTRACT_DEFINITIONS: list[_BalanceSheetSubtractDef] = [
    {
        "field": "NonCurrentLiabilities",
        "label": "負債合計−流動負債",
        "minuend_tags": [
            "LiabilitiesIFRS",
            "TotalLiabilitiesUSGAAP",
            "Liabilities",
        ],
        "subtrahend_tags": [
            "TotalCurrentLiabilitiesIFRS",
            "CurrentLiabilitiesIFRS",
            "CurrentLiabilitiesUSGAAP",
            "CurrentLiabilities",
        ],
    },
]

# 有利子負債（IBD）タグ定義
# analysis/interest_bearing_debt.py で使用

# 有利子負債合計タグ（直接法で使うタグ）
INTEREST_BEARING_DEBT_TAGS: list[str] = [
    "InterestBearingDebt",
    "InterestBearingLiabilities",
]

# 各コンポーネントのラベルと候補タグ名（J-GAAP → IFRS の優先順）
COMPONENT_DEFINITIONS: list[_ComponentDef] = [
    {
        "label": "短期借入金",
        "tags": [
            "ShortTermLoansPayable",        # J-GAAP
            "BorrowingsCLIFRS",             # IFRS 流動負債 借入金
        ],
    },
    {
        "label": "コマーシャル・ペーパー",
        "tags": [
            "CommercialPapersLiabilities",  # J-GAAP
            "CommercialPapersCLIFRS",       # IFRS
        ],
    },
    {
        "label": "短期社債",
        "tags": [
            "ShortTermBondsPayable",        # J-GAAP
        ],
    },
    {
        "label": "1年内償還予定の社債",
        "tags": [
            "CurrentPortionOfBonds",                    # J-GAAP
            "RedeemableBondsWithinOneYear",             # J-GAAP 別名
            "CurrentPortionOfBondsCLIFRS",              # IFRS
        ],
    },
    {
        "label": "1年内返済予定の長期借入金",
        "tags": [
            "CurrentPortionOfLongTermLoansPayable",     # J-GAAP
            "CurrentPortionOfLongTermBorrowingsCLIFRS", # IFRS 粒度別
        ],
    },
    {
        "label": "社債",
        "tags": [
            "BondsPayable",                 # J-GAAP
            "BondsPayableNCLIFRS",          # IFRS 非流動負債
        ],
    },
    {
        "label": "長期借入金",
        "tags": [
            "LongTermLoansPayable",         # J-GAAP
            "BorrowingsNCLIFRS",            # IFRS 非流動負債 借入金
        ],
    },
]

# 売上総利益（GP）タグ定義
# analysis/gross_profit.py で使用

# 売上総利益合計タグ（直接法）
# EDINET XBRL では IFRS連結は "IFRS" サフィックス付き、J-GAAP連結はサフィックスなし
GROSS_PROFIT_DIRECT_TAGS: list[str] = [
    "GrossProfitIFRS",  # IFRS連結（例: 味の素, 日立）
    "GrossProfit",      # J-GAAP連結（例: ニチレイ）
]

# 売上総利益 計算法コンポーネント（直接タグが存在しない場合のフォールバック）
# 売上高 − 売上原価 で計算する
GROSS_PROFIT_COMPONENT_DEFINITIONS: list[_ComponentDef] = [
    {
        "label": "売上高",
        "tags": [
            "NetSalesIFRS",     # IFRS連結
            "NetSales",         # J-GAAP連結
            "Revenue",          # IFRS代替
            "Revenues",         # US-GAAP
        ],
    },
    {
        "label": "売上原価",
        "tags": [
            "CostOfSalesIFRS",  # IFRS連結
            "CostOfSales",      # J-GAAP連結
            "CostOfRevenue",    # US-GAAP
        ],
    },
]

# 複数の構成要素を集約したIFRSタグ。
# 粒度別タグが存在しない場合に、カバーする個別コンポーネントを置き換える。
# キャッシュフロー（CF）タグ定義
# analysis/cash_flow.py で使用

# 営業活動によるキャッシュフロー
CF_OPERATING_TAGS: list[str] = [
    "NetCashProvidedByUsedInOperatingActivities",                       # J-GAAP 連結（CF計算書）
    "NetCashProvidedByUsedInOperatingActivitiesSummaryOfBusinessResults", # J-GAAP 連結（決算短信）
    "CashFlowsFromUsedInOperationsIFRS",                                # IFRS（間接法）
    "CashFlowsFromUsedInOperatingActivitiesIFRS",                       # IFRS（直接法）
    "CashFlowsFromUsedInOperatingActivitiesIFRSSummaryOfBusinessResults", # IFRS（決算短信）
]

# 投資活動によるキャッシュフロー
CF_INVESTING_TAGS: list[str] = [
    "NetCashProvidedByUsedInInvestingActivities",                       # J-GAAP 連結（CF計算書）
    "NetCashProvidedByUsedInInvestingActivitiesSummaryOfBusinessResults", # J-GAAP 連結（決算短信）
    "CashFlowsUsedInInvestingActivitiesIFRS",                           # IFRS
    "CashFlowsFromUsedInInvestingActivitiesIFRS",                       # IFRS（代替）
    "CashFlowsFromUsedInInvestingActivitiesIFRSSummaryOfBusinessResults", # IFRS（決算短信）
]

# 実効税率（Tax）タグ定義
# analysis/tax_expense.py で使用

# 税引前利益
PRETAX_INCOME_JGAAP_TAGS: list[str] = [
    "IncomeBeforeIncomeTaxes",
]
PRETAX_INCOME_IFRS_TAGS: list[str] = [
    "ProfitLossBeforeTaxIFRS",
]

# 法人税等
INCOME_TAX_JGAAP_TAGS: list[str] = [
    "IncomeTaxes",
]
INCOME_TAX_IFRS_TAGS: list[str] = [
    "IncomeTaxExpenseIFRS",
]

# 営業利益（OP）タグ定義
# analysis/operating_profit.py で使用

OPERATING_PROFIT_DIRECT_TAGS: list[str] = [
    "OperatingProfitLossIFRS",   # IFRS連結
    "OperatingIncomeLoss",       # J-GAAP連結（標準）
    "OperatingIncome",           # J-GAAP（旧タグ / 個別フォールバック）
]

ORDINARY_INCOME_TAGS: list[str] = [
    "OrdinaryIncome",            # J-GAAP 金融機関向け経常利益
    "OrdinaryIncomeLoss",        # J-GAAP 経常利益（代替）
]

# 営業利益 計算法: GrossProfit − SGA で算出する
# OperatingProfitLossIFRS が存在しない IFRS 企業（日立等）向けフォールバック

SGA_DIRECT_TAGS: list[str] = [
    "SellingGeneralAndAdministrativeExpensesIFRS",  # IFRS連結
    "SellingGeneralAndAdministrativeExpenses",       # J-GAAP連結
]

# 支払利息（IE）タグ定義
# analysis/interest_expense.py で使用

# J-GAAP: 営業外費用の支払利息
INTEREST_EXPENSE_JGAAP_TAGS: list[str] = [
    "InterestExpensesNOE",
]

# IFRS: 支払利息（InterestExpensesIFRS）を優先し、存在しない場合は金融費用合計（FinanceCostsIFRS）にフォールバック
INTEREST_EXPENSE_IFRS_TAGS: list[str] = [
    "InterestExpensesIFRS",   # 支払利息（推奨）
    "FinanceCostsIFRS",       # 金融費用合計（フォールバック）
]

AGGREGATE_IFRS_DEFINITIONS: list[_AggregateIFRSDef] = [
    {
        "tag": "CurrentPortionOfLongTermDebtCLIFRS",  # 1年内長期有利子負債（社債+借入金を集約）
        "covers": ["1年内償還予定の社債", "1年内返済予定の長期借入金"],
    },
    {
        "tag": "LongTermDebtNCLIFRS",                 # 長期有利子負債（社債+借入金を集約）
        "covers": ["社債", "長期借入金"],
    },
    {
        "tag": "BondsAndBorrowingsCLIFRS",             # 流動負債 社債及び借入金（社債+借入金を集約）
        "covers": ["1年内償還予定の社債", "1年内返済予定の長期借入金"],
    },
    {
        "tag": "BondsAndBorrowingsNCLIFRS",            # 非流動負債 社債及び借入金（社債+借入金を集約）
        "covers": ["社債", "長期借入金"],
    },
    {
        "tag": "InterestBearingLiabilitiesCLIFRS",     # 流動有利子負債合計（全流動コンポーネントを集約）
        "covers": ["短期借入金", "コマーシャル・ペーパー", "短期社債", "1年内償還予定の社債", "1年内返済予定の長期借入金"],
        "label": "流動有利子負債合計（集約）",
    },
    {
        "tag": "InterestBearingLiabilitiesNCLIFRS",    # 非流動有利子負債合計（全非流動コンポーネントを集約）
        "covers": ["社債", "長期借入金"],
    },
]

# 減価償却費（DA）タグ定義
# analysis/depreciation.py で使用

CF_DEPRECIATION_JGAAP_TAGS: list[str] = [
    "DepreciationAndAmortizationOpeCF",      # J-GAAP CF計算書（間接法）調整項目
]

CF_DEPRECIATION_IFRS_TAGS: list[str] = [
    "DepreciationAndAmortizationOpeCFIFRS",                   # IFRS CF計算書（一般的）
    "DepreciationAndAmortizationOfIntangibleAssetsOpeCFIFRS", # IFRS CF計算書（日立等）
]
