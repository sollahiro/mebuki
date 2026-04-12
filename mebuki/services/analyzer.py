"""
個別詳細分析モジュール

個別銘柄の詳細分析を実行します。
FinancialFetcher / EdinetFetcher を組み合わせてオーケストレーションします。
"""

import logging
import asyncio
from typing import List, Dict, Any, Optional
from pathlib import Path

from mebuki.api.jquants_client import JQuantsAPIClient
from mebuki.api.edinet_client import EdinetAPIClient
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
    ):
        self.api_client = api_client or JQuantsAPIClient(api_key=settings_store.jquants_api_key)

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
        actual_years = min(available_years, analysis_years) if analysis_years else available_years

        prices = await self._financial_fetcher.fetch_prices(code, annual_data, actual_years)
        metrics = await self._financial_fetcher.calculate_metrics(code, annual_data, prices, actual_years)

        edinet_data = {}
        ibd_by_year: Dict[str, dict] = {}
        gp_by_year: Dict[str, dict] = {}

        if financial_data:
            edinet_coro = self._edinet_fetcher.fetch_edinet_data_async(
                code, financial_data, max_documents=max_documents
            )
            ibd_coro = self._edinet_fetcher.extract_ibd_by_year(
                code, financial_data, actual_years
            )
            gp_coro = self._edinet_fetcher.extract_gross_profit_by_year(
                code, financial_data, actual_years
            )
            edinet_data, ibd_by_year, gp_by_year = await asyncio.gather(
                edinet_coro, ibd_coro, gp_coro
            )

        if financial_data and metrics:
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
