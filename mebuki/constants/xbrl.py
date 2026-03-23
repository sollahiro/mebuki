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

# 複数の構成要素を集約したIFRSタグ。
# 粒度別タグが存在しない場合に、カバーする個別コンポーネントを置き換える。
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
        "tag": "BondsAndBorrowingsNCLIFRS",            # 非流動負債 社債及び借入金（社債+借入金を集約）
        "covers": ["社債", "長期借入金"],
    },
]
