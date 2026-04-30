"""
個別詳細分析モジュール

個別銘柄の詳細分析を実行します。
FinancialFetcher / EdinetFetcher を組み合わせてオーケストレーションします。
"""

import logging
import asyncio
from typing import Any
from pathlib import Path
from collections.abc import Callable

from mebuki.api.jquants_client import JQuantsAPIClient
from mebuki.api.edinet_client import EdinetAPIClient
from mebuki.infrastructure.settings import settings_store
from mebuki.constants.financial import PERCENT, MILLION_YEN
from mebuki.utils.wacc import load_rf_rates, get_rf_for_date, calculate_wacc
from mebuki.utils.metrics_types import YearEntry

from .financial_fetcher import FinancialFetcher
from .edinet_fetcher import EdinetFetcher

logger = logging.getLogger(__name__)


def _apply_ibd(
    years: list[YearEntry],
    ibd_by_year: dict[str, dict],
    doc_id_by_year: dict[str, str],
) -> None:
    for year in years:
        fy_end_key = year.get("fy_end", "").replace("-", "")
        doc_id = doc_id_by_year.get(fy_end_key)
        if doc_id:
            year["CalculatedData"]["IBDDocID"] = doc_id
        ibd = ibd_by_year.get(fy_end_key)
        if not ibd or ibd.get("current") is None:
            continue
        ibd_m = ibd["current"] / MILLION_YEN
        cd = year["CalculatedData"]
        cd["InterestBearingDebt"] = ibd_m
        cd["IBDComponents"] = [
            {
                "label": c["label"],
                "current": c["current"] / MILLION_YEN if c["current"] is not None else None,
                "prior": c["prior"] / MILLION_YEN if c["prior"] is not None else None,
            }
            for c in ibd.get("components", [])
        ]
        cd["IBDAccountingStandard"] = ibd.get("accounting_standard", "unknown")
        np_ = cd.get("NP")
        eq = cd.get("Eq")
        if np_ is not None and eq is not None and (eq + ibd_m) != 0:
            cd["ROIC"] = np_ / (eq + ibd_m) * PERCENT


def _apply_interest_expense(
    years: list[YearEntry],
    ie_by_year: dict[str, dict],
) -> None:
    for year in years:
        fy_end_key = year.get("fy_end", "").replace("-", "")
        ie = ie_by_year.get(fy_end_key)
        if ie and ie.get("current") is not None:
            year["CalculatedData"]["InterestExpense"] = ie["current"] / MILLION_YEN


def _apply_tax(
    years: list[YearEntry],
    tax_by_year: dict[str, dict],
) -> None:
    for year in years:
        fy_end_key = year.get("fy_end", "").replace("-", "")
        tax = tax_by_year.get(fy_end_key)
        if not tax or tax.get("method") not in ("computed", "usgaap_html"):
            continue
        cd = year["CalculatedData"]
        if tax.get("pretax_income") is not None:
            cd["PretaxIncome"] = tax["pretax_income"] / MILLION_YEN
        if tax.get("income_tax") is not None:
            cd["IncomeTax"] = tax["income_tax"] / MILLION_YEN
        if tax.get("effective_tax_rate") is not None:
            cd["EffectiveTaxRate"] = tax["effective_tax_rate"] * PERCENT


def _apply_gross_profit(
    years: list[YearEntry],
    gp_by_year: dict[str, dict],
) -> None:
    for year in years:
        fy_end_key = year.get("fy_end", "").replace("-", "")
        gp = gp_by_year.get(fy_end_key)
        if not gp or gp.get("current") is None:
            continue
        gp_m = gp["current"] / MILLION_YEN
        # Sales の直後に挿入するため dict を再構築
        old_cd = year["CalculatedData"]
        new_cd: dict = {}
        for k, v in old_cd.items():
            new_cd[k] = v
            if k == "Sales":
                new_cd["GrossProfit"] = gp_m
                new_cd["GrossProfitMethod"] = gp.get("method", "unknown")
                new_cd["GrossProfitMargin"] = gp_m / v * PERCENT if v else None
        if "GrossProfit" not in new_cd:
            new_cd["GrossProfit"] = gp_m
            new_cd["GrossProfitMethod"] = gp.get("method", "unknown")
            sales = new_cd.get("Sales")
            new_cd["GrossProfitMargin"] = gp_m / sales * PERCENT if sales else None
        year["CalculatedData"] = new_cd


def _apply_operating_profit(
    years: list[YearEntry],
    op_by_year: dict[str, dict],
) -> None:
    for year in years:
        fy_end_key = year.get("fy_end", "").replace("-", "")
        op = op_by_year.get(fy_end_key)
        if not op or op.get("current") is None:
            continue
        cd = year["CalculatedData"]
        if cd.get("OP") is not None:
            continue
        op_m = op["current"] / MILLION_YEN
        cd["OP"] = op_m
        if op.get("label") == "経常利益":
            cd["OPLabel"] = "経常利益"
        sales = cd.get("Sales")
        if sales:
            cd["OperatingMargin"] = op_m / sales * PERCENT


