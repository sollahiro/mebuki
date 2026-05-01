"""
データサービス
純粋なデータ取得・計算ロジック（LLM非依存）
"""

import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from mebuki import __version__
from mebuki.api.jquants_client import JQuantsAPIClient
from mebuki.api.edinet_client import EdinetAPIClient
from mebuki.infrastructure.settings import settings_store
from mebuki.utils.cache import CacheManager

_CACHE_VERSION = ".".join(__version__.split(".")[:2])

from .analyzer import IndividualAnalyzer
from .company_info_service import CompanyInfoService
from .earnings_calendar_service import EarningsCalendarService
from .filing_service import FilingService
from .half_year_data_service import HalfYearDataService

logger = logging.getLogger(__name__)


class DataService:
    """財務データおよび有報データの取得を行うクラス"""

    def __init__(self):
        self.api_client = JQuantsAPIClient(api_key=settings_store.jquants_api_key)
        edinet_cache = Path(settings_store.cache_dir) / "edinet"
        self.edinet_client = EdinetAPIClient(
            api_key=settings_store.edinet_api_key,
            cache_dir=str(edinet_cache),
        )
        self.cache_manager = CacheManager(
            cache_dir=settings_store.cache_dir,
            enabled=settings_store.cache_enabled,
        )
        self.company_info_service = CompanyInfoService()
        self.earnings_calendar_service = EarningsCalendarService(
            self.api_client,
            self.cache_manager,
        )
        self.filing_service = FilingService(self.api_client, self.edinet_client)
        self.half_year_data_service = HalfYearDataService(
            self.api_client,
            self.edinet_client,
            self.cache_manager,
        )

    def _sync_child_services(self) -> None:
        """テストや再初期化で差し替えられた共有依存を委譲先にも反映する。"""
        self.earnings_calendar_service.api_client = self.api_client
        self.earnings_calendar_service.cache_manager = self.cache_manager
        self.filing_service.api_client = self.api_client
        self.filing_service.edinet_client = self.edinet_client
        self.half_year_data_service.api_client = self.api_client
        self.half_year_data_service.edinet_client = self.edinet_client
        self.half_year_data_service.cache_manager = self.cache_manager

    async def _refresh_earnings_calendar_if_needed(self) -> None:
        """1日1回、決算カレンダーのストアを更新する"""
        self._sync_child_services()
        await self.earnings_calendar_service.refresh_if_needed()

    async def close(self) -> None:
        """全APIクライアントのセッションをクローズする"""
        await self.api_client.close()
        await self.edinet_client.close()

    def reinitialize(self) -> None:
        """設定変更時に呼び出され、APIクライアントなどの設定を更新します。"""
        logger.info("再初期化中: APIクライアントの設定を更新します")
        self.api_client.update_api_key(settings_store.jquants_api_key)
        self.edinet_client.update_api_key(settings_store.edinet_api_key)

        self.cache_manager.cache_dir = Path(settings_store.cache_dir)
        self.cache_manager.enabled = settings_store.cache_enabled
        self.cache_manager.cache_dir.mkdir(parents=True, exist_ok=True)
        self.earnings_calendar_service = EarningsCalendarService(
            self.api_client,
            self.cache_manager,
        )
        self.filing_service = FilingService(self.api_client, self.edinet_client)
        self.half_year_data_service = HalfYearDataService(
            self.api_client,
            self.edinet_client,
            self.cache_manager,
        )

    def get_analyzer(self) -> IndividualAnalyzer:
        """IndividualAnalyzerのインスタンスを取得"""
        return IndividualAnalyzer(
            api_client=self.api_client,
            edinet_client=self.edinet_client,
        )

    async def search_companies(self, query: str) -> list[dict[str, Any]]:
        """銘柄コードまたは名称で企業を検索します。"""
        return await self.company_info_service.search_companies(query)

    def fetch_stock_basic_info(self, code: str) -> dict[str, Any]:
        """銘柄の基本情報を取得"""
        return self.company_info_service.fetch_stock_basic_info(code)

    def _attach_upcoming_earnings(self, result: dict, code: str) -> None:
        """決算スケジュールを result に付与する（該当なければ何もしない）"""
        self.earnings_calendar_service.attach_upcoming_earnings(result, code)

    async def get_financial_data(
        self,
        code: str,
        scope: str | None = None,
        use_cache: bool = True,
        include_2q: bool = False,
        analysis_years: int | None = None,
    ) -> dict[str, Any] | list[dict[str, Any]]:
        """財務データ取得の統一公開API。scope=None で財務サマリー、scope="raw" で生データ。"""
        if scope == "raw":
            raw_data = await self.api_client.get_financial_summary(code=code)
            return [
                {k: v for k, v in record.items() if v is not None and v != ""}
                for record in raw_data
            ]

        result = await self.get_raw_analysis_data(code, use_cache=use_cache, include_2q=include_2q, analysis_years=analysis_years)
        try:
            await self._refresh_earnings_calendar_if_needed()
            self._attach_upcoming_earnings(result, code)
        except Exception:
            pass
        return result

    async def get_half_year_periods(
        self,
        code: str,
        years: int = 3,
        use_cache: bool = True,
    ) -> list[dict[str, Any]]:
        """H1/H2 の半期財務データを返す。"""
        self._sync_child_services()
        return await self.half_year_data_service.get_half_year_periods(
            code=code,
            years=years,
            use_cache=use_cache,
        )

    async def search_filings(
        self,
        code: str,
        max_years: int = 10,
        doc_types: list[str] | None = None,
        max_documents: int = 10,
    ) -> list[dict[str, Any]]:
        """EDINET書類を検索"""
        self._sync_child_services()
        return await self.filing_service.search_filings(
            code=code,
            max_years=max_years,
            doc_types=doc_types,
            max_documents=max_documents,
        )

    async def extract_filing_content(
        self,
        code: str,
        doc_id: str | None = None,
        sections: list[str] | None = None,
    ) -> dict[str, Any]:
        """EDINET書類からセクションを抽出"""
        self._sync_child_services()
        return await self.filing_service.extract_filing_content(
            code=code,
            doc_id=doc_id,
            sections=sections,
        )

    async def get_raw_analysis_data(
        self,
        code: str,
        use_cache: bool = True,
        max_documents: int = 2,
        analysis_years: int | None = None,
        include_2q: bool = False,
    ) -> dict[str, Any]:
        """AI分析抜きの純粋な分析データを取得（財務指標 + 有報テキスト）"""
        cache_key = f"individual_analysis_{code}"
        analyzer = self.get_analyzer()

        if use_cache:
            cached = self.cache_manager.get(cache_key)
            if cached and cached.get("_cache_version") == _CACHE_VERSION:
                return {k: v for k, v in cached.items() if k != "_cache_version" and k != "llm_financial_analysis"}

        result = await analyzer.fetch_analysis_data(code, analysis_years, max_documents, include_2q=include_2q)
        if not result:
            return {}

        formatted = {
            "_cache_version": _CACHE_VERSION,
            "code": code,
            **self.fetch_stock_basic_info(code),
            "metrics": result["metrics"],
            "edinet_data": result["edinet_data"],
            "analyzed_at": datetime.now().isoformat(),
        }
        self.cache_manager.set(cache_key, formatted)
        return {k: v for k, v in formatted.items() if k != "_cache_version"}


# シングルトンインスタンス
data_service = DataService()
