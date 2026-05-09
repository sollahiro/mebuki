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

from pathlib import Path

from blue_ticker.analysis.context_helpers import (
    _is_consolidated_duration,
    _is_consolidated_prior_duration,
    _is_nonconsolidated_duration,
    _is_nonconsolidated_prior_duration,
    _is_pure_context,
    _is_pure_nonconsolidated_context,
    has_nonconsolidated_contexts,
)
from blue_ticker.analysis.xbrl_utils import collect_numeric_elements, find_xbrl_files
from blue_ticker.utils.xbrl_result_types import CashFlowResult, XbrlTagElements
from blue_ticker.constants.xbrl import (
    CF_INVESTING_TAGS,
    CF_OPERATING_TAGS,
    DURATION_CONTEXT_PATTERNS,
    IFRS_PL_MARKER_TAGS,
    PRIOR_DURATION_CONTEXT_PATTERNS,
    USGAAP_MARKER_TAGS,
)

_CF_RELEVANT_TAGS: frozenset[str] = frozenset(
    CF_OPERATING_TAGS
    + CF_INVESTING_TAGS
    + USGAAP_MARKER_TAGS
    + IFRS_PL_MARKER_TAGS
)



def _find_duration_value(
    tag_elements: XbrlTagElements, tag: str, *, consolidated: bool = True
) -> tuple[float | None, float | None]:
    """指定タグの連結当期・前期（Duration）値を返す。"""
    if tag not in tag_elements:
        return None, None
    is_current = _is_consolidated_duration if consolidated else _is_nonconsolidated_duration
    is_prior = _is_consolidated_prior_duration if consolidated else _is_nonconsolidated_prior_duration
    is_pure = _is_pure_context if consolidated else _is_pure_nonconsolidated_context
    current = prior = None
    current_pure = prior_pure = None
    for ctx, val in tag_elements[tag].items():
        if is_current(ctx):
            if is_pure(ctx, DURATION_CONTEXT_PATTERNS):
                current_pure = val
            else:
                current = val
        elif is_prior(ctx):
            if is_pure(ctx, PRIOR_DURATION_CONTEXT_PATTERNS):
                prior_pure = val
            else:
                prior = val
    return (
        current_pure if current_pure is not None else current,
        prior_pure if prior_pure is not None else prior,
    )


def extract_cash_flow(
    xbrl_dir: Path,
    *,
    pre_parsed: XbrlTagElements | None = None,
) -> CashFlowResult:
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
    if pre_parsed is not None:
        tag_elements: XbrlTagElements = {
            tag: ctx for tag, ctx in pre_parsed.items() if tag in _CF_RELEVANT_TAGS
        }
    else:
        tag_elements = {}
        for f in find_xbrl_files(xbrl_dir):
            for tag, ctx_map in collect_numeric_elements(f, _CF_RELEVANT_TAGS).items():
                if tag not in tag_elements:
                    tag_elements[tag] = {}
                tag_elements[tag].update(ctx_map)

    check_elements = pre_parsed if pre_parsed is not None else tag_elements
    _blocks_nc = has_nonconsolidated_contexts(check_elements)

    # 会計基準判定
    if any(t in tag_elements for t in USGAAP_MARKER_TAGS) and not any(
        t in tag_elements for t in IFRS_PL_MARKER_TAGS
    ):
        accounting_standard = "US-GAAP"
    elif any(t in tag_elements for t in IFRS_PL_MARKER_TAGS):
        accounting_standard = "IFRS"
    else:
        accounting_standard = "J-GAAP"

    # 営業CF
    cfo_current = cfo_prior = None
    for tag in CF_OPERATING_TAGS:
        c, p = _find_duration_value(tag_elements, tag)
        if c is None and p is None and not _blocks_nc:
            c, p = _find_duration_value(tag_elements, tag, consolidated=False)
        if c is not None or p is not None:
            cfo_current, cfo_prior = c, p
            break

    # 投資CF
    cfi_current = cfi_prior = None
    for tag in CF_INVESTING_TAGS:
        c, p = _find_duration_value(tag_elements, tag)
        if c is None and p is None and not _blocks_nc:
            c, p = _find_duration_value(tag_elements, tag, consolidated=False)
        if c is not None or p is not None:
            cfi_current, cfi_prior = c, p
            break

    return {
        "cfo": {"current": cfo_current, "prior": cfo_prior},
        "cfi": {"current": cfi_current, "prior": cfi_prior},
        "accounting_standard": accounting_standard,
    }
