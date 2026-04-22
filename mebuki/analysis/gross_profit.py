"""
売上総利益 XBRL抽出モジュール

XBRLインスタンス文書から連結損益計算書の売上総利益を抽出する。

定義:
  売上総利益 = 売上高 − 売上原価

タグ体系:
  J-GAAP:   GrossProfit（直接）/ NetSales − CostOfSales（計算）
  IFRS連結:  GrossProfit（直接）/ Revenue − CostOfSales（計算）
  US-GAAP:  GrossProfit（直接）/ Revenues − CostOfRevenue（計算）

抽出戦略:
  1. 直接法: GrossProfit タグを検索
  2. 計算法: 売上高タグ − 売上原価タグ で算出（フォールバック）

コンテキスト:
  損益計算書はフロー項目なので Duration コンテキストを使用する。
  （貸借対照表の Instant コンテキストとは異なる点に注意）
"""

from pathlib import Path
from typing import Any, Dict, Optional

from mebuki.analysis.xbrl_utils import parse_xbrl_value, collect_numeric_elements, find_xbrl_files
from mebuki.constants.xbrl import (
    GROSS_PROFIT_DIRECT_TAGS,
    GROSS_PROFIT_COMPONENT_DEFINITIONS,
)

# XBRL解析で収集対象とするローカルタグ名のセット
_GP_RELEVANT_TAGS: frozenset[str] = frozenset(
    GROSS_PROFIT_DIRECT_TAGS
    + [tag for comp in GROSS_PROFIT_COMPONENT_DEFINITIONS for tag in comp["tags"]]
    + [
        # 会計基準判定用マーカー（IBDモジュールと同一セット）
        "TotalAssetsUSGAAPSummaryOfBusinessResults",
        "EquityAttributableToOwnersOfParentUSGAAPSummaryOfBusinessResults",
        "InterestBearingLiabilitiesCLIFRS",
        "BorrowingsCLIFRS",
        "BondsPayableNCLIFRS",
        "BorrowingsNCLIFRS",
    ]
)

# 損益計算書（Duration）コンテキストパターン
# 年次: CurrentYearDuration / 新形式半期: InterimDuration / 旧形式半期・四半期: CurrentYTDDuration
DURATION_CONTEXT_PATTERNS = [
    "CurrentYearDuration",
    "FilingDateDuration",
    "InterimDuration",
    "CurrentYTDDuration",
]

PRIOR_DURATION_CONTEXT_PATTERNS = [
    "Prior1YearDuration",
    "PriorYearDuration",
    "Prior1InterimDuration",
    "Prior1YTDDuration",
]


def _is_consolidated_duration(ctx: str) -> bool:
    """連結の当期損益コンテキストかどうか。"""
    return (
        any(p in ctx for p in DURATION_CONTEXT_PATTERNS)
        and "_NonConsolidated" not in ctx
    )


def _is_consolidated_prior_duration(ctx: str) -> bool:
    """連結の前期損益コンテキストかどうか。"""
    return (
        any(p in ctx for p in PRIOR_DURATION_CONTEXT_PATTERNS)
        and "_NonConsolidated" not in ctx
    )


def _is_nonconsolidated_duration(ctx: str) -> bool:
    """個別の当期損益コンテキストかどうか。"""
    return (
        any(p in ctx for p in DURATION_CONTEXT_PATTERNS)
        and "_NonConsolidated" in ctx
    )


def _is_nonconsolidated_prior_duration(ctx: str) -> bool:
    """個別の前期損益コンテキストかどうか。"""
    return (
        any(p in ctx for p in PRIOR_DURATION_CONTEXT_PATTERNS)
        and "_NonConsolidated" in ctx
    )



def _find_consolidated_duration_value(
    tag_elements: dict, tag: str
) -> tuple[Optional[float], Optional[float]]:
    """指定タグの連結当期・前期（Duration）値を返す。"""
    if tag not in tag_elements:
        return None, None
    current = prior = None
    for ctx, val in tag_elements[tag].items():
        if _is_consolidated_duration(ctx):
            current = val
        elif _is_consolidated_prior_duration(ctx):
            prior = val
    return current, prior


def _find_nonconsolidated_duration_value(
    tag_elements: dict, tag: str
) -> tuple[Optional[float], Optional[float]]:
    """指定タグの個別当期・前期（Duration）値を返す。"""
    if tag not in tag_elements:
        return None, None
    current = prior = None
    for ctx, val in tag_elements[tag].items():
        if _is_nonconsolidated_duration(ctx):
            current = val
        elif _is_nonconsolidated_prior_duration(ctx):
            prior = val
    return current, prior


