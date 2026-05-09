"""
貸借対照表（BS）XBRL抽出モジュール

XBRLインスタンス文書から流動資産・固定資産・流動負債・固定負債・純資産を抽出する。
"""

from pathlib import Path

from bs4 import BeautifulSoup

from blue_ticker.analysis.context_helpers import (
    _is_consolidated_instant,
    _is_consolidated_prior_instant,
    _is_nonconsolidated_instant,
    _is_nonconsolidated_prior_instant,
    has_nonconsolidated_contexts,
    _is_pure_nonconsolidated_context,
)
from blue_ticker.analysis.xbrl_utils import collect_numeric_elements, find_xbrl_files, parse_html_number
from blue_ticker.constants.xbrl import (
    BALANCE_SHEET_AGGREGATE_DEFINITIONS,
    BALANCE_SHEET_COMPONENT_DEFINITIONS,
    BALANCE_SHEET_SUBTRACT_DEFINITIONS,
    IFRS_BALANCE_SHEET_MARKER_TAGS,
    INSTANT_CONTEXT_PATTERNS,
    PRIOR_INSTANT_CONTEXT_PATTERNS,
    USGAAP_MARKER_TAGS,
)
from blue_ticker.constants.financial import MILLION_YEN
from blue_ticker.utils.xbrl_result_types import BalanceSheetResult, MetricComponent, XbrlTagElements

_BS_RELEVANT_TAGS: frozenset[str] = frozenset(
    [tag for comp in BALANCE_SHEET_COMPONENT_DEFINITIONS for tag in comp["tags"]]
    + [tag for agg in BALANCE_SHEET_AGGREGATE_DEFINITIONS for tag in agg["tags"]]
    + [tag for sub in BALANCE_SHEET_SUBTRACT_DEFINITIONS for tag in sub["minuend_tags"]]
    + [tag for sub in BALANCE_SHEET_SUBTRACT_DEFINITIONS for tag in sub["subtrahend_tags"]]
    + IFRS_BALANCE_SHEET_MARKER_TAGS
    + USGAAP_MARKER_TAGS
)

_RESULT_FIELD_BY_COMPONENT_FIELD: dict[str, str] = {
    "TotalAssets": "total_assets",
    "CurrentAssets": "current_assets",
    "NonCurrentAssets": "non_current_assets",
    "CurrentLiabilities": "current_liabilities",
    "NonCurrentLiabilities": "non_current_liabilities",
    "NetAssets": "net_assets",
}


def _find_consolidated_value(tag_elements: XbrlTagElements, tag: str) -> tuple[float | None, float | None]:
    """指定タグの連結当期・前期値のみを返す（個別へのフォールバックなし）。"""
    if tag not in tag_elements:
        return None, None
    current = prior = None
    exact_current_contexts = set(INSTANT_CONTEXT_PATTERNS)
    exact_prior_contexts = set(PRIOR_INSTANT_CONTEXT_PATTERNS)
    for ctx, val in tag_elements[tag].items():
        if ctx in exact_current_contexts:
            current = val
        elif ctx in exact_prior_contexts:
            prior = val
    if current is not None or prior is not None:
        return current, prior
    for ctx, val in tag_elements[tag].items():
        if _is_consolidated_instant(ctx):
            current = val
        elif _is_consolidated_prior_instant(ctx):
            prior = val
    return current, prior


def _find_nonconsolidated_value(tag_elements: XbrlTagElements, tag: str) -> tuple[float | None, float | None]:
    """指定タグの個別当期・前期値のみを返す。"""
    if tag not in tag_elements:
        return None, None
    current = prior = None
    current_pure = prior_pure = None
    for ctx, val in tag_elements[tag].items():
        if _is_nonconsolidated_instant(ctx):
            if _is_pure_nonconsolidated_context(ctx, INSTANT_CONTEXT_PATTERNS):
                current_pure = val
            else:
                current = val
        elif _is_nonconsolidated_prior_instant(ctx):
            if _is_pure_nonconsolidated_context(ctx, PRIOR_INSTANT_CONTEXT_PATTERNS):
                prior_pure = val
            else:
                prior = val
    return (
        current_pure if current_pure is not None else current,
        prior_pure if prior_pure is not None else prior,
    )


def _safe_sum(values: list[float | None]) -> float | None:
    found = [v for v in values if v is not None]
    return sum(found) if found else None


def _detect_accounting_standard(tag_elements: XbrlTagElements) -> str:
    if any(tag in IFRS_BALANCE_SHEET_MARKER_TAGS or tag.endswith("IFRS") for tag in tag_elements):
        return "IFRS"
    if any(tag in USGAAP_MARKER_TAGS or "USGAAP" in tag for tag in tag_elements):
        return "US-GAAP"
    return "J-GAAP"


