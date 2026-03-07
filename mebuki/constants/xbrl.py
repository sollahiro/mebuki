from typing import Dict, Any

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
