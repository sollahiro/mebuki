import logging
from typing import Dict, Any, List, Optional
from backend.utils.boj_client import BOJClient
from .macro_series_mapping import MONETARY_POLICY_SERIES, FX_SERIES
from backend.services.data_service import data_service

logger = logging.getLogger(__name__)

class MacroAnalyzer:
    """
    マクロ分析業務ロジッククラス（新API対応版）
    """
    def __init__(self):
        self.boj_client = BOJClient(cache=data_service.cache_manager)

    def get_monetary_policy_status(self, start_date: Optional[str] = None, end_date: Optional[str] = None) -> Dict[str, Any]:
        """金融政策の現状と時系列データを取得"""
        results = {}
        for key, info in MONETARY_POLICY_SERIES.items():
            db = info["db"]
            code = info["code"]
            results[key] = self.boj_client.get_time_series(db, code, start_date, end_date)
        
        return {
            "title": "金融政策 指標データ",
            "indicators": results,
            "description": "基準貸付利率、マネタリーベース、マネーストックM3の推移。"
        }

    def get_fx_environment(self, start_date: Optional[str] = None, end_date: Optional[str] = None) -> Dict[str, Any]:
        """為替環境のデータを取得"""
        results = {}
        for key, info in FX_SERIES.items():
            results[key] = self.boj_client.get_time_series(info["db"], info["code"], start_date, end_date)
            
        return {
            "title": "為替環境 指標データ",
            "indicators": results,
            "description": "ドル円スポットレート（17時）および実質実効為替レート。"
        }

# シングルトン
macro_analyzer = MacroAnalyzer()
