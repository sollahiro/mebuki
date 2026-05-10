"""
IFRS純収益・事業利益 XBRL抽出モジュール

IFRS適用の金融会社（クレディセゾン等）で売上高・営業利益タグが
空になる場合に、XBRL から純収益（NetRevenueIFRS）と事業利益
（BusinessProfitIFRSSummaryOfBusinessResults）を抽出してフォールバックに使う。
"""
from pathlib import Path

from blue_ticker.analysis.field_parser import (
    field_set_from_pre_parsed_duration,
    parse_duration_fields,
    resolve_item,
)
from blue_ticker.utils.xbrl_result_types import NetRevenueResult, XbrlTagElements

_NET_REVENUE_TAGS: frozenset[str] = frozenset([
    "NetRevenueIFRS",
    "BusinessProfitIFRSSummaryOfBusinessResults",
])


def extract_net_revenue(
    xbrl_dir: Path,
    *,
    pre_parsed: XbrlTagElements | None = None,
) -> NetRevenueResult:
    """
    XBRLディレクトリから IFRS 純収益と事業利益を抽出する。

    Returns:
        {
            "net_revenue":           float | None,  # 純収益・当期（円）
            "net_revenue_prior":     float | None,  # 純収益・前期（円）
            "business_profit":       float | None,  # 事業利益・当期（円）
            "business_profit_prior": float | None,  # 事業利益・前期（円）
            "found": bool,
        }
    """
    field_set = (
        field_set_from_pre_parsed_duration(pre_parsed)
        if pre_parsed is not None
        else parse_duration_fields(xbrl_dir, allowed_tags=_NET_REVENUE_TAGS)
    )

    nr_item = resolve_item(field_set, ["NetRevenueIFRS"])
    bp_item = resolve_item(field_set, ["BusinessProfitIFRSSummaryOfBusinessResults"])

    return {
        "net_revenue": nr_item["current"],
        "net_revenue_prior": nr_item["prior"],
        "business_profit": bp_item["current"],
        "business_profit_prior": bp_item["prior"],
        "found": nr_item["current"] is not None or bp_item["current"] is not None,
    }
