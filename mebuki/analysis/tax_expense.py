"""
実効税率 XBRL抽出モジュール

XBRLインスタンス文書から連結損益計算書の税引前利益・法人税等を抽出し、
実効税率を計算する。

タグ体系:
  J-GAAP:  IncomeBeforeIncomeTaxes / IncomeTaxes
  IFRS:    ProfitLossBeforeTaxIFRS / IncomeTaxExpenseIFRS
  US-GAAP: 未対応（not_found を返す）
"""

from pathlib import Path
from typing import Optional

from mebuki.analysis.xbrl_utils import collect_numeric_elements, find_xbrl_files
from mebuki.constants.xbrl import (
    PRETAX_INCOME_JGAAP_TAGS,
    PRETAX_INCOME_IFRS_TAGS,
    INCOME_TAX_JGAAP_TAGS,
    INCOME_TAX_IFRS_TAGS,
)

_TAX_RELEVANT_TAGS: frozenset[str] = frozenset(
    PRETAX_INCOME_JGAAP_TAGS
    + PRETAX_INCOME_IFRS_TAGS
    + INCOME_TAX_JGAAP_TAGS
    + INCOME_TAX_IFRS_TAGS
    + [
        "TotalAssetsUSGAAPSummaryOfBusinessResults",
        "EquityAttributableToOwnersOfParentUSGAAPSummaryOfBusinessResults",
        "InterestBearingLiabilitiesCLIFRS",
        "BorrowingsCLIFRS",
        "BondsPayableNCLIFRS",
        "BorrowingsNCLIFRS",
        "ProfitLossBeforeTaxIFRS",
        "IncomeTaxExpenseIFRS",
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


def _find_consolidated_duration_value(
    tag_elements: dict, tag: str
) -> tuple[Optional[float], Optional[float]]:
    if tag not in tag_elements:
        return None, None
    current = prior = None
    current_pure = prior_pure = None
    for ctx, val in tag_elements[tag].items():
        if _is_consolidated_duration(ctx):
            if any(ctx == p for p in _DURATION_CONTEXT_PATTERNS):
                current_pure = val
            else:
                current = val
        elif _is_consolidated_prior_duration(ctx):
            if any(ctx == p for p in _PRIOR_DURATION_CONTEXT_PATTERNS):
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
    if tag not in tag_elements:
        return None, None
    current = prior = None
    current_pure = prior_pure = None
    for ctx, val in tag_elements[tag].items():
        if _is_nonconsolidated_duration(ctx):
            if any(ctx == p for p in _DURATION_CONTEXT_PATTERNS):
                current_pure = val
            else:
                current = val
        elif _is_nonconsolidated_prior_duration(ctx):
            if any(ctx == p for p in _PRIOR_DURATION_CONTEXT_PATTERNS):
                prior_pure = val
            else:
                prior = val
    return (
        current_pure if current_pure is not None else current,
        prior_pure if prior_pure is not None else prior,
    )


def _detect_accounting_standard(tag_elements: dict) -> str:
    usgaap_tags = {
        "TotalAssetsUSGAAPSummaryOfBusinessResults",
        "EquityAttributableToOwnersOfParentUSGAAPSummaryOfBusinessResults",
    }
    ifrs_marker_tags = [
        "InterestBearingLiabilitiesCLIFRS",
        "BorrowingsCLIFRS",
        "BondsPayableNCLIFRS",
        "BorrowingsNCLIFRS",
        "ProfitLossBeforeTaxIFRS",
        "IncomeTaxExpenseIFRS",
    ]
    if any(t in tag_elements for t in usgaap_tags) and not any(
        t in tag_elements for t in ifrs_marker_tags
    ):
        return "US-GAAP"
    if any(t in tag_elements for t in ifrs_marker_tags):
        return "IFRS"
    return "J-GAAP"


def _get_value(tag_elements: dict, tags: list[str]) -> tuple[Optional[float], Optional[float]]:
    for tag in tags:
        current, prior = _find_consolidated_duration_value(tag_elements, tag)
        if current is None and prior is None:
            current, prior = _find_nonconsolidated_duration_value(tag_elements, tag)
        if current is not None or prior is not None:
            return current, prior
    return None, None


def extract_tax_expense(xbrl_dir: Path) -> dict:
    """
    XBRLディレクトリから税引前利益・法人税等を抽出し実効税率を計算する。

    Returns:
        {
            "pretax_income":    float | None,  # 当期税引前利益（円）
            "income_tax":       float | None,  # 当期法人税等（円）
            "effective_tax_rate": float | None,  # 実効税率（小数、例: 0.254）
            "prior_pretax_income":  float | None,
            "prior_income_tax":     float | None,
            "prior_effective_tax_rate": float | None,
            "accounting_standard": str,
            "method": str,   # "computed" | "not_found"
        }
    """
    tag_elements: dict = {}
    for f in find_xbrl_files(xbrl_dir):
        for tag, ctx_map in collect_numeric_elements(f, allowed_tags=_TAX_RELEVANT_TAGS).items():
            tag_elements.setdefault(tag, {}).update(ctx_map)

    accounting_standard = _detect_accounting_standard(tag_elements)

    if accounting_standard == "US-GAAP":
        return {
            "pretax_income": None, "income_tax": None, "effective_tax_rate": None,
            "prior_pretax_income": None, "prior_income_tax": None, "prior_effective_tax_rate": None,
            "accounting_standard": "US-GAAP", "method": "not_found",
            "reason": "US-GAAP 税引前利益の HTML 解析は未対応",
        }

    if accounting_standard == "IFRS":
        pretax_tags = PRETAX_INCOME_IFRS_TAGS
        tax_tags = INCOME_TAX_IFRS_TAGS
    else:
        pretax_tags = PRETAX_INCOME_JGAAP_TAGS
        tax_tags = INCOME_TAX_JGAAP_TAGS

    pretax_cur, pretax_prior = _get_value(tag_elements, pretax_tags)
    tax_cur, tax_prior = _get_value(tag_elements, tax_tags)

    def _tax_rate(pretax: Optional[float], tax: Optional[float]) -> Optional[float]:
        if pretax is not None and tax is not None and pretax != 0:
            return tax / pretax
        return None

    if pretax_cur is None and tax_cur is None:
        return {
            "pretax_income": None, "income_tax": None, "effective_tax_rate": None,
            "prior_pretax_income": None, "prior_income_tax": None, "prior_effective_tax_rate": None,
            "accounting_standard": accounting_standard, "method": "not_found",
            "reason": f"{accounting_standard} 税引前利益タグが見つからない",
        }

    return {
        "pretax_income": pretax_cur,
        "income_tax": tax_cur,
        "effective_tax_rate": _tax_rate(pretax_cur, tax_cur),
        "prior_pretax_income": pretax_prior,
        "prior_income_tax": tax_prior,
        "prior_effective_tax_rate": _tax_rate(pretax_prior, tax_prior),
        "accounting_standard": accounting_standard,
        "method": "computed",
    }
