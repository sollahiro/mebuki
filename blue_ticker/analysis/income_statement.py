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

from blue_ticker.analysis.field_parser import (
    FieldSet,
    field_set_from_pre_parsed_duration,
    parse_duration_fields,
    resolve_item,
    resolve_item_prefer_current,
)
from blue_ticker.constants.xbrl import (
    IFRS_PL_MARKER_TAGS,
    NET_PROFIT_TAGS,
    NET_SALES_TAGS,
    OPERATING_PROFIT_DIRECT_TAGS,
    OPERATING_REVENUE_TAGS,
    USGAAP_MARKER_TAGS,
)
from blue_ticker.utils.xbrl_result_types import IncomeStatementResult, XbrlTagElements

_IS_RELEVANT_TAGS: frozenset[str] = frozenset(
    NET_SALES_TAGS
    + OPERATING_PROFIT_DIRECT_TAGS
    + NET_PROFIT_TAGS
    + USGAAP_MARKER_TAGS
    + IFRS_PL_MARKER_TAGS
)


def _detect_accounting_standard(field_set: FieldSet) -> str:
    has_usgaap = any("USGAAP" in tag for tag in field_set)
    has_ifrs = any("IFRS" in tag for tag in field_set)
    if has_ifrs:
        return "IFRS"
    if has_usgaap:
        return "US-GAAP"
    return "J-GAAP"


def _sales_label_for_tag(tag: str | None) -> str:
    if tag in OPERATING_REVENUE_TAGS:
        return "営業収益"
    if tag in ("NetSalesIFRS", "RevenueIFRS", "Revenue"):
        return "売上収益"
    if tag in (
        "NetSalesOfCompletedConstructionContractsCNS",
        "NetSalesOfCompletedConstructionContractsSummaryOfBusinessResults",
    ):
        return "完成工事高"
    return "売上高"


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
    field_set = (
        field_set_from_pre_parsed_duration(pre_parsed)
        if pre_parsed is not None
        else parse_duration_fields(xbrl_dir, allowed_tags=_IS_RELEVANT_TAGS)
    )

    standard = _detect_accounting_standard(field_set)

    sales_item = resolve_item_prefer_current(field_set, NET_SALES_TAGS)
    op_item = resolve_item_prefer_current(field_set, OPERATING_PROFIT_DIRECT_TAGS)
    np_item = resolve_item_prefer_current(field_set, NET_PROFIT_TAGS)

    found_tags = [
        k for k in ("sales", "operating_profit", "net_profit")
        if {"sales": sales_item["current"], "operating_profit": op_item["current"], "net_profit": np_item["current"]}[k] is not None
    ]
    method = ",".join(found_tags) if found_tags else "not_found"

    result: IncomeStatementResult = {
        "sales": sales_item["current"],
        "sales_prior": sales_item["prior"],
        "operating_profit": op_item["current"],
        "operating_profit_prior": op_item["prior"],
        "net_profit": np_item["current"],
        "net_profit_prior": np_item["prior"],
        "accounting_standard": standard,
        "method": method,
    }
    if sales_item["current"] is not None:
        result["sales_label"] = _sales_label_for_tag(sales_item["tag"])
    return result
