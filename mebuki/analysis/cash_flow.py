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

from mebuki.analysis.context_helpers import _is_consolidated_duration, _is_consolidated_prior_duration
from mebuki.analysis.xbrl_utils import parse_xbrl_value, collect_numeric_elements, find_xbrl_files
from mebuki.constants.xbrl import CF_INVESTING_TAGS, CF_OPERATING_TAGS

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



def _find_duration_value(
    tag_elements: dict, tag: str
) -> tuple[float | None, float | None]:
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


def extract_cash_flow(xbrl_dir: Path, *, pre_parsed: dict | None = None) -> dict:
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
        tag_elements: dict = {tag: ctx for tag, ctx in pre_parsed.items() if tag in _CF_RELEVANT_TAGS}
    else:
        tag_elements = {}
        for f in find_xbrl_files(xbrl_dir):
            for tag, ctx_map in collect_numeric_elements(f, _CF_RELEVANT_TAGS).items():
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
