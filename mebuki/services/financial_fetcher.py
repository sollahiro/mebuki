"""
財務データフェッチャー

J-QUANTS APIからの財務データ・株価データ取得と指標計算を担当。
"""

import asyncio
import logging
from typing import List, Dict, Any, Optional

from mebuki.api.jquants_client import JQuantsAPIClient
from mebuki.utils.financial_data import extract_annual_data
from mebuki.analysis.calculator import calculate_metrics_flexible

logger = logging.getLogger(__name__)


class FinancialFetcher:
    """J-QUANTSからの財務データ・株価データ取得と指標計算"""

    def __init__(self, api_client: JQuantsAPIClient):
        self.api_client = api_client

    async def fetch_financial_data(
        self,
        code: str,
        include_2q: bool = False,
    ) -> tuple[Optional[Dict[str, Any]], Optional[List[Dict[str, Any]]], Optional[List[Dict[str, Any]]]]:
        """財務データを取得"""
        master_data, financial_data = await asyncio.gather(
            self.api_client.get_equity_master(code=code),
            self.api_client.get_financial_summary(
                code=code,
                period_types=["FY", "2Q"],
                include_fields=None,
            ),
        )

        stock_info = master_data[0] if master_data else {}

        if not stock_info:
            logger.warning(f"銘柄コード {code}: 銘柄マスタにデータが見つかりませんでした。")
            return None, None, None

        if not financial_data:
            logger.warning(f"銘柄コード {code}: 財務データが取得できませんでした。")
            return stock_info, None, None

        try:
            annual_data = extract_annual_data(financial_data, include_2q=include_2q)
        except Exception as e:
            logger.error(f"銘柄コード {code}: 年度データ抽出中にエラーが発生しました - {e}", exc_info=True)
            return stock_info, financial_data, None

        return stock_info, financial_data, annual_data

    async def calculate_metrics(
        self,
        code: str,
        annual_data: List[Dict[str, Any]],
        analysis_years: int,
    ) -> Optional[Dict[str, Any]]:
        """指標を計算"""
        try:
            return calculate_metrics_flexible(annual_data, analysis_years)
        except Exception as e:
            logger.error(f"銘柄コード {code}: 指標計算中にエラーが発生しました - {e}", exc_info=True)
            return None
