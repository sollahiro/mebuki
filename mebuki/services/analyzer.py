"""
個別詳細分析モジュール

個別銘柄の詳細分析を実行します。
FinancialFetcher / EdinetFetcher を組み合わせてオーケストレーションします。
"""

import logging
import asyncio
from typing import Any, cast
from pathlib import Path
from collections.abc import Callable

from mebuki.api.jquants_client import JQuantsAPIClient
from mebuki.api.edinet_client import EdinetAPIClient
from mebuki.infrastructure.settings import settings_store
from mebuki.constants.financial import PERCENT, MILLION_YEN
from mebuki.utils.cache import CacheManager
from mebuki.utils.wacc import load_rf_rates, get_rf_for_date, calculate_wacc
from mebuki.utils.metrics_types import CalculatedData, MetricSource, YearEntry

from .financial_fetcher import FinancialFetcher
from .edinet_fetcher import EdinetFetcher

logger = logging.getLogger(__name__)


def _fy_end_key(year: YearEntry) -> str:
    fy_end = year.get("fy_end")
    return fy_end.replace("-", "") if fy_end is not None else ""


def _set_metric_source(
    cd: CalculatedData,
    metric: str,
    *,
    source: str,
    unit: str,
    method: str | None = None,
    doc_id: str | None = None,
    label: str | None = None,
) -> None:
    sources = cd.setdefault("MetricSources", {})
    item: MetricSource = {"source": source, "unit": unit}
    if method is not None:
        item["method"] = method
    if doc_id is not None:
        item["docID"] = doc_id
    if label is not None:
        item["label"] = label
    sources[metric] = item


def _apply_ibd(
    years: list[YearEntry],
    ibd_by_year: dict[str, dict[str, Any]],
    doc_id_by_year: dict[str, str],
) -> None:
    for year in years:
        fy_end_key = _fy_end_key(year)
        doc_id = doc_id_by_year.get(fy_end_key)
        cd = year["CalculatedData"]
        if doc_id:
            cd["DocID"] = doc_id
            _set_metric_source(cd, "DocID", source="edinet", unit="id", doc_id=doc_id)
        ibd = ibd_by_year.get(fy_end_key)
        if not ibd or ibd.get("current") is None:
            continue
        ibd_m = ibd["current"] / MILLION_YEN
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
        _set_metric_source(
            cd,
            "InterestBearingDebt",
            source="edinet",
            unit="million_yen",
            method=ibd.get("method"),
            doc_id=doc_id,
            label=ibd.get("accounting_standard"),
        )
        np_ = cd.get("NP")
        eq = cd.get("Eq")
        if np_ is not None and eq is not None and (eq + ibd_m) != 0:
            cd["ROIC"] = np_ / (eq + ibd_m) * PERCENT
            _set_metric_source(cd, "ROIC", source="derived", unit="percent", method="NP / (Eq + InterestBearingDebt)")


def _apply_interest_expense(
    years: list[YearEntry],
    ie_by_year: dict[str, dict[str, Any]],
) -> None:
    for year in years:
        fy_end_key = _fy_end_key(year)
        ie = ie_by_year.get(fy_end_key)
        if ie and ie.get("current") is not None:
            cd = year["CalculatedData"]
            cd["InterestExpense"] = ie["current"] / MILLION_YEN
            _set_metric_source(
                cd,
                "InterestExpense",
                source="edinet",
                unit="million_yen",
                method=ie.get("method"),
                doc_id=ie.get("docID"),
            )


def _apply_tax(
    years: list[YearEntry],
    tax_by_year: dict[str, dict[str, Any]],
) -> None:
    for year in years:
        fy_end_key = _fy_end_key(year)
        tax = tax_by_year.get(fy_end_key)
        if not tax or tax.get("method") not in ("computed", "usgaap_html"):
            continue
        cd = year["CalculatedData"]
        if tax.get("pretax_income") is not None:
            cd["PretaxIncome"] = tax["pretax_income"] / MILLION_YEN
            _set_metric_source(cd, "PretaxIncome", source="edinet", unit="million_yen", method=tax.get("method"), doc_id=tax.get("docID"))
        if tax.get("income_tax") is not None:
            cd["IncomeTax"] = tax["income_tax"] / MILLION_YEN
            _set_metric_source(cd, "IncomeTax", source="edinet", unit="million_yen", method=tax.get("method"), doc_id=tax.get("docID"))
        if tax.get("effective_tax_rate") is not None:
            cd["EffectiveTaxRate"] = tax["effective_tax_rate"] * PERCENT
            _set_metric_source(cd, "EffectiveTaxRate", source="derived", unit="percent", method=tax.get("method"), doc_id=tax.get("docID"))


