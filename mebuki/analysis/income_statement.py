"""
損益計算書 XBRL 抽出モジュール

XBRLインスタンス文書から連結損益計算書の
売上高・営業利益・当期純利益を抽出する。

EDINET-only運用時の基幹財務データ取得に使用する。

タグ体系:
  J-GAAP:   NetSales / OperatingIncomeLoss / ProfitLossAttributableToOwnersOfParent
  IFRS連結:  NetSalesIFRS / OperatingProfitLossIFRS / ProfitLossAttributableToOwnersOfParentIFRS
  US-GAAP:   Revenues / (OperatingIncomeLoss) / NetIncomeLossAttributableToOwnersOfParentUSGAAP

コンテキスト:
  損益計算書はフロー項目なので Duration コンテキストを使用する。
"""

from pathlib import Path

from mebuki.analysis.context_helpers import (
    _is_consolidated_duration,
    _is_consolidated_prior_duration,
    _is_pure_context,
)
from mebuki.analysis.xbrl_utils import collect_numeric_elements, find_xbrl_files
from mebuki.constants.xbrl import (
    DURATION_CONTEXT_PATTERNS,
    IFRS_PL_MARKER_TAGS,
    NET_PROFIT_TAGS,
    NET_SALES_TAGS,
    OPERATING_PROFIT_DIRECT_TAGS,
    PRIOR_DURATION_CONTEXT_PATTERNS,
    USGAAP_MARKER_TAGS,
)
from mebuki.utils.xbrl_result_types import IncomeStatementResult, XbrlTagElements

_IS_RELEVANT_TAGS: frozenset[str] = frozenset(
    NET_SALES_TAGS
    + OPERATING_PROFIT_DIRECT_TAGS
    + NET_PROFIT_TAGS
    + USGAAP_MARKER_TAGS
    + IFRS_PL_MARKER_TAGS
)


def _find_first_duration_value(
    tag_elements: XbrlTagElements,
    tags: list[str],
) -> tuple[float | None, float | None]:
    """タグリストを優先順に試み、最初にヒットした連結 Duration 値（当期・前期）を返す。"""
    for tag in tags:
        if tag not in tag_elements:
            continue
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
        resolved_current = current_pure if current_pure is not None else current
        resolved_prior = prior_pure if prior_pure is not None else prior
        if resolved_current is not None:
            return resolved_current, resolved_prior
    return None, None


def extract_income_statement(
    xbrl_dir: Path,
    *,
    pre_parsed: XbrlTagElements | None = None,
) -> IncomeStatementResult:
    """
    XBRLディレクトリから連結損益計算書の売上高・営業利益・当期純利益を抽出する。

    Returns:
        売上高・営業利益・当期純利益（円単位）と会計基準。
        取得できない項目は None。
    """
    if pre_parsed is not None:
        tag_elements = pre_parsed
    else:
        tag_elements = {}
        for f in find_xbrl_files(xbrl_dir):
            for tag, ctx_map in collect_numeric_elements(f, allowed_tags=_IS_RELEVANT_TAGS).items():
                if tag not in tag_elements:
                    tag_elements[tag] = {}
                tag_elements[tag].update(ctx_map)

    is_ifrs = any(t in tag_elements for t in IFRS_PL_MARKER_TAGS)
    is_usgaap = any(t in tag_elements for t in USGAAP_MARKER_TAGS)
    if is_ifrs:
        standard = "IFRS"
    elif is_usgaap:
        standard = "US-GAAP"
    else:
        standard = "J-GAAP"

    sales_cur, sales_prior = _find_first_duration_value(tag_elements, NET_SALES_TAGS)
    op_cur, op_prior = _find_first_duration_value(tag_elements, OPERATING_PROFIT_DIRECT_TAGS)
    np_cur, np_prior = _find_first_duration_value(tag_elements, NET_PROFIT_TAGS)

    found_tags = [
        k for k in ("sales", "operating_profit", "net_profit")
        if {"sales": sales_cur, "operating_profit": op_cur, "net_profit": np_cur}[k] is not None
    ]
    method = ",".join(found_tags) if found_tags else "not_found"

    return {
        "sales": sales_cur,
        "sales_prior": sales_prior,
        "operating_profit": op_cur,
        "operating_profit_prior": op_prior,
        "net_profit": np_cur,
        "net_profit_prior": np_prior,
        "accounting_standard": standard,
        "method": method,
    }
