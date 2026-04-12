"""
キャッシュフロー XBRL抽出モジュール

XBRLインスタンス文書から連結キャッシュフロー計算書の
営業CF・投資CFを抽出する。

タグ体系:
  J-GAAP:   NetCashProvidedByUsedInOperatingActivities / NetCashProvidedByUsedInInvestingActivities
  IFRS連結:  CashFlowsFromUsedInOperationsIFRS / CashFlowsUsedInInvestingActivitiesIFRS

コンテキスト:
  CF計算書はフロー項目なので Duration コンテキストを使用する。
"""

import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Dict, Optional

from mebuki.constants.xbrl import CF_OPERATING_TAGS, CF_INVESTING_TAGS

_CF_RELEVANT_TAGS: frozenset = frozenset(
    CF_OPERATING_TAGS
    + CF_INVESTING_TAGS
    + [
        # 会計基準判定用マーカー（gross_profit.py と同一セット）
        "TotalAssetsUSGAAPSummaryOfBusinessResults",
        "EquityAttributableToOwnersOfParentUSGAAPSummaryOfBusinessResults",
        "InterestBearingLiabilitiesCLIFRS",
        "BorrowingsCLIFRS",
        "BondsPayableNCLIFRS",
        "BorrowingsNCLIFRS",
    ]
)

# 年次: CurrentYearDuration / 新形式半期: InterimDuration / 旧形式半期・四半期: CurrentYTDDuration
_DURATION_CONTEXT_PATTERNS = ["CurrentYearDuration", "FilingDateDuration", "InterimDuration", "CurrentYTDDuration"]
_PRIOR_DURATION_CONTEXT_PATTERNS = ["Prior1YearDuration", "PriorYearDuration", "Prior1InterimDuration", "Prior1YTDDuration"]


def _is_consolidated_duration(ctx: str) -> bool:
    return any(p in ctx for p in _DURATION_CONTEXT_PATTERNS) and "_NonConsolidated" not in ctx


def _is_consolidated_prior_duration(ctx: str) -> bool:
    return any(p in ctx for p in _PRIOR_DURATION_CONTEXT_PATTERNS) and "_NonConsolidated" not in ctx


def _parse_value(text: Optional[str]) -> Optional[float]:
    if not text or text.strip() in ("", "nil"):
        return None
    try:
        return float(text.strip())
    except (ValueError, TypeError):
        return None


def _collect_numeric_elements(xml_file: Path, allowed_tags: frozenset) -> Dict[str, Any]:
    results: dict = {}
    try:
        tree = ET.parse(xml_file)
        root = tree.getroot()
        for elem in root.iter():
            tag = elem.tag
            local_tag = tag.split("}")[1] if "}" in tag else tag
            if local_tag not in allowed_tags:
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


def _find_duration_value(
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


def extract_cash_flow(xbrl_dir: Path) -> dict:
    """
    XBRLディレクトリから連結CF計算書の営業CF・投資CFを抽出する。

    年次報告書では当期 = FY の値、2Q 報告書では当期 = H1（上半期累計）の値。

    Returns:
        {
            "cfo": {"current": float | None, "prior": float | None},
            "cfi": {"current": float | None, "prior": float | None},
            "accounting_standard": str,   # "J-GAAP" | "IFRS" | "US-GAAP"
        }
    """
    xml_files = [
        f for f in xbrl_dir.rglob("*.xml")
        if not any(s in f.name for s in ["_lab", "_pre", "_cal", "_def"])
    ]
    xml_files += list(xbrl_dir.rglob("*.xbrl"))

    tag_elements: dict = {}
    for f in xml_files:
        for tag, ctx_map in _collect_numeric_elements(f, _CF_RELEVANT_TAGS).items():
            if tag not in tag_elements:
                tag_elements[tag] = {}
            tag_elements[tag].update(ctx_map)

    # 会計基準判定
    usgaap_markers = {
        "TotalAssetsUSGAAPSummaryOfBusinessResults",
        "EquityAttributableToOwnersOfParentUSGAAPSummaryOfBusinessResults",
    }
    ifrs_markers = [
        "InterestBearingLiabilitiesCLIFRS",
        "BorrowingsCLIFRS",
        "BondsPayableNCLIFRS",
        "BorrowingsNCLIFRS",
    ]
    if any(t in tag_elements for t in usgaap_markers) and not any(
        t in tag_elements for t in ifrs_markers
    ):
        accounting_standard = "US-GAAP"
    elif any(t in tag_elements for t in ifrs_markers):
        accounting_standard = "IFRS"
    else:
        accounting_standard = "J-GAAP"

    # 営業CF
    cfo_current = cfo_prior = None
    for tag in CF_OPERATING_TAGS:
        c, p = _find_duration_value(tag_elements, tag)
        if c is not None or p is not None:
            cfo_current, cfo_prior = c, p
            break

    # 投資CF
    cfi_current = cfi_prior = None
    for tag in CF_INVESTING_TAGS:
        c, p = _find_duration_value(tag_elements, tag)
        if c is not None or p is not None:
            cfi_current, cfi_prior = c, p
            break

    return {
        "cfo": {"current": cfo_current, "prior": cfo_prior},
        "cfi": {"current": cfi_current, "prior": cfi_prior},
        "accounting_standard": accounting_standard,
    }
