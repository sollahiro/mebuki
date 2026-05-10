"""
貸借対照表（BS）XBRL抽出モジュール

field_parser ベースの3ステージパイプライン:
  Stage 1: XBRL XML → FieldSet  (parse_instant_fields / field_set_from_pre_parsed)
  Stage 2: HTML 補完            (parse_usgaap_html_bs_fields — US-GAAP 企業のみ)
  Stage 3: FieldSet → 財務項目値 (resolve_item / resolve_aggregate / derive_subtraction)
"""

from pathlib import Path

from blue_ticker.analysis.field_parser import (
    FieldSet,
    field_set_from_pre_parsed,
    parse_instant_fields,
    parse_usgaap_html_bs_fields,
    resolve_aggregate,
    resolve_item,
    derive_subtraction,
)
from blue_ticker.constants.xbrl import ALL_STANDARD_BS_ITEMS, USGAAP_HTML_NCA_COMPONENTS, USGAAP_XBRL_NCA_COMPONENTS
from blue_ticker.utils.xbrl_result_types import BalanceSheetResult, MetricComponent, XbrlTagElements


def _detect_accounting_standard(field_set: FieldSet) -> str:
    has_usgaap = any("USGAAP" in tag for tag in field_set)
    has_ifrs = any("IFRS" in tag for tag in field_set)
    if has_usgaap and not has_ifrs:
        return "US-GAAP"
    if has_ifrs:
        return "IFRS"
    return "J-GAAP"


def _build_field_set(xbrl_dir: Path, pre_parsed: XbrlTagElements | None) -> FieldSet:
    field_set = (
        field_set_from_pre_parsed(pre_parsed)
        if pre_parsed is not None
        else parse_instant_fields(xbrl_dir)
    )
    if any("USGAAP" in tag for tag in field_set):
        field_set.update(parse_usgaap_html_bs_fields(xbrl_dir))
    return field_set


def extract_balance_sheet(
    xbrl_dir: Path,
    *,
    pre_parsed: XbrlTagElements | None = None,
) -> BalanceSheetResult:
    """XBRLディレクトリから主要な貸借対照表項目を抽出する。"""
    field_set = _build_field_set(xbrl_dir, pre_parsed)
    accounting_standard = _detect_accounting_standard(field_set)

    components: list[MetricComponent] = []
    label_to_value: dict[str, float | None] = {}

    for item_def in ALL_STANDARD_BS_ITEMS:
        resolved = resolve_item(field_set, item_def["tags"])
        if resolved["tag"] is None and "derive" in item_def:
            d = item_def["derive"]
            resolved = derive_subtraction(field_set, d["minuend_tags"], d["subtrahend_tags"])
        if item_def["field"] == "NonCurrentAssets" and resolved["current"] is None:
            resolved = resolve_aggregate(field_set, USGAAP_HTML_NCA_COMPONENTS)
        if item_def["field"] == "NonCurrentAssets" and resolved["current"] is None:
            resolved = resolve_aggregate(field_set, USGAAP_XBRL_NCA_COMPONENTS)

        components.append({
            "label": item_def["label"],
            "tag": resolved["tag"],
            "current": resolved["current"],
            "prior": resolved["prior"],
        })
        label_to_value[item_def["label"]] = resolved["current"]

    total_assets = label_to_value.get("資産合計")
    current_assets = label_to_value.get("流動資産")
    non_current_assets = label_to_value.get("非流動資産")
    current_liabilities = label_to_value.get("流動負債")
    non_current_liabilities = label_to_value.get("非流動負債")
    net_assets = label_to_value.get("純資産/資本合計")

    has_any = any(
        v is not None
        for v in [total_assets, current_assets, non_current_assets,
                  current_liabilities, non_current_liabilities, net_assets]
    )

    result: BalanceSheetResult = {
        "total_assets": total_assets,
        "current_assets": current_assets,
        "non_current_assets": non_current_assets,
        "current_liabilities": current_liabilities,
        "non_current_liabilities": non_current_liabilities,
        "net_assets": net_assets,
        "accounting_standard": accounting_standard,
        "method": "field_parser" if has_any else "not_found",
        "components": components,
    }
    if not has_any:
        result["reason"] = "貸借対照表タグが見つからない"
    return result
