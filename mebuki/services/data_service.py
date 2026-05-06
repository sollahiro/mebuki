"""
データサービス
純粋なデータ取得・計算ロジック（LLM非依存）
"""

import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from mebuki import __version__
from mebuki.api.edinet_client import EdinetAPIClient
from mebuki.infrastructure.settings import settings_store
from mebuki.constants.financial import (
    PERCENT,
    WACC_DEFAULT_BETA,
    WACC_MARKET_RISK_PREMIUM,
    WACC_RF_FALLBACK,
)
from mebuki.utils.cache import CacheManager
from mebuki.utils.master_types import StockSearchResult
from mebuki.utils.output_serializer import serialize_metrics_result

_CACHE_VERSION = ".".join(__version__.split(".")[:2])

from .analyzer import IndividualAnalyzer
from .company_info_service import CompanyInfoService
from .filing_service import FilingService
from .half_year_data_service import HalfYearDataService

logger = logging.getLogger(__name__)


def _apply_debug_filter(result: dict[str, Any], include_debug_fields: bool) -> dict[str, Any]:
    if include_debug_fields or not result.get("metrics"):
        return result
    return {**result, "metrics": serialize_metrics_result(result["metrics"])}


def _analysis_year_count(cached: dict[str, Any]) -> int:
    metrics = cached.get("metrics")
    if not isinstance(metrics, dict):
        return 0
    years = metrics.get("years")
    return len(years) if isinstance(years, list) else 0


def _trim_analysis_years(result: dict[str, Any], analysis_years: int | None) -> dict[str, Any]:
    if analysis_years is None:
        return result
    metrics = result.get("metrics")
    if not isinstance(metrics, dict):
        return result
    years = metrics.get("years")
    if not isinstance(years, list) or len(years) <= analysis_years:
        return result

    trimmed_metrics = dict(metrics)
    trimmed_metrics["years"] = years[:analysis_years]
    trimmed_metrics["analysis_years"] = analysis_years
    trimmed_metrics["available_years"] = analysis_years
    return {**result, "metrics": trimmed_metrics}


def _has_incomplete_edinet_metrics(cached: dict[str, Any]) -> bool:
    """EDINET 書類が紐づいているのに新しいEDINET指標が欠けた古い分析キャッシュを検出する。"""
    metrics = cached.get("metrics")
    if not isinstance(metrics, dict):
        return False
    years = metrics.get("years")
    if not isinstance(years, list):
        return False

    for year in years:
        if not isinstance(year, dict):
            continue
        calculated = year.get("CalculatedData")
        if not isinstance(calculated, dict):
            continue
        if calculated.get("DocID") and (
            calculated.get("InterestBearingDebt") is None
            or calculated.get("ROIC") is None
            or "CurrentAssets" not in calculated
            or "NonCurrentAssets" not in calculated
            or "CurrentLiabilities" not in calculated
            or "NonCurrentLiabilities" not in calculated
            or "NetAssets" not in calculated
        ):
            return True
    return False


def _has_fallback_mof_metrics(cached: dict[str, Any]) -> bool:
    """MOF 金利取得失敗時のフォールバック Rf で作られた分析キャッシュを検出する。"""
    metrics = cached.get("metrics")
    if not isinstance(metrics, dict):
        return False
    years = metrics.get("years")
    if not isinstance(years, list):
        return False

    fallback_cost_of_equity = (WACC_RF_FALLBACK + WACC_DEFAULT_BETA * WACC_MARKET_RISK_PREMIUM) * PERCENT
    for year in years:
        if not isinstance(year, dict):
            continue
        calculated = year.get("CalculatedData")
        if not isinstance(calculated, dict):
            continue
        sources = calculated.get("MetricSources")
        cost_of_equity_source = sources.get("CostOfEquity") if isinstance(sources, dict) else None
        if not isinstance(cost_of_equity_source, dict) or cost_of_equity_source.get("source") != "mof":
            continue
        rf_source = cost_of_equity_source.get("rf_source")
        if rf_source == "fallback":
            return True
        if rf_source is not None:
            continue
        cost_of_equity = calculated.get("CostOfEquity")
        if isinstance(cost_of_equity, float) and cost_of_equity == fallback_cost_of_equity:
            return True
    return False


