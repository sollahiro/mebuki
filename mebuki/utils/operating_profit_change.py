"""
営業利益前年差の要因分解ユーティリティ。

売上高、売上総利益、営業利益から販管費を導出し、営業利益の前年差を
売上差・粗利率差・販管費増の3要素へ分解する。
"""

from typing import Any, cast

from mebuki.constants.financial import MILLION_YEN
from mebuki.utils.metrics_types import YearEntry


_SGA_KEY = "SellingGeneralAdministrativeExpenses"
_OP_CHANGE_KEY = "OperatingProfitChange"
_SALES_IMPACT_KEY = "SalesChangeImpact"
_GM_IMPACT_KEY = "GrossMarginChangeImpact"
_SGA_IMPACT_KEY = "SGAChangeImpact"
_RECONCILIATION_DIFF_KEY = "OperatingProfitChangeReconciliationDiff"


def _gross_margin(gross_profit: float | None, sales: float | None) -> float | None:
    if gross_profit is None or sales is None or sales == 0:
        return None
    return gross_profit / sales


def _set_source(
    data: dict[str, Any],
    metric: str,
    *,
    method: str,
    unit: str = "million_yen",
) -> None:
    sources = data.setdefault("MetricSources", {})
    sources[metric] = {"source": "derived", "method": method, "unit": unit}


def _apply_sga(data: dict[str, Any]) -> None:
    gross_profit = data.get("GrossProfit")
    op = data.get("OP")
    if gross_profit is None or op is None:
        return

    data[_SGA_KEY] = gross_profit - op
    _set_source(data, _SGA_KEY, method="GrossProfit - OP")


def _apply_change(current: dict[str, Any], prior: dict[str, Any]) -> None:
    current_sales = current.get("Sales")
    current_gross_profit = current.get("GrossProfit")
    current_op = current.get("OP")
    current_sga = current.get(_SGA_KEY)
    prior_sales = prior.get("Sales")
    prior_gross_profit = prior.get("GrossProfit")
    prior_op = prior.get("OP")
    prior_sga = prior.get(_SGA_KEY)

    current_margin = _gross_margin(current_gross_profit, current_sales)
    prior_margin = _gross_margin(prior_gross_profit, prior_sales)

    if (
        current_sales is None
        or current_op is None
        or current_sga is None
        or current_margin is None
        or prior_sales is None
        or prior_op is None
        or prior_sga is None
        or prior_margin is None
    ):
        return

    op_change = current_op - prior_op
    sales_impact = (current_sales - prior_sales) * prior_margin
    gross_margin_impact = current_sales * (current_margin - prior_margin)
    sga_impact = -(current_sga - prior_sga)
    total_impact = sales_impact + gross_margin_impact + sga_impact

    current[_OP_CHANGE_KEY] = op_change
    current[_SALES_IMPACT_KEY] = sales_impact
    current[_GM_IMPACT_KEY] = gross_margin_impact
    current[_SGA_IMPACT_KEY] = sga_impact
    current[_RECONCILIATION_DIFF_KEY] = op_change - total_impact

    _set_source(current, _OP_CHANGE_KEY, method="current OP - prior OP")
    _set_source(
        current,
        _SALES_IMPACT_KEY,
        method="(current Sales - prior Sales) * prior GrossProfitMargin",
    )
    _set_source(
        current,
        _GM_IMPACT_KEY,
        method="current Sales * (current GrossProfitMargin - prior GrossProfitMargin)",
    )
    _set_source(current, _SGA_IMPACT_KEY, method="-(current SGA - prior SGA)")
    _set_source(
        current,
        _RECONCILIATION_DIFF_KEY,
        method="OperatingProfitChange - (SalesChangeImpact + GrossMarginChangeImpact + SGAChangeImpact)",
    )


def apply_operating_profit_change_to_years(years: list[YearEntry]) -> None:
    """年次データへ営業利益前年差分解を付与する。"""
    for year in years:
        _apply_sga(cast(dict[str, Any], year["CalculatedData"]))

    chronological = sorted(
        years,
        key=lambda year: str(year.get("fy_end") or ""),
    )
    for prior, current in zip(chronological, chronological[1:]):
        _apply_change(
            cast(dict[str, Any], current["CalculatedData"]),
            cast(dict[str, Any], prior["CalculatedData"]),
        )


