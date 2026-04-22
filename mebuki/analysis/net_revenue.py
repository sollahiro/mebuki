"""
IFRS純収益・事業利益 XBRL抽出モジュール

IFRS適用の金融会社（クレディセゾン等）は J-QUANTS の Sales/OP フィールドが
空になるため、XBRL から純収益（NetRevenueIFRS）と事業利益
（BusinessProfitIFRSSummaryOfBusinessResults）を抽出してフォールバックに使う。
"""
from pathlib import Path
from typing import Optional

from mebuki.analysis.xbrl_utils import collect_numeric_elements, find_xbrl_files

_NET_REVENUE_TAGS: frozenset[str] = frozenset([
    "NetRevenueIFRS",
    "BusinessProfitIFRSSummaryOfBusinessResults",
])

_CURRENT_PATTERNS = [
    "CurrentYearDuration",
    "FilingDateDuration",
]

_PRIOR_PATTERNS = [
    "Prior1YearDuration",
]


def _is_target_ctx(ctx: str, patterns: list[str]) -> bool:
    return (
        any(p in ctx for p in patterns)
        and "_NonConsolidated" not in ctx
        and "Member" not in ctx
    )


def extract_net_revenue(xbrl_dir: Path) -> dict:
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
    tag_elements: dict = {}
    for f in find_xbrl_files(xbrl_dir):
        for tag, ctx_map in collect_numeric_elements(f, allowed_tags=_NET_REVENUE_TAGS).items():
            if tag not in tag_elements:
                tag_elements[tag] = {}
            tag_elements[tag].update(ctx_map)

    def _get(tag: str, patterns: list[str]) -> Optional[float]:
        for ctx, val in tag_elements.get(tag, {}).items():
            if _is_target_ctx(ctx, patterns):
                return val
        return None

    nr_cur = _get("NetRevenueIFRS", _CURRENT_PATTERNS)
    nr_prior = _get("NetRevenueIFRS", _PRIOR_PATTERNS)
    bp_cur = _get("BusinessProfitIFRSSummaryOfBusinessResults", _CURRENT_PATTERNS)
    bp_prior = _get("BusinessProfitIFRSSummaryOfBusinessResults", _PRIOR_PATTERNS)

    return {
        "net_revenue": nr_cur,
        "net_revenue_prior": nr_prior,
        "business_profit": bp_cur,
        "business_profit_prior": bp_prior,
        "found": nr_cur is not None or bp_cur is not None,
    }
