"""
出力境界での JSON 整形ユーティリティ。

内部の CalculatedData には計算追跡・デバッグ用フィールドが含まれるが、
MCP / CLI の標準 JSON 出力にはトークン効率・可読性のためこれらを除外する。
include_debug_fields=True を渡すと全フィールドを含む。
"""

from typing import Any

_DEBUG_FIELDS: frozenset[str] = frozenset({
    "MetricSources",
    "IBDComponents",
    "GrossProfitMethod",
    "IBDAccountingStandard",
    "BalanceSheetComponents",
    "BalanceSheetAccountingStandard",
    "OperatingProfitChangeReconciliationDiff",
})

_REDUNDANT_SUMMARY_FIELDS: frozenset[str] = frozenset({
    "latest_fcf",
    "latest_roe",
    "latest_eps",
    "latest_sales",
})


def _strip_debug(cd: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in cd.items() if k not in _DEBUG_FIELDS}


def _strip_redundant_summary(metrics: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in metrics.items() if k not in _REDUNDANT_SUMMARY_FIELDS}


def serialize_metrics_result(
    metrics: dict[str, Any],
    *,
    include_debug_fields: bool = False,
) -> dict[str, Any]:
    """MetricsResult の各 YearEntry.CalculatedData からデバッグフィールドを除去する。"""
    if include_debug_fields:
        return metrics
    metrics = _strip_redundant_summary(metrics)
    years = metrics.get("years")
    if not years:
        return metrics
    result = dict(metrics)
    result["years"] = [
        {**entry, "CalculatedData": _strip_debug(entry.get("CalculatedData") or {})}
        for entry in years
    ]
    return result


def serialize_half_year_periods(
    periods: list[dict[str, Any]],
    *,
    include_debug_fields: bool = False,
) -> list[dict[str, Any]]:
    """半期データ各エントリの data からデバッグフィールドを除去する。"""
    if include_debug_fields:
        return periods
    return [
        {**p, "data": _strip_debug(p.get("data") or {})}
        for p in periods
    ]