def _apply_gross_profit(
    years: list[YearEntry],
    gp_by_year: dict[str, dict[str, Any]],
) -> None:
    for year in years:
        fy_end_key = _fy_end_key(year)
        gp = gp_by_year.get(fy_end_key)
        if not gp or gp.get("current") is None:
            continue
        gp_m = gp["current"] / MILLION_YEN
        # Sales の直後に挿入するため dict を再構築
        old_cd = year["CalculatedData"]
        new_cd: dict[str, Any] = {}
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
        cast_cd = cast(CalculatedData, new_cd)
        _set_metric_source(
            cast_cd,
            "GrossProfit",
            source="edinet",
            unit="million_yen",
            method=gp.get("method", "unknown"),
            doc_id=gp.get("docID"),
        )
        _set_metric_source(cast_cd, "GrossProfitMargin", source="derived", unit="percent", method="GrossProfit / Sales")
        year["CalculatedData"] = cast_cd


def _apply_operating_profit(
    years: list[YearEntry],
    op_by_year: dict[str, dict[str, Any]],
) -> None:
    for year in years:
        fy_end_key = _fy_end_key(year)
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
        _set_metric_source(
            cd,
            "OP",
            source="edinet",
            unit="million_yen",
            method=op.get("method"),
            doc_id=op.get("docID"),
            label=op.get("label"),
        )
        sales = cd.get("Sales")
        if sales:
            cd["OperatingMargin"] = op_m / sales * PERCENT
            _set_metric_source(cd, "OperatingMargin", source="derived", unit="percent", method="OP / Sales")


def _apply_net_revenue(
    years: list[YearEntry],
    nr_by_year: dict[str, dict[str, Any]],
) -> None:
    for year in years:
        fy_end_key = _fy_end_key(year)
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
            _set_metric_source(cd, "Sales", source="edinet", unit="million_yen", method=nr.get("method"), doc_id=nr.get("docID"), label="純収益")
            # GrossProfitMargin を Sales 確定後に再計算
            gp = cd.get("GrossProfit")
            if gp is not None:
                cd["GrossProfitMargin"] = gp / nr_m * PERCENT
                _set_metric_source(cd, "GrossProfitMargin", source="derived", unit="percent", method="GrossProfit / Sales")
        if cd.get("OP") is None and nr.get("business_profit") is not None:
            bp_m = nr["business_profit"] / MILLION_YEN
            cd["OP"] = bp_m
            rd["OP"] = nr["business_profit"]
            cd["OPLabel"] = "事業利益"
            _set_metric_source(cd, "OP", source="edinet", unit="million_yen", method=nr.get("method"), doc_id=nr.get("docID"), label="事業利益")
            sales = cd.get("Sales")
            if sales:
                cd["OperatingMargin"] = bp_m / sales * PERCENT
                _set_metric_source(cd, "OperatingMargin", source="derived", unit="percent", method="OP / Sales")


def _apply_employees(
    years: list[YearEntry],
    emp_by_year: dict[str, dict[str, Any]],
) -> None:
    for year in years:
        fy_end_key = _fy_end_key(year)
        emp = emp_by_year.get(fy_end_key)
        if emp and emp.get("current") is not None:
            cd = year["CalculatedData"]
            cd["Employees"] = emp["current"]
            _set_metric_source(cd, "Employees", source="edinet", unit="persons", method=emp.get("method"), doc_id=emp.get("docID"), label=emp.get("scope"))


_METRIC_APPLIERS: list[Callable[[list[YearEntry], dict[str, dict[str, Any]]], None]] = [
    lambda years, m: _apply_ibd(years, m.get("ibd", {}), m.get("doc_ids", {})),
    lambda years, m: _apply_interest_expense(years, m.get("ie", {})),
    lambda years, m: _apply_tax(years, m.get("tax", {})),
    lambda years, m: _apply_gross_profit(years, m.get("gp", {})),
    lambda years, m: _apply_operating_profit(years, m.get("op", {})),
    lambda years, m: _apply_net_revenue(years, m.get("nr", {})),
    lambda years, m: _apply_employees(years, m.get("emp", {})),
]