def apply_operating_profit_change_to_periods(periods: list[dict[str, Any]]) -> None:
    """H1/H2/FY 期間データへ前年同期間比の営業利益前年差分解を付与する。"""
    latest_by_half: dict[str, dict[str, Any]] = {}

    for period in sorted(periods, key=lambda item: str(item.get("fy_end") or "")):
        data = period.get("data") or {}
        _apply_sga(data)

        half = period.get("half")
        comparison_key = half if isinstance(half, str) else "FY"
        prior = latest_by_half.get(comparison_key)
        if prior is not None:
            _apply_change(data, prior.get("data") or {})
        latest_by_half[comparison_key] = period


def apply_operating_profit_change_from_xbrl(
    years: list[YearEntry],
    gp_by_year: dict[str, dict[str, Any]],
    op_by_year: dict[str, dict[str, Any]],
) -> None:
    """有報XBRLの前期比較値を使って営業利益前年差分解を付与する。

    各年度の有報に含まれる前期数値（Prior1YearDuration コンテキスト）を使うため、
    J-QUANTSデータと前年リストへの依存なしに全年度の前年差を計算できる。
    gp_by_year / op_by_year は YYYYMMDD キーの XBRL 抽出結果 dict。
    """
    for year in years:
        fy_end = year.get("fy_end") or ""
        fy_end_key = fy_end.replace("-", "")

        gp = gp_by_year.get(fy_end_key, {})
        op = op_by_year.get(fy_end_key, {})

        current_gp_raw = gp.get("current")
        current_op_raw = op.get("current")
        current_sales_raw = gp.get("current_sales")

        prior_gp_raw = gp.get("prior")
        prior_op_raw = op.get("prior")
        prior_sales_raw = gp.get("prior_sales")

        cd = cast(dict[str, Any], year["CalculatedData"])

        if current_gp_raw is not None and current_op_raw is not None:
            current_gp_m = current_gp_raw / MILLION_YEN
            current_op_m = current_op_raw / MILLION_YEN
            if cd.get(_SGA_KEY) is None:
                cd[_SGA_KEY] = current_gp_m - current_op_m
                _set_source(cd, _SGA_KEY, method="GrossProfit(XBRL) - OP(XBRL)")
        else:
            current_gp_m = current_op_m = None

        if (
            current_gp_m is None
            or current_op_m is None
            or current_sales_raw is None
            or prior_gp_raw is None
            or prior_op_raw is None
            or prior_sales_raw is None
        ):
            continue

        current_sales = current_sales_raw / MILLION_YEN
        prior_gp = prior_gp_raw / MILLION_YEN
        prior_op = prior_op_raw / MILLION_YEN
        prior_sales = prior_sales_raw / MILLION_YEN

        if prior_sales == 0 or current_sales == 0:
            continue

        current_sga = current_gp_m - current_op_m
        prior_sga = prior_gp - prior_op
        current_margin = current_gp_m / current_sales
        prior_margin = prior_gp / prior_sales

        op_change = current_op_m - prior_op
        sales_impact = (current_sales - prior_sales) * prior_margin
        gm_impact = current_sales * (current_margin - prior_margin)
        sga_impact = -(current_sga - prior_sga)
        total_impact = sales_impact + gm_impact + sga_impact

        cd[_OP_CHANGE_KEY] = op_change
        cd[_SALES_IMPACT_KEY] = sales_impact
        cd[_GM_IMPACT_KEY] = gm_impact
        cd[_SGA_IMPACT_KEY] = sga_impact
        cd[_RECONCILIATION_DIFF_KEY] = op_change - total_impact

        _set_source(cd, _OP_CHANGE_KEY, method="current OP - prior OP (XBRL)")
        _set_source(
            cd,
            _SALES_IMPACT_KEY,
            method="(current Sales - prior Sales) * prior GrossProfitMargin (XBRL)",
        )
        _set_source(
            cd,
            _GM_IMPACT_KEY,
            method="current Sales * (current GrossProfitMargin - prior GrossProfitMargin) (XBRL)",
        )
        _set_source(cd, _SGA_IMPACT_KEY, method="-(current SGA - prior SGA) (XBRL)")
        _set_source(
            cd,
            _RECONCILIATION_DIFF_KEY,
            method="OperatingProfitChange - (SalesChangeImpact + GrossMarginChangeImpact + SGAChangeImpact) (XBRL)",
        )
