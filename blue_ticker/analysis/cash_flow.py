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

from blue_ticker.analysis.field_parser import (
    FieldSet,
    field_set_from_pre_parsed_duration,
    parse_duration_fields,
    resolve_item,
)
from blue_ticker.utils.xbrl_result_types import CashFlowResult, XbrlTagElements
from blue_ticker.constants.xbrl import (
    CF_INVESTING_TAGS,
    CF_OPERATING_TAGS,
    IFRS_PL_MARKER_TAGS,
    USGAAP_MARKER_TAGS,
)

_CF_RELEVANT_TAGS: frozenset[str] = frozenset(
    CF_OPERATING_TAGS
    + CF_INVESTING_TAGS
    + USGAAP_MARKER_TAGS
    + IFRS_PL_MARKER_TAGS
)


def _detect_accounting_standard(field_set: FieldSet) -> str:
    has_usgaap = any("USGAAP" in tag for tag in field_set)
    has_ifrs = any("IFRS" in tag for tag in field_set)
    if has_usgaap and not has_ifrs:
        return "US-GAAP"
    if has_ifrs:
        return "IFRS"
    return "J-GAAP"


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
    field_set = (
        field_set_from_pre_parsed_duration(pre_parsed)
        if pre_parsed is not None
        else parse_duration_fields(xbrl_dir, allowed_tags=_CF_RELEVANT_TAGS)
    )

    accounting_standard = _detect_accounting_standard(field_set)

    cfo_item = resolve_item(field_set, CF_OPERATING_TAGS)
    cfi_item = resolve_item(field_set, CF_INVESTING_TAGS)

    return {
        "cfo": {"current": cfo_item["current"], "prior": cfo_item["prior"]},
        "cfi": {"current": cfi_item["current"], "prior": cfi_item["prior"]},
        "accounting_standard": accounting_standard,
    }