def _apply_wacc(years: list[YearEntry], rf_rates: dict[str, float]) -> None:
    for year in years:
        cd = year["CalculatedData"]
        fy_end = year.get("fy_end") or ""
        rf = get_rf_for_date(rf_rates, fy_end)
        wacc = calculate_wacc(
            eq=cd.get("Eq"),
            ibd=cd.get("InterestBearingDebt"),
            ie=cd.get("InterestExpense"),
            tc_pct=cd.get("EffectiveTaxRate"),
            rf=rf,
        )
        cost_of_equity = wacc["CostOfEquity"]
        cost_of_debt = wacc["CostOfDebt"]
        wacc_value = wacc["WACC"]
        wacc_label = wacc["WACCLabel"]
        cd["CostOfEquity"] = cost_of_equity if isinstance(cost_of_equity, float) else None
        cd["CostOfDebt"] = cost_of_debt if isinstance(cost_of_debt, float) else None
        cd["WACC"] = wacc_value if isinstance(wacc_value, float) else None
        cd["WACCLabel"] = wacc_label if isinstance(wacc_label, str) else None
        _set_metric_source(cd, "CostOfEquity", source="mof", unit="percent", method="Rf + beta * MRP")
        _set_metric_source(cd, "CostOfDebt", source="derived", unit="percent", method="InterestExpense / InterestBearingDebt")
        _set_metric_source(cd, "WACC", source="derived", unit="percent", method="weighted average cost of capital")


class IndividualAnalyzer:
    """個別詳細分析クラス"""

    def __init__(
        self,
        api_client: JQuantsAPIClient | None = None,
        edinet_client: EdinetAPIClient | None = None,
        cache_manager: CacheManager | None = None,
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

        if cache_manager is None:
            cache_manager = CacheManager(
                cache_dir=str(settings_store.cache_dir),
                enabled=settings_store.cache_enabled,
            )
        self._cache_manager = cache_manager

        self._financial_fetcher = FinancialFetcher(self.api_client)
        self._edinet_fetcher = EdinetFetcher(
            self.api_client,
            self.edinet_client,
            cache_manager=self._cache_manager,
        )

    async def fetch_analysis_data(
        self,
        code: str,
        analysis_years: int | None = None,
        max_documents: int = 10,
        include_2q: bool = False,
        prefetched_stock_info: dict[str, Any] | None = None,
        prefetched_financial_data: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """財務指標 + EDINETデータを取得する公開API（use_cache=False）。

        data_service などの上位層が private メソッドを直接呼ばずに済むよう提供する。
        """
        if prefetched_stock_info is not None and prefetched_financial_data is not None:
            from mebuki.utils.financial_data import extract_annual_data

            stock_info = prefetched_stock_info
            financial_data = prefetched_financial_data
            try:
                annual_data = extract_annual_data(financial_data, include_2q=include_2q)
            except Exception as e:
                logger.error(f"銘柄コード {code}: 年度データ抽出中にエラーが発生しました - {e}", exc_info=True)
                return {}
            if not annual_data:
                return {}
        else:
            stock_info, financial_data, annual_data = await self._financial_fetcher.fetch_financial_data(code, include_2q)
            if not stock_info or not annual_data:
                return {}

        available_years = sum(1 for d in annual_data if d.get("CurPerType") == "FY")
        actual_years = min(available_years, analysis_years) if analysis_years else available_years

        metrics = await self._financial_fetcher.calculate_metrics(code, annual_data, actual_years)
        if not metrics:
            return {}

        edinet_data: dict[str, Any] = {}
        all_metrics: dict[str, dict[str, Any]] = {}

        if financial_data:
            pre_parsed_map, edinet_data = await asyncio.gather(
                self._edinet_fetcher.predownload_and_parse(code, financial_data, actual_years),
                self._edinet_fetcher.fetch_edinet_data_async(code, financial_data, max_documents=max_documents),
            )
            all_metrics = await self._edinet_fetcher.extract_all_by_year(
                code, financial_data, actual_years, pre_parsed_map=pre_parsed_map
            )

        years: list[YearEntry] = metrics.get("years", [])

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