class DataService:
    """財務データおよび有報データの取得を行うクラス"""

    def __init__(self) -> None:
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
        self.filing_service = FilingService(self.edinet_client)
        self.half_year_data_service = HalfYearDataService(
            self.edinet_client,
            self.cache_manager,
        )

    def _sync_child_services(self) -> None:
        """テストや再初期化で差し替えられた共有依存を委譲先にも反映する。"""
        self.filing_service.edinet_client = self.edinet_client
        self.half_year_data_service.edinet_client = self.edinet_client
        self.half_year_data_service.cache_manager = self.cache_manager

    async def close(self) -> None:
        """全APIクライアントのセッションをクローズする"""
        await self.edinet_client.close()

    def reinitialize(self) -> None:
        """設定変更時に呼び出され、APIクライアントなどの設定を更新します。"""
        logger.info("再初期化中: APIクライアントの設定を更新します")
        self.edinet_client.update_api_key(settings_store.edinet_api_key)

        self.cache_manager.cache_dir = Path(settings_store.cache_dir)
        self.cache_manager.enabled = settings_store.cache_enabled
        self.cache_manager.cache_dir.mkdir(parents=True, exist_ok=True)
        self.filing_service = FilingService(self.edinet_client)
        self.half_year_data_service = HalfYearDataService(
            self.edinet_client,
            self.cache_manager,
        )

    def get_analyzer(self) -> IndividualAnalyzer:
        """IndividualAnalyzerのインスタンスを取得"""
        return IndividualAnalyzer(
            edinet_client=self.edinet_client,
            cache_manager=self.cache_manager,
        )

    async def search_companies(self, query: str) -> list[StockSearchResult]:
        """銘柄コードまたは名称で企業を検索します。"""
        return await self.company_info_service.search_companies(query)

    def fetch_stock_basic_info(self, code: str) -> dict[str, Any]:
        """銘柄の基本情報を取得"""
        return self.company_info_service.fetch_stock_basic_info(code)

    async def get_financial_data(
        self,
        code: str,
        use_cache: bool = True,
        include_2q: bool = False,
        analysis_years: int | None = None,
        include_debug_fields: bool = False,
    ) -> dict[str, Any]:
        """財務データ取得の統一公開API。財務サマリーを返す。"""
        result = await self.get_raw_analysis_data(code, use_cache=use_cache, include_2q=include_2q, analysis_years=analysis_years, include_debug_fields=include_debug_fields)
        return result

    async def get_half_year_periods(
        self,
        code: str,
        years: int = 3,
        use_cache: bool = True,
        include_debug_fields: bool = False,
    ) -> list[dict[str, Any]]:
        """H1/H2 の半期財務データを返す。"""
        self._sync_child_services()
        return await self.half_year_data_service.get_half_year_periods(
            code=code,
            years=years,
            use_cache=use_cache,
            include_debug_fields=include_debug_fields,
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
        include_debug_fields: bool = False,
    ) -> dict[str, Any]:
        """AI分析抜きの純粋な分析データを取得（財務指標 + 有報テキスト）"""
        cache_key = f"individual_analysis_{code}"
        analyzer = self.get_analyzer()

        if use_cache:
            cached = self.cache_manager.get(cache_key)
            if (
                cached
                and cached.get("_cache_version") == _CACHE_VERSION
                and not _has_incomplete_edinet_metrics(cached)
                and not _has_fallback_mof_metrics(cached)
                and (analysis_years is None or _analysis_year_count(cached) >= analysis_years)
            ):
                result = {k: v for k, v in cached.items() if k != "_cache_version" and k != "llm_financial_analysis"}
                result = _trim_analysis_years(result, analysis_years)
                return _apply_debug_filter(result, include_debug_fields)

        stock_info = {"Code": code, **self.fetch_stock_basic_info(code)}
        financial_data: list[dict[str, Any]] = []

        result = await analyzer.fetch_analysis_data(
            code,
            analysis_years,
            max_documents,
            include_2q=include_2q,
            prefetched_stock_info=stock_info,
            prefetched_financial_data=financial_data,
        )
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
        output = {k: v for k, v in formatted.items() if k != "_cache_version"}
        output = _trim_analysis_years(output, analysis_years)
        return _apply_debug_filter(output, include_debug_fields)


# シングルトンインスタンス
data_service = DataService()
