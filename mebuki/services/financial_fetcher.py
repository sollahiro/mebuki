"""
財務データフェッチャー

J-QUANTS APIからの財務データ・株価データ取得と指標計算を担当。
"""

import logging
from concurrent.futures import ThreadPoolExecutor
from typing import List, Dict, Any, Optional
from datetime import datetime

from mebuki.api.jquants_client import JQuantsAPIClient
from mebuki.utils.financial_data import extract_annual_data
from mebuki.analysis.calculator import calculate_metrics_flexible
from mebuki.constants.formats import DATE_LEN_COMPACT
from mebuki.utils.fiscal_year import normalize_date_format, parse_date_string

logger = logging.getLogger(__name__)


class FinancialFetcher:
    """J-QUANTSからの財務データ・株価データ取得と指標計算"""

    def __init__(self, api_client: JQuantsAPIClient):
        self.api_client = api_client

    def fetch_financial_data(
        self,
        code: str,
        include_2q: bool = False,
    ) -> tuple[Optional[Dict[str, Any]], Optional[List[Dict[str, Any]]], Optional[List[Dict[str, Any]]]]:
        """財務データを取得"""
        with ThreadPoolExecutor(max_workers=2) as executor:
            master_future = executor.submit(self.api_client.get_equity_master, code=code)
            financial_future = executor.submit(
                self.api_client.get_financial_summary,
                code=code,
                period_types=["FY", "2Q"],
                include_fields=None,
            )
            master_data = master_future.result()
            financial_data = financial_future.result()

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

    def fetch_prices(
        self,
        code: str,
        annual_data: List[Dict[str, Any]],
        analysis_years: int,
    ) -> Dict[str, float]:
        """年度末株価を取得"""
        prices = {}
        subscription_start_date = datetime(2021, 1, 9)
        dates_to_fetch = []
        date_to_fy_end = {}

        fy_count = 0
        for year_data in annual_data:
            if fy_count >= analysis_years:
                break
            fy_end = year_data.get("CurFYEn")
            if fy_end:
                fy_end_formatted = normalize_date_format(fy_end) or fy_end
                try:
                    fy_end_date = parse_date_string(fy_end)
                    if fy_end_date and fy_end_date < subscription_start_date:
                        if year_data.get("CurPerType") == "FY":
                            fy_count += 1
                        continue

                    dates_to_fetch.append(fy_end_formatted)
                    date_to_fy_end[fy_end_formatted] = fy_end
                except (ValueError, TypeError):
                    pass
            if year_data.get("CurPerType") == "FY":
                fy_count += 1

        if dates_to_fetch:
            try:
                batch_prices = self.api_client.get_prices_at_dates(
                    code, dates_to_fetch, use_nearest_trading_day=True
                )
                for date_str, price in batch_prices.items():
                    if price is not None:
                        prices[date_str] = price
                        original = date_to_fy_end.get(date_str)
                        if original:
                            prices[original] = price
            except Exception as e:
                logger.warning(f"バッチ株価取得に失敗、個別取得にフォールバック: {e}")
                for date_str in dates_to_fetch:
                    try:
                        price = self.api_client.get_price_at_date(
                            code, date_str, use_nearest_trading_day=True
                        )
                        if price:
                            prices[date_str] = price
                    except Exception as e:
                        logger.warning(f"株価個別取得に失敗: {e}")

        return prices

    def calculate_metrics(
        self,
        code: str,
        annual_data: List[Dict[str, Any]],
        prices: Dict[str, float],
        analysis_years: int,
    ) -> Optional[Dict[str, Any]]:
        """指標を計算"""
        try:
            return calculate_metrics_flexible(annual_data, prices, analysis_years)
        except Exception as e:
            logger.error(f"銘柄コード {code}: 指標計算中にエラーが発生しました - {e}", exc_info=True)
            return None
