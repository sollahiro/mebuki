"""
個別詳細分析モジュール

個別銘柄の詳細分析を実行します。
FinancialFetcher / EdinetFetcher を組み合わせてオーケストレーションします。
"""

import logging
import asyncio
from typing import List, Dict, Any, Optional, Callable, AsyncGenerator
from datetime import datetime
from pathlib import Path

from mebuki.api.jquants_client import JQuantsAPIClient
from mebuki.api.edinet_client import EdinetAPIClient
from mebuki.utils.cache import CacheManager
from mebuki.infrastructure.settings import settings_store
from mebuki.constants.financial import PERCENT, MILLION_YEN

from .financial_fetcher import FinancialFetcher
from .edinet_fetcher import EdinetFetcher

logger = logging.getLogger(__name__)


class IndividualAnalyzer:
    """個別詳細分析クラス"""

    def __init__(
        self,
        api_client: Optional[JQuantsAPIClient] = None,
        edinet_client: Optional[EdinetAPIClient] = None,
        cache: Optional[CacheManager] = None,
        use_cache: bool = True,
    ):
        """
        初期化

        Args:
            api_client: J-QUANTS APIクライアント。Noneの場合は新規作成
            edinet_client: EDINET APIクライアント。Noneの場合は新規作成
            cache: キャッシュマネージャー。Noneの場合は新規作成
            use_cache: キャッシュを使用するか
        """
        self.api_client = api_client or JQuantsAPIClient(api_key=settings_store.jquants_api_key)
        self.use_cache = use_cache
        self.cache = cache if cache is not None else (
            CacheManager(
                cache_dir=settings_store.cache_dir,
                enabled=settings_store.cache_enabled,
            ) if use_cache else None
        )

        # EDINET統合
        if edinet_client is not None:
            self.edinet_client = edinet_client
        else:
            try:
                edinet_cache_dir = Path(settings_store.cache_dir) / "edinet"
                self.edinet_client = EdinetAPIClient(
                    api_key=settings_store.edinet_api_key,
                    cache_dir=str(edinet_cache_dir),
                )
            except Exception as e:
                logger.warning(f"EDINETクライアントの初期化に失敗しました: {e}")
                self.edinet_client = None

        self._financial_fetcher = FinancialFetcher(self.api_client)
        self._edinet_fetcher = EdinetFetcher(self.api_client, self.edinet_client)

    # ------------------------------------------------------------------
    # 公開メソッド: EDINET（後方互換として IndividualAnalyzer 経由で提供）
    # ------------------------------------------------------------------

    async def fetch_edinet_reports_stream(
        self,
        code: str,
        financial_data: List[Dict[str, Any]],
        max_documents: int = 20,
        edinet_code: Optional[str] = None,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """EDINET書類を取得し、準備ができた段階で順次yieldする"""
        async for item in self._edinet_fetcher.fetch_edinet_reports_stream(
            code, financial_data, max_documents, edinet_code
        ):
            yield item

    def fetch_edinet_reports(
        self,
        code: str,
        years: List[int],
        jquants_annual_data: Optional[List[Dict[str, Any]]] = None,
        progress_callback: Optional[Callable] = None,
        edinet_code: Optional[str] = None,
        max_documents: int = 20,
    ) -> Dict[int, List[Dict[str, Any]]]:
        """指定年度の有価証券報告書を取得（同期互換用）"""
        return self._edinet_fetcher.fetch_edinet_reports(
            code, years, jquants_annual_data, progress_callback, edinet_code, max_documents
        )

    # ------------------------------------------------------------------
    # 内部フロー
    # ------------------------------------------------------------------

    async def _edinet_flow(
        self,
        code: str,
        financial_data: List[Dict[str, Any]],
        edinet_code: Optional[str],
        result: Dict[str, Any],
        queue: asyncio.Queue,
    ) -> None:
        """EDINETフロー: 書類取得をストリーミングで result へ反映し queue へ通知"""
        try:
            existing_indices: Dict[str, Dict[str, int]] = {}
            async for data in self._edinet_fetcher.fetch_edinet_reports_stream(
                code, financial_data, edinet_code=edinet_code
            ):
                fy_key = data["fy_key"]
                report = data["report"]

                if "edinet_data" not in result:
                    result["edinet_data"] = {}

                fy_key_str = str(fy_key)
                if fy_key_str not in result["edinet_data"]:
                    result["edinet_data"][fy_key_str] = []
                    existing_indices[fy_key_str] = {}

                doc_id = report["docID"]
                if doc_id in existing_indices.get(fy_key_str, {}):
                    result["edinet_data"][fy_key_str][existing_indices[fy_key_str][doc_id]] = report
                else:
                    existing_indices.setdefault(fy_key_str, {})[doc_id] = len(
                        result["edinet_data"][fy_key_str]
                    )
                    result["edinet_data"][fy_key_str].append(report)

                edinet_snapshot = {k: list(v) for k, v in result.get("edinet_data", {}).items()}
                await queue.put({**result, "edinet_data": edinet_snapshot})
        except Exception as e:
            logger.error(f"EDINETフローエラー: {e}", exc_info=True)
            edinet_snapshot = {k: list(v) for k, v in result.get("edinet_data", {}).items()}
            await queue.put({**result, "edinet_data": edinet_snapshot})

    async def _main_flow(
        self,
        code: str,
        cache_key: str,
        result: Dict[str, Any],
        queue: asyncio.Queue,
        include_2q: bool = False,
    ) -> None:
        """メインフロー: 財務データ取得 -> 指標計算 -> 株価反映 -> EDINETを並列実行"""
        try:
            stock_info, financial_data, annual_data = await self._financial_fetcher.fetch_financial_data(code, include_2q)
            if not stock_info or not financial_data or not annual_data:
                await queue.put({"status": "error", "message": "財務データの取得に失敗しました"})
                return

            result.update({
                "name": stock_info.get("CoName"),
                "name_en": stock_info.get("CoNameEn"),
                "sector_33_name": stock_info.get("S33Nm"),
                "market_name": stock_info.get("MktNm"),
            })

            available_years = sum(1 for d in annual_data if d.get("CurPerType") == "FY")
            max_years = settings_store.get_max_analysis_years()
            analysis_years = min(available_years, max_years)

            edinet_code = stock_info.get("EdinetCode")
            edinet_task = asyncio.create_task(
                self._edinet_flow(code, financial_data, edinet_code, result, queue)
            )
            prices = await self._financial_fetcher.fetch_prices(code, annual_data, analysis_years)
            metrics = await self._financial_fetcher.calculate_metrics(code, annual_data, prices, analysis_years)

            if metrics:
                result["metrics"] = metrics
                result["status"] = "fetching_edinet"
                result["message"] = "有価証券報告書を取得中..."
                await queue.put(dict(result))
            else:
                await queue.put({"status": "error", "message": "株価反映後の指標計算に失敗しました"})
                return

            await edinet_task

            result["status"] = "complete"
            result["message"] = "分析完了"
            if self.cache:
                self.cache.set(cache_key, result.copy())
            await queue.put(result)

        except Exception as e:
            logger.error(f"メインフローエラー: {e}", exc_info=True)
            await queue.put({"status": "error", "message": str(e)})

    # ------------------------------------------------------------------
    # 公開API
    # ------------------------------------------------------------------

    async def analyze_stock_stream(self, code: str) -> AsyncGenerator[Dict[str, Any], None]:
        """銘柄分析をストリーミング形式で実行（並列化版）"""
        cache_key = f"individual_analysis_{code}"

        if self.use_cache and self.cache:
            cached_result = self.cache.get(cache_key)
            if cached_result is not None:
                cached_result["status"] = "complete"
                cached_result["message"] = "分析完了（キャッシュ）"
                yield cached_result
                return

        result = {
            "code": code,
            "status": "initializing",
            "message": "銘柄データを取得中...",
            "analyzed_at": datetime.now().isoformat(),
        }

        queue: asyncio.Queue = asyncio.Queue()
        main_task = asyncio.create_task(self._main_flow(code, cache_key, result, queue))

        try:
            yield result

            finished = False
            while not finished:
                try:
                    item = await asyncio.wait_for(queue.get(), timeout=1.0)
                    yield item

                    if item.get("status") in ["complete", "error"]:
                        finished = True

                except asyncio.TimeoutError:
                    if main_task.done():
                        if queue.empty():
                            finished = True
                    continue
                except Exception as e:
                    logger.error(f"配信ループエラー: {e}")
                    finished = True
        finally:
            if not main_task.done():
                logger.info(f"分析タスクをキャンセルします: {code}")
                main_task.cancel()
                try:
                    await main_task
                except asyncio.CancelledError:
                    pass
                except Exception as e:
                    logger.error(f"タスクキャンセル中のエラー: {e}")

    async def analyze_stock(
        self,
        code: str,
        progress_callback: Optional[Callable] = None,
        include_2q: bool = False,
    ) -> Optional[Dict[str, Any]]:
        """個別銘柄を詳細分析"""
        cache_key = f"individual_analysis_{code}"

        if self.use_cache and self.cache:
            cached_result = self.cache.get(cache_key)
            if cached_result is not None:
                return cached_result

        try:
            stock_info, financial_data, annual_data = await self._financial_fetcher.fetch_financial_data(code, include_2q)
            if not stock_info or not financial_data or not annual_data:
                return None

            available_years = sum(1 for d in annual_data if d.get("CurPerType") == "FY")
            max_years = settings_store.get_max_analysis_years()
            analysis_years = min(available_years, max_years)

            edinet_task = asyncio.create_task(
                self._edinet_fetcher.fetch_edinet_data_async(
                    code, financial_data, edinet_code=stock_info.get("EdinetCode")
                )
            )

            prices = await self._financial_fetcher.fetch_prices(code, annual_data, analysis_years)
            metrics = await self._financial_fetcher.calculate_metrics(code, annual_data, prices, analysis_years)
            if not metrics:
                edinet_task.cancel()
                return None

            result = {
                "code": code,
                "name": stock_info.get("CoName"),
                "name_en": stock_info.get("CoNameEn"),
                "sector_33_name": stock_info.get("S33Nm"),
                "market_name": stock_info.get("MktNm"),
                "metrics": metrics,
                "analyzed_at": datetime.now().isoformat(),
            }

            edinet_data = await edinet_task
            if edinet_data:
                result["edinet_data"] = edinet_data

            if self.cache:
                self.cache.set(cache_key, result)

            return result
        except Exception as e:
            logger.error(f"エラー: {code} の分析に失敗しました: {e}", exc_info=True)
            return None

    async def get_metrics(
        self,
        code: str,
        analysis_years: Optional[int] = None,
        include_2q: bool = False,
    ) -> Optional[Dict[str, Any]]:
        """
        指標データのみを返す公開API。
        上位層（CLI/MCP）は private メソッドへ依存せず、このメソッドを利用する。
        """
        stock_info, _, annual_data = await self._financial_fetcher.fetch_financial_data(code, include_2q)
        if not stock_info or not annual_data:
            return None

        max_years = analysis_years or settings_store.get_max_analysis_years()
        fy_count = sum(1 for d in annual_data if d.get("CurPerType") == "FY")
        years = min(fy_count, max_years)
        prices = await self._financial_fetcher.fetch_prices(code, annual_data, years)
        return await self._financial_fetcher.calculate_metrics(code, annual_data, prices, years)

    async def retry_edinet_fetch(self, code: str) -> AsyncGenerator[Dict[str, Any], None]:
        """EDINET書類取得のみを再試行"""
        cache_key = f"individual_analysis_{code}"
        result = self.cache.get(cache_key) if self.cache else None

        if not result:
            yield {"status": "error", "message": "キャッシュデータが見つかりません。"}
            return

        try:
            stock_info, financial_data, annual_data = await self._financial_fetcher.fetch_financial_data(code)

            if not financial_data:
                yield {"status": "error", "message": "EDINET検索に必要な財務情報が取得できませんでした。"}
                return

            result["status"] = "fetching_edinet"
            result["message"] = "有価証券報告書を再取得中..."
            yield result.copy()

            edinet_data = await self._edinet_fetcher.fetch_edinet_data_async(
                code, financial_data, max_documents=10
            )
            if edinet_data:
                result["edinet_data"] = edinet_data

            result["status"] = "complete"
            result["message"] = "EDINET取得完了"
            if self.cache:
                self.cache.set(cache_key, result)
            yield result.copy()

        except Exception as e:
            logger.error(f"EDINET再取得エラー: {e}", exc_info=True)
            yield {"status": "error", "message": str(e)}

    async def fetch_analysis_data(
        self,
        code: str,
        analysis_years: int | None = None,
        max_documents: int = 10,
        include_2q: bool = False,
    ) -> Dict[str, Any]:
        """財務指標 + EDINETデータを取得する公開API（use_cache=False）。

        data_service などの上位層が private メソッドを直接呼ばずに済むよう提供する。
        """
        stock_info, financial_data, annual_data = await self._financial_fetcher.fetch_financial_data(code, include_2q)
        if not stock_info or not annual_data:
            return {}

        available_years = sum(1 for d in annual_data if d.get("CurPerType") == "FY")
        max_years = analysis_years or settings_store.get_max_analysis_years()
        actual_years = min(available_years, max_years)

        prices = await self._financial_fetcher.fetch_prices(code, annual_data, actual_years)
        metrics = await self._financial_fetcher.calculate_metrics(code, annual_data, prices, actual_years)

        edinet_data = {}
        if financial_data:
            edinet_data = await self._edinet_fetcher.fetch_edinet_data_async(
                code, financial_data, max_documents=max_documents
            )

        if financial_data and metrics:
            ibd_by_year = await self._edinet_fetcher.extract_ibd_by_year(
                code, financial_data, actual_years
            )
            for year in metrics.get("years", []):
                fy_end = year.get("fy_end", "")
                fy_end_key = fy_end.replace("-", "")
                ibd = ibd_by_year.get(fy_end_key)
                if ibd and ibd.get("current") is not None:
                    ibd_m = ibd["current"] / MILLION_YEN
                    year["CalculatedData"]["InterestBearingDebt"] = ibd_m
                    raw_comps = ibd.get("components", [])
                    year["CalculatedData"]["IBDComponents"] = [
                        {
                            "label": c["label"],
                            "current": c["current"] / MILLION_YEN if c["current"] is not None else None,
                            "prior": c["prior"] / MILLION_YEN if c["prior"] is not None else None,
                        }
                        for c in raw_comps
                    ]
                    year["CalculatedData"]["IBDAccountingStandard"] = ibd.get(
                        "accounting_standard", "unknown"
                    )
                    np_ = year["CalculatedData"].get("NP")
                    eq = year["CalculatedData"].get("Eq")
                    if np_ is not None and eq is not None and (eq + ibd_m) != 0:
                        year["CalculatedData"]["ROIC"] = np_ / (eq + ibd_m) * PERCENT

            gp_by_year = await self._edinet_fetcher.extract_gross_profit_by_year(
                code, financial_data, actual_years
            )
            for year in metrics.get("years", []):
                fy_end_key = year.get("fy_end", "").replace("-", "")
                gp = gp_by_year.get(fy_end_key)
                if gp and gp.get("current") is not None:
                    # Sales の直後に挿入するため dict を再構築
                    gp_m = gp["current"] / MILLION_YEN
                    old_cd = year["CalculatedData"]
                    new_cd: dict = {}
                    for k, v in old_cd.items():
                        new_cd[k] = v
                        if k == "Sales":
                            new_cd["GrossProfit"] = gp_m
                            new_cd["GrossProfitMethod"] = gp.get("method", "unknown")
                            sales = new_cd.get("Sales")
                            new_cd["GrossProfitMargin"] = gp_m / sales * PERCENT if sales else None
                    if "GrossProfit" not in new_cd:
                        new_cd["GrossProfit"] = gp_m
                        new_cd["GrossProfitMethod"] = gp.get("method", "unknown")
                        sales = new_cd.get("Sales")
                        new_cd["GrossProfitMargin"] = gp_m / sales * PERCENT if sales else None
                    year["CalculatedData"] = new_cd

        return {
            "stock_info": stock_info,
            "financial_data": financial_data,
            "annual_data": annual_data,
            "metrics": metrics,
            "edinet_data": edinet_data,
        }


# 互換性維持
# パターン評価関数は patterns.py に移動済み