def _collect_tag_elements(xbrl_dir: Path) -> XbrlTagElements:
    tag_elements: XbrlTagElements = {}
    for f in find_xbrl_files(xbrl_dir):
        for tag, ctx_map in collect_numeric_elements(f, allowed_tags=_BS_RELEVANT_TAGS).items():
            if tag not in tag_elements:
                tag_elements[tag] = {}
            tag_elements[tag].update(ctx_map)
    return tag_elements


def _find_first_value(
    tag_elements: XbrlTagElements,
    tags: list[str],
    *,
    consolidated: bool,
) -> tuple[str | None, float | None, float | None]:
    find_value = _find_consolidated_value if consolidated else _find_nonconsolidated_value
    for tag in tags:
        current, prior = find_value(tag_elements, tag)
        if current is not None or prior is not None:
            return tag, current, prior
    return None, None, None


def _aggregate_component(
    tag_elements: XbrlTagElements,
    field: str,
    *,
    consolidated: bool,
) -> tuple[str | None, float | None, float | None]:
    find_value = _find_consolidated_value if consolidated else _find_nonconsolidated_value
    for agg_def in BALANCE_SHEET_AGGREGATE_DEFINITIONS:
        if agg_def["field"] != field:
            continue
        current_values: list[float | None] = []
        prior_values: list[float | None] = []
        found_tags: list[str] = []
        for tag in agg_def["tags"]:
            current, prior = find_value(tag_elements, tag)
            if current is not None or prior is not None:
                found_tags.append(tag)
                current_values.append(current)
                prior_values.append(prior)
        if found_tags:
            return "+".join(found_tags), _safe_sum(current_values), _safe_sum(prior_values)
    return None, None, None


def _subtract_component(
    tag_elements: XbrlTagElements,
    field: str,
    *,
    consolidated: bool,
) -> tuple[str | None, float | None, float | None]:
    for sub_def in BALANCE_SHEET_SUBTRACT_DEFINITIONS:
        if sub_def["field"] != field:
            continue
        minuend_tag, minuend_current, minuend_prior = _find_first_value(
            tag_elements,
            sub_def["minuend_tags"],
            consolidated=consolidated,
        )
        subtrahend_tag, subtrahend_current, subtrahend_prior = _find_first_value(
            tag_elements,
            sub_def["subtrahend_tags"],
            consolidated=consolidated,
        )
        current = (
            minuend_current - subtrahend_current
            if minuend_current is not None and subtrahend_current is not None
            else None
        )
        prior = (
            minuend_prior - subtrahend_prior
            if minuend_prior is not None and subtrahend_prior is not None
            else None
        )
        if current is not None or prior is not None:
            tag = f"{minuend_tag}-{subtrahend_tag}" if minuend_tag is not None and subtrahend_tag is not None else None
            return tag, current, prior
    return None, None, None


def _extract_components(tag_elements: XbrlTagElements, *, consolidated: bool) -> list[MetricComponent]:
    components: list[MetricComponent] = []
    for comp_def in BALANCE_SHEET_COMPONENT_DEFINITIONS:
        tag, current, prior = _find_first_value(tag_elements, comp_def["tags"], consolidated=consolidated)
        method_label = comp_def["label"]
        if current is None and prior is None:
            tag, current, prior = _aggregate_component(tag_elements, comp_def["field"], consolidated=consolidated)
            for agg_def in BALANCE_SHEET_AGGREGATE_DEFINITIONS:
                if agg_def["field"] == comp_def["field"] and tag is not None:
                    found_tags = tag.split("+")
                    method_label = agg_def["label"] if len(found_tags) > 1 else found_tags[0]
                    break
        if current is None and prior is None:
            tag, current, prior = _subtract_component(tag_elements, comp_def["field"], consolidated=consolidated)
            for sub_def in BALANCE_SHEET_SUBTRACT_DEFINITIONS:
                if sub_def["field"] == comp_def["field"] and tag is not None:
                    method_label = sub_def["label"]
                    break
        components.append({
            "label": method_label,
            "tag": tag,
            "current": current,
            "prior": prior,
        })
    return components


def _build_result(
    components: list[MetricComponent],
    accounting_standard: str,
    method: str,
    reason: str | None = None,
) -> BalanceSheetResult:
    values: dict[str, float | None] = {
        "total_assets": None,
        "current_assets": None,
        "non_current_assets": None,
        "current_liabilities": None,
        "non_current_liabilities": None,
        "net_assets": None,
    }
    for comp_def, component in zip(BALANCE_SHEET_COMPONENT_DEFINITIONS, components, strict=True):
        values[_RESULT_FIELD_BY_COMPONENT_FIELD[comp_def["field"]]] = component["current"]

    result: BalanceSheetResult = {
        "total_assets": values["total_assets"],
        "current_assets": values["current_assets"],
        "non_current_assets": values["non_current_assets"],
        "current_liabilities": values["current_liabilities"],
        "non_current_liabilities": values["non_current_liabilities"],
        "net_assets": values["net_assets"],
        "accounting_standard": accounting_standard,
        "method": method,
        "components": components,
    }
    if reason is not None:
        result["reason"] = reason
    return result


