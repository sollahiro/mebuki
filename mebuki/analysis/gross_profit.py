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

import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Dict, Optional

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
DURATION_CONTEXT_PATTERNS = [
    "CurrentYearDuration",
    "FilingDateDuration",
]

PRIOR_DURATION_CONTEXT_PATTERNS = [
    "Prior1YearDuration",
    "PriorYearDuration",
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


def _parse_value(text: Optional[str]) -> Optional[float]:
    """XBRL数値テキストを float に変換。"""
    if not text or text.strip() in ("", "nil"):
        return None
    try:
        return float(text.strip())
    except (ValueError, TypeError):
        return None


def _collect_numeric_elements(
    xml_file: Path,
    allowed_tags: frozenset[str] | None = None,
) -> Dict[str, Any]:
    """XMLファイルから {local_tag: {ctx: value}} の辞書を返す。"""
    results: dict = {}
    try:
        tree = ET.parse(xml_file)
        root = tree.getroot()
        for elem in root.iter():
            tag = elem.tag
            local_tag = tag.split("}")[1] if "}" in tag else tag
            if allowed_tags is not None and local_tag not in allowed_tags:
                continue
            ctx = elem.attrib.get("contextRef", "")
            value = _parse_value(elem.text)
            if value is not None and ctx:
                if local_tag not in results:
                    results[local_tag] = {}
                results[local_tag][ctx] = value
    except ET.ParseError:
        pass
    return results


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
    xml_files = [
        f for f in xbrl_dir.rglob("*.xml")
        if not any(s in f.name for s in ["_lab", "_pre", "_cal", "_def"])
    ]
    xml_files += list(xbrl_dir.rglob("*.xbrl"))

    tag_elements: dict = {}
    for f in xml_files:
        for tag, ctx_map in _collect_numeric_elements(f, allowed_tags=_GP_RELEVANT_TAGS).items():
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
