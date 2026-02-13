"""
データサービス
純粋なデータ取得・計算ロジック（LLM非依存）
"""

import logging
from typing import Dict, Any, List, Optional
from mebuki.api.jquants_client import JQuantsAPIClient
from mebuki.api.edinet_client import EdinetAPIClient
from mebuki.utils.cache import CacheManager
from .analyzer import IndividualAnalyzer
from backend.settings import settings_store

logger = logging.getLogger(__name__)

class DataService:
    """財務データおよび有報データの取得を行うクラス"""
    
    def __init__(self):
        # 起動時は settings_store のデフォルト値（空文字列など）が使用される
        from pathlib import Path
        self.api_client = JQuantsAPIClient(api_key=settings_store.jquants_api_key)
        
        # EDINETクライアントには明示的に Application Support 配下のキャッシュディレクトリを渡す
        edinet_cache = Path(settings_store.cache_dir) / "edinet"
        self.edinet_client = EdinetAPIClient(
            api_key=settings_store.edinet_api_key,
            cache_dir=str(edinet_cache)
        )
        
        self.cache_manager = CacheManager(
            cache_dir=settings_store.cache_dir,
            enabled=settings_store.cache_enabled
        )
        
    def reinitialize(self) -> None:
        """
        設定変更時に呼び出され、APIクライアントなどの設定を更新します。
        """
        from pathlib import Path
        logger.info("再初期化中: APIクライアントの設定を更新します")
        self.api_client.update_api_key(settings_store.jquants_api_key)
        self.edinet_client.update_api_key(settings_store.edinet_api_key)
        
        # キャッシュマネージャーの再設定
        # CacheManager内部でPathに変換されるが、すでにあるインスタンスの属性を上書きする場合
        # Pathオブジェクトであることを確実にする
        self.cache_manager.cache_dir = Path(settings_store.cache_dir)
        self.cache_manager.enabled = settings_store.cache_enabled
        self.cache_manager.cache_dir.mkdir(parents=True, exist_ok=True)
        
    def get_analyzer(self, use_cache: bool = True) -> IndividualAnalyzer:
        """
        IndividualAnalyzerのインスタンスを取得
        注意: このインスタンスはLLM機能制限版として使用することを想定
        """
        return IndividualAnalyzer(
            api_client=self.api_client,
            edinet_client=self.edinet_client,
            cache=self.cache_manager,
            use_cache=use_cache
        )

    async def search_companies(self, query: str) -> List[Dict[str, Any]]:
        """
        銘柄コードまたは名称で企業を検索します。
        MasterDataManager を使用して高速に検索します。
        """
        from .master_data import master_data_manager
        
        # MasterDataManager は内部でキャッシュ（メモリ保持）しているため、
        # ここでの DataService キャッシュは廃止し、委譲のみを行う
        return master_data_manager.search(query, limit=50)

    def fetch_stock_basic_info(self, code: str) -> Dict[str, Any]:
        """銘柄の基本情報を取得"""
        from .master_data import master_data_manager
        
        # API への問い合わせを廃止し、MasterDataManager (CSV) から取得
        stock_info = master_data_manager.get_by_code(code)
        if not stock_info:
            return {}
        
        return {
            "name": stock_info.get("CoName"),
            "name_en": stock_info.get("CoNameEn", ""), # CSVにない場合は空
            "sector_33": stock_info.get("S33"),
            "sector_33_name": stock_info.get("S33Nm"),
            "sector_17": stock_info.get("S17"),
            "sector_17_name": stock_info.get("S17Nm"),
            "market": stock_info.get("MktNm", "").split("（")[0].split("(")[0],
            "market_name": stock_info.get("MktNm", "").split("（")[0].split("(")[0],
        }

    async def get_raw_analysis_data(self, code: str, use_cache: bool = True, max_documents: int = 2) -> Dict[str, Any]:
        """
        AI分析抜きの純粋な分析データを取得（財務指標 + 有報テキスト）
        """
        analyzer = self.get_analyzer(use_cache=use_cache)
        
        # キャッシュの確認
        if use_cache:
            cached = self.cache_manager.get(f"individual_analysis_{code}")
            if cached:
                # AI分析結果を除去して返す
                if "llm_financial_analysis" in cached:
                    del cached["llm_financial_analysis"]
                return cached

        # 財務データの取得
        stock_info, financial_data, annual_data = analyzer._fetch_financial_data(code)
        if not stock_info:
            return {}
            
        # 指標計算
        available_years = len(annual_data)
        max_years = settings_store.get_max_analysis_years()
        analysis_years = min(available_years, max_years)
        
        prices = analyzer._fetch_prices(code, annual_data, analysis_years)
        metrics = analyzer._calculate_metrics(code, annual_data, prices, analysis_years)
        
        # EDINETデータの取得
        edinet_data = analyzer._fetch_edinet_data(code, financial_data, max_documents=max_documents)
        
        from datetime import datetime
        result = {
            "code": code,
            **self.fetch_stock_basic_info(code),
            "metrics": metrics,
            "edinet_data": edinet_data,
            "analyzed_at": datetime.now().isoformat()
        }
        
        return result

# シングルトンインスタンス
data_service = DataService()
