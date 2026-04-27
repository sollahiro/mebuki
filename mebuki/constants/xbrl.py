from typing import Dict, Any, List

XBRL_SECTIONS: Dict[str, Dict[str, Any]] = {
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

# 有利子負債（IBD）タグ定義
# analysis/interest_bearing_debt.py で使用

# 有利子負債合計タグ（直接法で使うタグ）
INTEREST_BEARING_DEBT_TAGS: List[str] = [
    "InterestBearingDebt",
    "InterestBearingLiabilities",
]

# 各コンポーネントのラベルと候補タグ名（J-GAAP → IFRS の優先順）
COMPONENT_DEFINITIONS: List[Dict[str, Any]] = [
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
GROSS_PROFIT_DIRECT_TAGS: List[str] = [
    "GrossProfitIFRS",  # IFRS連結（例: 味の素, 日立）
    "GrossProfit",      # J-GAAP連結（例: ニチレイ）
]

# 売上総利益 計算法コンポーネント（直接タグが存在しない場合のフォールバック）
# 売上高 − 売上原価 で計算する
GROSS_PROFIT_COMPONENT_DEFINITIONS: List[Dict[str, Any]] = [
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
CF_OPERATING_TAGS: List[str] = [
    "NetCashProvidedByUsedInOperatingActivities",                       # J-GAAP 連結（CF計算書）
    "NetCashProvidedByUsedInOperatingActivitiesSummaryOfBusinessResults", # J-GAAP 連結（決算短信）
    "CashFlowsFromUsedInOperationsIFRS",                                # IFRS（間接法）
    "CashFlowsFromUsedInOperatingActivitiesIFRS",                       # IFRS（直接法）
    "CashFlowsFromUsedInOperatingActivitiesIFRSSummaryOfBusinessResults", # IFRS（決算短信）
]

# 投資活動によるキャッシュフロー
CF_INVESTING_TAGS: List[str] = [
    "NetCashProvidedByUsedInInvestingActivities",                       # J-GAAP 連結（CF計算書）
    "NetCashProvidedByUsedInInvestingActivitiesSummaryOfBusinessResults", # J-GAAP 連結（決算短信）
    "CashFlowsUsedInInvestingActivitiesIFRS",                           # IFRS
    "CashFlowsFromUsedInInvestingActivitiesIFRS",                       # IFRS（代替）
    "CashFlowsFromUsedInInvestingActivitiesIFRSSummaryOfBusinessResults", # IFRS（決算短信）
]

# 実効税率（Tax）タグ定義
# analysis/tax_expense.py で使用

# 税引前利益
PRETAX_INCOME_JGAAP_TAGS: List[str] = [
    "IncomeBeforeIncomeTaxes",
]
PRETAX_INCOME_IFRS_TAGS: List[str] = [
    "ProfitLossBeforeTaxIFRS",
]

# 法人税等
INCOME_TAX_JGAAP_TAGS: List[str] = [
    "IncomeTaxes",
]
INCOME_TAX_IFRS_TAGS: List[str] = [
    "IncomeTaxExpenseIFRS",
]

# 支払利息（IE）タグ定義
# analysis/interest_expense.py で使用

# J-GAAP: 営業外費用の支払利息
INTEREST_EXPENSE_JGAAP_TAGS: List[str] = [
    "InterestExpensesNOE",
]

# IFRS: 支払利息（InterestExpensesIFRS）を優先し、存在しない場合は金融費用合計（FinanceCostsIFRS）にフォールバック
INTEREST_EXPENSE_IFRS_TAGS: List[str] = [
    "InterestExpensesIFRS",   # 支払利息（推奨）
    "FinanceCostsIFRS",       # 金融費用合計（フォールバック）
]

AGGREGATE_IFRS_DEFINITIONS: List[Dict[str, Any]] = [
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