def _detect_accounting_standard(tag_elements: dict) -> str:
    """会計基準を判定: 'J-GAAP' | 'IFRS' | 'US-GAAP'"""
    usgaap_tags = {
        "TotalAssetsUSGAAPSummaryOfBusinessResults",
        "EquityAttributableToOwnersOfParentUSGAAPSummaryOfBusinessResults",
    }
    ifrs_marker_tags = [
        "InterestBearingLiabilitiesCLIFRS",
        "BorrowingsCLIFRS",
        "BondsPayableNCLIFRS",
        "BorrowingsNCLIFRS",
    ]
    if any(t in tag_elements for t in usgaap_tags) and not any(
        t in tag_elements for t in ifrs_marker_tags
    ):
        return "US-GAAP"
    if any(t in tag_elements for t in ifrs_marker_tags):
        return "IFRS"
    return "J-GAAP"


def extract_gross_profit(xbrl_dir: Path) -> dict:
    """
    XBRLディレクトリから連結損益計算書の売上総利益を抽出する。

    Returns:
        {
            "current": float | None,      # 当期（円）
            "prior":   float | None,      # 前期（円）
            "method":  str,               # "direct" | "computed" | "not_found"
            "accounting_standard": str,   # "J-GAAP" | "IFRS" | "US-GAAP"
            "components": [
                {
                    "label": str,
                    "tag":   str | None,
                    "current": float | None,
                    "prior":   float | None,
                }
            ]
        }
    """
    tag_elements: dict = {}
    for f in find_xbrl_files(xbrl_dir):
        for tag, ctx_map in collect_numeric_elements(f, allowed_tags=_GP_RELEVANT_TAGS).items():
            if tag not in tag_elements:
                tag_elements[tag] = {}
            tag_elements[tag].update(ctx_map)

    accounting_standard = _detect_accounting_standard(tag_elements)

    # 直接法: GrossProfit タグを検索
    for gp_tag in GROSS_PROFIT_DIRECT_TAGS:
        current, prior = _find_consolidated_duration_value(tag_elements, gp_tag)
        if current is None and prior is None:
            current, prior = _find_nonconsolidated_duration_value(tag_elements, gp_tag)
        if current is not None or prior is not None:
            return {
                "current": current,
                "prior": prior,
                "method": "direct",
                "accounting_standard": accounting_standard,
                "components": [
                    {"label": "売上総利益", "tag": gp_tag, "current": current, "prior": prior}
                ],
            }

    # 計算法: 売上高タグ・売上原価タグをそれぞれ取得して差し引く
    comp_results = []
    for comp_def in GROSS_PROFIT_COMPONENT_DEFINITIONS:
        found_tag = None
        current = prior = None
        for tag in comp_def["tags"]:
            c, p = _find_consolidated_duration_value(tag_elements, tag)
            if c is not None or p is not None:
                found_tag = tag
                current, prior = c, p
                break
        comp_results.append({
            "label": comp_def["label"],
            "tag": found_tag,
            "current": current,
            "prior": prior,
        })

    # 連結値が全くなければ個別にフォールバック
    has_consolidated = any(c["current"] is not None or c["prior"] is not None for c in comp_results)
    if not has_consolidated:
        comp_results = []
        for comp_def in GROSS_PROFIT_COMPONENT_DEFINITIONS:
            found_tag = None
            current = prior = None
            for tag in comp_def["tags"]:
                c, p = _find_nonconsolidated_duration_value(tag_elements, tag)
                if c is not None or p is not None:
                    found_tag = tag
                    current, prior = c, p
                    break
            comp_results.append({
                "label": comp_def["label"],
                "tag": found_tag,
                "current": current,
                "prior": prior,
            })

    sales = next((c for c in comp_results if c["label"] == "売上高"), None)
    cogs = next((c for c in comp_results if c["label"] == "売上原価"), None)

    if sales is None or (sales["current"] is None and sales["prior"] is None):
        return {
            "current": None,
            "prior": None,
            "method": "not_found",
            "accounting_standard": accounting_standard,
            "components": comp_results,
        }

    def _subtract(a: Optional[float], b: Optional[float]) -> Optional[float]:
        if a is None:
            return None
        return a - (b or 0.0)

    cogs_current = cogs["current"] if cogs else None
    cogs_prior = cogs["prior"] if cogs else None
    gp_current = _subtract(sales["current"], cogs_current)
    gp_prior = _subtract(sales["prior"], cogs_prior)

    if gp_current is None and gp_prior is None:
        return {
            "current": None,
            "prior": None,
            "method": "not_found",
            "accounting_standard": accounting_standard,
            "components": comp_results,
        }

    return {
        "current": gp_current,
        "prior": gp_prior,
        "method": "computed",
        "accounting_standard": accounting_standard,
        "components": comp_results,
    }