def _apply_net_revenue(
    years: list[YearEntry],
    nr_by_year: dict[str, dict],
) -> None:
    for year in years:
        fy_end_key = year.get("fy_end", "").replace("-", "")
        nr = nr_by_year.get(fy_end_key)
        if not nr or not nr.get("found"):
            continue
        cd = year["CalculatedData"]
        rd = year["RawData"]
        if cd.get("Sales") is None and nr.get("net_revenue") is not None:
            nr_m = nr["net_revenue"] / MILLION_YEN
            cd["Sales"] = nr_m
            rd["Sales"] = nr["net_revenue"]
            cd["SalesLabel"] = "純収益"
            # GrossProfitMargin を Sales 確定後に再計算
            gp = cd.get("GrossProfit")
            if gp is not None:
                cd["GrossProfitMargin"] = gp / nr_m * PERCENT
        if cd.get("OP") is None and nr.get("business_profit") is not None:
            bp_m = nr["business_profit"] / MILLION_YEN
            cd["OP"] = bp_m
            rd["OP"] = nr["business_profit"]
            cd["OPLabel"] = "事業利益"
            sales = cd.get("Sales")
            if sales:
                cd["OperatingMargin"] = bp_m / sales * PERCENT


def _apply_employees(
    years: list[YearEntry],
    emp_by_year: dict[str, dict],
) -> None:
    for year in years:
        fy_end_key = year.get("fy_end", "").replace("-", "")
        emp = emp_by_year.get(fy_end_key)
        if emp and emp.get("current") is not None:
            year["CalculatedData"]["Employees"] = emp["current"]


_METRIC_APPLIERS: list[Callable[[list[YearEntry], dict], None]] = [
    lambda years, m: _apply_ibd(years, m.get("ibd", {}), m.get("doc_ids", {})),
    lambda years, m: _apply_interest_expense(years, m.get("ie", {})),
    lambda years, m: _apply_tax(years, m.get("tax", {})),
    lambda years, m: _apply_gross_profit(years, m.get("gp", {})),
    lambda years, m: _apply_operating_profit(years, m.get("op", {})),
    lambda years, m: _apply_net_revenue(years, m.get("nr", {})),
    lambda years, m: _apply_employees(years, m.get("emp", {})),
]


def _apply_wacc(years: list[YearEntry], rf_rates: dict) -> None:
    for year in years:
        cd = year["CalculatedData"]
        rf = get_rf_for_date(rf_rates, year.get("fy_end", ""))
        cd.update(calculate_wacc(
            eq=cd.get("Eq"),
            ibd=cd.get("InterestBearingDebt"),
            ie=cd.get("InterestExpense"),
            tc_pct=cd.get("EffectiveTaxRate"),
            rf=rf,
        ))


class IndividualAnalyzer:
    """個別詳細分析クラス"""

    def __init__(
        self,
        api_client: JQuantsAPIClient | None = None,
        edinet_client: EdinetAPIClient | None = None,
    ):
        self.api_client = api_client or JQuantsAPIClient(api_key=settings_store.jquants_api_key)

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
    ) -> dict[str, Any]:
        """財務指標 + EDINETデータを取得する公開API（use_cache=False）。

        data_service などの上位層が private メソッドを直接呼ばずに済むよう提供する。
        """
        stock_info, financial_data, annual_data = await self._financial_fetcher.fetch_financial_data(code, include_2q)
        if not stock_info or not annual_data:
            return {}

        available_years = sum(1 for d in annual_data if d.get("CurPerType") == "FY")
        actual_years = min(available_years, analysis_years) if analysis_years else available_years

        metrics = await self._financial_fetcher.calculate_metrics(code, annual_data, actual_years)

        edinet_data: dict = {}
        all_metrics: dict[str, dict[str, dict]] = {}

        if financial_data:
            pre_parsed_map = await self._edinet_fetcher.predownload_and_parse(
                code, financial_data, actual_years
            )
            edinet_data, all_metrics = await asyncio.gather(
                self._edinet_fetcher.fetch_edinet_data_async(code, financial_data, max_documents=max_documents),
                self._edinet_fetcher.extract_all_by_year(code, financial_data, actual_years, pre_parsed_map=pre_parsed_map),
            )

        years = metrics.get("years", [])

        for apply_fn in _METRIC_APPLIERS:
            apply_fn(years, all_metrics)

        _apply_wacc(years, load_rf_rates(settings_store.cache_dir))

        return {
            "stock_info": stock_info,
            "financial_data": financial_data,
            "annual_data": annual_data,
            "metrics": metrics,
            "edinet_data": edinet_data,
        }


# 互換性維持
# パターン評価関数は patterns.py に移動済み