_USGAAP_HTML_LABELS: dict[str, list[str]] = {
    "total_assets": ["資産合計"],
    "current_assets": ["流動資産合計"],
    "non_current_assets": ["投資及び長期債権合計", "有形固定資産合計", "その他の資産合計"],
    "current_liabilities": ["流動負債合計"],
    "non_current_liabilities": ["固定負債合計"],
    "net_assets": ["純資産合計"],
}


def _extract_usgaap_html_values(xbrl_dir: Path) -> dict[str, float]:
    html_files = [
        f for f in list(xbrl_dir.rglob("*.htm")) + list(xbrl_dir.rglob("*.html"))
        if "0105010" in f.name
    ]
    if not html_files:
        html_files = list(xbrl_dir.rglob("*.htm")) + list(xbrl_dir.rglob("*.html"))

    for html_file in html_files:
        try:
            soup = BeautifulSoup(html_file.read_text(encoding="utf-8", errors="ignore"), "html.parser")
        except Exception:
            continue
        values: dict[str, float] = {}
        for field, labels in _USGAAP_HTML_LABELS.items():
            field_values: list[float] = []
            for label in labels:
                value = _find_html_row_current_value(soup, label)
                if value is not None:
                    field_values.append(abs(value) * MILLION_YEN)
            if len(field_values) == len(labels):
                values[field] = sum(field_values)
        if values:
            return values
    return {}


def _find_html_row_current_value(soup: BeautifulSoup, label: str) -> float | None:
    for row in soup.find_all("tr"):
        cells = row.find_all(["td", "th"])
        if not cells:
            continue
        texts = [cell.get_text(" ", strip=True).replace("\xa0", " ") for cell in cells]
        if not any(label in text for text in texts):
            continue
        numbers = [parse_html_number(text) for text in texts]
        found = [number for number in numbers if number is not None]
        if found:
            return found[-1]
    return None


def _apply_usgaap_html_fallback(result: BalanceSheetResult, xbrl_dir: Path) -> BalanceSheetResult:
    html_values = _extract_usgaap_html_values(xbrl_dir)
    if not html_values:
        return result
    components = list(result["components"])
    for idx, comp_def in enumerate(BALANCE_SHEET_COMPONENT_DEFINITIONS):
        result_key = _RESULT_FIELD_BY_COMPONENT_FIELD[comp_def["field"]]
        value = html_values.get(result_key)
        if value is None:
            continue
        result[result_key] = value
        components[idx] = {
            "label": comp_def["label"],
            "tag": "usgaap_html",
            "current": value,
            "prior": components[idx]["prior"],
        }
    result["components"] = components
    if any(result[key] is not None for key in _RESULT_FIELD_BY_COMPONENT_FIELD.values()):
        result["method"] = "direct_html" if result["method"] == "not_found" else result["method"]
    return result


def extract_balance_sheet(
    xbrl_dir: Path,
    *,
    pre_parsed: XbrlTagElements | None = None,
) -> BalanceSheetResult:
    """XBRLディレクトリから主要な貸借対照表項目を抽出する。"""
    if pre_parsed is not None:
        tag_elements: XbrlTagElements = {tag: ctx for tag, ctx in pre_parsed.items() if tag in _BS_RELEVANT_TAGS}
    else:
        tag_elements = _collect_tag_elements(xbrl_dir)

    check_elements = pre_parsed if pre_parsed is not None else tag_elements
    _blocks_nc = has_nonconsolidated_contexts(check_elements)

    accounting_standard = _detect_accounting_standard(tag_elements)
    components = _extract_components(tag_elements, consolidated=True)
    if not any(c["current"] is not None or c["prior"] is not None for c in components) and not _blocks_nc:
        components = _extract_components(tag_elements, consolidated=False)

    if not any(c["current"] is not None or c["prior"] is not None for c in components):
        result = _build_result(
            components,
            accounting_standard,
            "not_found",
            "貸借対照表タグが見つからない",
        )
        return _apply_usgaap_html_fallback(result, xbrl_dir)

    result = _build_result(components, accounting_standard, "direct")
    if result["total_assets"] is None and result["current_assets"] is not None and result["non_current_assets"] is not None:
        result["total_assets"] = result["current_assets"] + result["non_current_assets"]
    if accounting_standard == "US-GAAP":
        return _apply_usgaap_html_fallback(result, xbrl_dir)
    return result
