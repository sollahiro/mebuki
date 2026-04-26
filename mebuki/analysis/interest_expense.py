"""
支払利息 XBRL抽出モジュール

XBRLインスタンス文書から連結損益計算書の支払利息（金融費用）を抽出する。

タグ体系:
  J-GAAP:  InterestExpensesNOE（営業外費用の支払利息）
  IFRS:    FinanceCostsIFRS（金融費用）
  US-GAAP: 未対応（not_found を返す）

コンテキスト:
  損益計算書はフロー項目なので Duration コンテキストを使用する。
"""

from pathlib import Path
from typing import Optional

from mebuki.analysis.xbrl_utils import collect_numeric_elements, find_xbrl_files
from mebuki.constants.xbrl import (
    INTEREST_EXPENSE_JGAAP_TAGS,
    INTEREST_EXPENSE_IFRS_TAGS,
)

_IE_RELEVANT_TAGS: frozenset[str] = frozenset(
    INTEREST_EXPENSE_JGAAP_TAGS
    + INTEREST_EXPENSE_IFRS_TAGS
    + [
        # 会計基準判定用マーカー（gross_profit.py / interest_bearing_debt.py と共通）
        "TotalAssetsUSGAAPSummaryOfBusinessResults",
        "EquityAttributableToOwnersOfParentUSGAAPSummaryOfBusinessResults",
        "InterestBearingLiabilitiesCLIFRS",
        "BorrowingsCLIFRS",
        "BondsPayableNCLIFRS",
        "BorrowingsNCLIFRS",
    ]
)

_DURATION_CONTEXT_PATTERNS = [
    "CurrentYearDuration",
    "FilingDateDuration",
    "InterimDuration",
    "CurrentYTDDuration",
]

_PRIOR_DURATION_CONTEXT_PATTERNS = [
    "Prior1YearDuration",
    "PriorYearDuration",
    "Prior1InterimDuration",
    "Prior1YTDDuration",
]


def _is_consolidated_duration(ctx: str) -> bool:
    return any(p in ctx for p in _DURATION_CONTEXT_PATTERNS) and "_NonConsolidated" not in ctx


def _is_consolidated_prior_duration(ctx: str) -> bool:
    return any(p in ctx for p in _PRIOR_DURATION_CONTEXT_PATTERNS) and "_NonConsolidated" not in ctx


def _is_nonconsolidated_duration(ctx: str) -> bool:
    return any(p in ctx for p in _DURATION_CONTEXT_PATTERNS) and "_NonConsolidated" in ctx


def _is_nonconsolidated_prior_duration(ctx: str) -> bool:
    return any(p in ctx for p in _PRIOR_DURATION_CONTEXT_PATTERNS) and "_NonConsolidated" in ctx


def _is_pure_context(ctx: str, patterns: list[str]) -> bool:
    """コンテキストがパターンに完全一致するか（セグメント修飾なし）。"""
    return any(ctx == p for p in patterns)


def _find_consolidated_duration_value(
    tag_elements: dict, tag: str
) -> tuple[Optional[float], Optional[float]]:
    """連結当期・前期の値を返す。純コンテキスト（セグメント修飾なし）を優先する。"""
    if tag not in tag_elements:
        return None, None
    current = prior = None
    current_pure = prior_pure = None
    for ctx, val in tag_elements[tag].items():
        if _is_consolidated_duration(ctx):
            if _is_pure_context(ctx, _DURATION_CONTEXT_PATTERNS):
                current_pure = val
            else:
                current = val
        elif _is_consolidated_prior_duration(ctx):
            if _is_pure_context(ctx, _PRIOR_DURATION_CONTEXT_PATTERNS):
                prior_pure = val
            else:
                prior = val
    return (
        current_pure if current_pure is not None else current,
        prior_pure if prior_pure is not None else prior,
    )


def _find_nonconsolidated_duration_value(
    tag_elements: dict, tag: str
) -> tuple[Optional[float], Optional[float]]:
    """個別当期・前期の値を返す。純コンテキストを優先する。"""
    if tag not in tag_elements:
        return None, None
    current = prior = None
    current_pure = prior_pure = None
    for ctx, val in tag_elements[tag].items():
        if _is_nonconsolidated_duration(ctx):
            if _is_pure_context(ctx, _DURATION_CONTEXT_PATTERNS):
                current_pure = val
            else:
                current = val
        elif _is_nonconsolidated_prior_duration(ctx):
            if _is_pure_context(ctx, _PRIOR_DURATION_CONTEXT_PATTERNS):
                prior_pure = val
            else:
                prior = val
    return (
        current_pure if current_pure is not None else current,
        prior_pure if prior_pure is not None else prior,
    )


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
        # 損益計算書のIFRSタグでも判定できる（貸借対照表タグが存在しない企業に対応）
        "InterestExpensesIFRS",
        "FinanceCostsIFRS",
    ]
    if any(t in tag_elements for t in usgaap_tags) and not any(
        t in tag_elements for t in ifrs_marker_tags
    ):
        return "US-GAAP"
    if any(t in tag_elements for t in ifrs_marker_tags):
        return "IFRS"
    return "J-GAAP"


def extract_interest_expense(xbrl_dir: Path) -> dict:
    """
    XBRLディレクトリから連結損益計算書の支払利息（金融費用）を抽出する。

    Returns:
        {
            "current": float | None,      # 当期（円）
            "prior":   float | None,      # 前期（円）
            "method":  str,               # "direct" | "not_found"
            "reason":  str | None,        # not_found 時のみ
            "accounting_standard": str,   # "J-GAAP" | "IFRS" | "US-GAAP"
        }
    """
    tag_elements: dict = {}
    for f in find_xbrl_files(xbrl_dir):
        for tag, ctx_map in collect_numeric_elements(f, allowed_tags=_IE_RELEVANT_TAGS).items():
            if tag not in tag_elements:
                tag_elements[tag] = {}
            tag_elements[tag].update(ctx_map)

    accounting_standard = _detect_accounting_standard(tag_elements)

    if accounting_standard == "US-GAAP":
        return {
            "current": None, "prior": None,
            "method": "not_found", "accounting_standard": "US-GAAP",
            "reason": "US-GAAP 支払利息の HTML 解析は未対応",
        }

    candidate_tags = (
        INTEREST_EXPENSE_IFRS_TAGS if accounting_standard == "IFRS"
        else INTEREST_EXPENSE_JGAAP_TAGS
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
        "current": None, "prior": None,
        "method": "not_found", "accounting_standard": accounting_standard,
        "reason": f"{accounting_standard} 支払利息タグが見つからない",
    }
