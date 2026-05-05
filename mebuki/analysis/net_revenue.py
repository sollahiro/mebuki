"""
IFRS純収益・事業利益 XBRL抽出モジュール

IFRS適用の金融会社（クレディセゾン等）で売上高・営業利益タグが
空になる場合に、XBRL から純収益（NetRevenueIFRS）と事業利益
（BusinessProfitIFRSSummaryOfBusinessResults）を抽出してフォールバックに使う。
"""
from pathlib import Path

from mebuki.analysis.xbrl_utils import collect_numeric_elements, find_xbrl_files
from mebuki.utils.xbrl_result_types import NetRevenueResult, XbrlTagElements

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
    if pre_parsed is not None:
        tag_elements: XbrlTagElements = {
            tag: ctx for tag, ctx in pre_parsed.items() if tag in _NET_REVENUE_TAGS
        }
    else:
        tag_elements = {}
        for f in find_xbrl_files(xbrl_dir):
            for tag, ctx_map in collect_numeric_elements(f, allowed_tags=_NET_REVENUE_TAGS).items():
                if tag not in tag_elements:
                    tag_elements[tag] = {}
                tag_elements[tag].update(ctx_map)

    def _get(tag: str, patterns: list[str]) -> float | None:
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
