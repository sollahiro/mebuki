"""
減価償却費 XBRL抽出モジュール

XBRLインスタンス文書から連結キャッシュ・フロー計算書の減価償却費を抽出する。

タグ体系:
  J-GAAP: DepreciationAndAmortizationOpeCF
  IFRS:   DepreciationAndAmortizationOpeCFIFRS

コンテキスト:
  CF計算書はフロー項目なので Duration コンテキストを使用する。
"""

from pathlib import Path

from mebuki.analysis.context_helpers import (
    _is_consolidated_duration,
    _is_consolidated_prior_duration,
    _is_nonconsolidated_duration,
    _is_nonconsolidated_prior_duration,
)
from mebuki.analysis.xbrl_utils import collect_numeric_elements, find_xbrl_files
from mebuki.constants.xbrl import (
    CF_DEPRECIATION_IFRS_TAGS,
    CF_DEPRECIATION_JGAAP_TAGS,
    DURATION_CONTEXT_PATTERNS,
    PRIOR_DURATION_CONTEXT_PATTERNS,
)
from mebuki.utils.xbrl_result_types import DepreciationResult, XbrlTagElements

_CF_DA_RELEVANT_TAGS: frozenset[str] = frozenset(
    CF_DEPRECIATION_JGAAP_TAGS
    + CF_DEPRECIATION_IFRS_TAGS
    + [
        "TotalAssetsUSGAAPSummaryOfBusinessResults",
        "EquityAttributableToOwnersOfParentUSGAAPSummaryOfBusinessResults",
        "InterestBearingLiabilitiesCLIFRS",
        "BorrowingsCLIFRS",
        "BondsPayableNCLIFRS",
        "BorrowingsNCLIFRS",
    ]
)


def _is_pure_context(ctx: str, patterns: list[str]) -> bool:
    return any(ctx == p for p in patterns)


def _find_consolidated_duration_value(
    tag_elements: XbrlTagElements,
    tag: str,
) -> tuple[float | None, float | None]:
    if tag not in tag_elements:
        return None, None
    current = prior = None
    current_pure = prior_pure = None
    for ctx, val in tag_elements[tag].items():
        if _is_consolidated_duration(ctx):
            if _is_pure_context(ctx, DURATION_CONTEXT_PATTERNS):
                current_pure = val
            else:
                current = val
        elif _is_consolidated_prior_duration(ctx):
            if _is_pure_context(ctx, PRIOR_DURATION_CONTEXT_PATTERNS):
                prior_pure = val
            else:
                prior = val
    return (
        current_pure if current_pure is not None else current,
        prior_pure if prior_pure is not None else prior,
    )


def _find_nonconsolidated_duration_value(
    tag_elements: XbrlTagElements,
    tag: str,
) -> tuple[float | None, float | None]:
    if tag not in tag_elements:
        return None, None
    current = prior = None
    current_pure = prior_pure = None
    for ctx, val in tag_elements[tag].items():
        if _is_nonconsolidated_duration(ctx):
            if _is_pure_context(ctx, DURATION_CONTEXT_PATTERNS):
                current_pure = val
            else:
                current = val
        elif _is_nonconsolidated_prior_duration(ctx):
            if _is_pure_context(ctx, PRIOR_DURATION_CONTEXT_PATTERNS):
                prior_pure = val
            else:
                prior = val
    return (
        current_pure if current_pure is not None else current,
        prior_pure if prior_pure is not None else prior,
    )


def _detect_accounting_standard(tag_elements: XbrlTagElements) -> str:
    usgaap_tags = {
        "TotalAssetsUSGAAPSummaryOfBusinessResults",
        "EquityAttributableToOwnersOfParentUSGAAPSummaryOfBusinessResults",
    }
    ifrs_marker_tags = [
        "InterestBearingLiabilitiesCLIFRS",
        "BorrowingsCLIFRS",
        "BondsPayableNCLIFRS",
        "BorrowingsNCLIFRS",
        "DepreciationAndAmortizationOpeCFIFRS",  # DA タグ自身で IFRS 判定（集約型 IBD タグしか持たない企業に対応）
    ]
    if any(t in tag_elements for t in usgaap_tags) and not any(
        t in tag_elements for t in ifrs_marker_tags
    ):
        return "US-GAAP"
    if any(t in tag_elements for t in ifrs_marker_tags):
        return "IFRS"
    return "J-GAAP"


def extract_depreciation(
    xbrl_dir: Path,
    *,
    pre_parsed: XbrlTagElements | None = None,
) -> DepreciationResult:
    """
    XBRLディレクトリから連結CF計算書の減価償却費を抽出する。

    Returns:
        {
            "current": float | None,
            "prior":   float | None,
            "method":  str,
            "accounting_standard": str,
        }
    """
    if pre_parsed is not None:
        tag_elements: XbrlTagElements = {
            tag: ctx for tag, ctx in pre_parsed.items() if tag in _CF_DA_RELEVANT_TAGS
        }
    else:
        tag_elements = {}
        for file_path in find_xbrl_files(xbrl_dir):
            for tag, ctx_map in collect_numeric_elements(
                file_path,
                allowed_tags=_CF_DA_RELEVANT_TAGS,
            ).items():
                if tag not in tag_elements:
                    tag_elements[tag] = {}
                tag_elements[tag].update(ctx_map)

    accounting_standard = _detect_accounting_standard(tag_elements)

    if accounting_standard == "US-GAAP":
        return {
            "current": None,
            "prior": None,
            "method": "not_found",
            "accounting_standard": "US-GAAP",
            "reason": "US-GAAP CF計算書の減価償却費タグは未対応",
        }

    candidate_tags = (
        CF_DEPRECIATION_IFRS_TAGS
        if accounting_standard == "IFRS"
        else CF_DEPRECIATION_JGAAP_TAGS
    )

    for tag in candidate_tags:
        current, prior = _find_consolidated_duration_value(tag_elements, tag)
        if current is None and prior is None:
            current, prior = _find_nonconsolidated_duration_value(tag_elements, tag)
        if current is not None or prior is not None:
            return {
                "current": current,
                "prior": prior,
                "method": "direct",
                "accounting_standard": accounting_standard,
            }

    return {
        "current": None,
        "prior": None,
        "method": "not_found",
        "accounting_standard": accounting_standard,
        "reason": f"{accounting_standard} 減価償却費タグが見つからない",
    }
