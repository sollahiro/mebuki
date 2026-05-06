"""
売上総利益 XBRL抽出モジュール

XBRLインスタンス文書から連結損益計算書の売上総利益を抽出する。

定義:
  売上総利益 = 売上高 − 売上原価

タグ体系:
  J-GAAP:   GrossProfit（直接）/ NetSales − CostOfSales（計算）
  IFRS連結:  GrossProfit（直接）/ Revenue − CostOfSales（計算）
  US-GAAP:  連結損益計算書HTML(0105010)から直接解析

抽出戦略:
  1. 直接法: GrossProfit タグを検索
  2. 計算法: 売上高タグ − 売上原価タグ で算出（フォールバック）
  3. US-GAAP: 連結損益計算書HTMLをパースして売上総利益を取得

コンテキスト:
  損益計算書はフロー項目なので Duration コンテキストを使用する。
  （貸借対照表の Instant コンテキストとは異なる点に注意）
"""

from pathlib import Path

try:
    from bs4 import BeautifulSoup
    _BS4_AVAILABLE = True
except ImportError:
    _BS4_AVAILABLE = False

from mebuki.analysis.context_helpers import (
    _is_consolidated_duration,
    _is_consolidated_prior_duration,
    _is_nonconsolidated_duration,
    _is_nonconsolidated_prior_duration,
    _is_pure_context,
    _is_pure_nonconsolidated_context,
)
from mebuki.analysis.xbrl_utils import (
    parse_xbrl_value,
    collect_numeric_elements,
    find_xbrl_files,
    parse_html_int_attribute,
    parse_html_number,
)
from mebuki.constants.financial import MILLION_YEN
from mebuki.constants.xbrl import (
    BUSINESS_GROSS_PROFIT_COMPONENT_DEFINITIONS,
    DURATION_CONTEXT_PATTERNS,
    GROSS_PROFIT_COMPONENT_DEFINITIONS,
    GROSS_PROFIT_DIRECT_TAGS,
    IFRS_PL_MARKER_TAGS,
    OPERATING_GROSS_PROFIT_DIRECT_TAGS,
    ORDINARY_REVENUE_TAGS,
    PRIOR_DURATION_CONTEXT_PATTERNS,
    USGAAP_MARKER_TAGS,
)
from mebuki.utils.xbrl_result_types import GrossProfitResult, MetricComponent, XbrlTagElements

# XBRL解析で収集対象とするローカルタグ名のセット
_GP_RELEVANT_TAGS: frozenset[str] = frozenset(
    GROSS_PROFIT_DIRECT_TAGS
    + OPERATING_GROSS_PROFIT_DIRECT_TAGS
    + [tag for comp in GROSS_PROFIT_COMPONENT_DEFINITIONS for tag in comp["tags"]]
    + [tag for comp in BUSINESS_GROSS_PROFIT_COMPONENT_DEFINITIONS for tag in comp["tags"]]
    + ORDINARY_REVENUE_TAGS
    + USGAAP_MARKER_TAGS
    + IFRS_PL_MARKER_TAGS
)


def _find_consolidated_duration_value(
    tag_elements: XbrlTagElements, tag: str
) -> tuple[float | None, float | None]:
    """指定タグの連結当期・前期（Duration）値を返す。"""
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
    tag_elements: XbrlTagElements, tag: str
) -> tuple[float | None, float | None]:
    """指定タグの個別当期・前期（Duration）値を返す。"""
    if tag not in tag_elements:
        return None, None
    current = prior = None
    current_pure = prior_pure = None
    for ctx, val in tag_elements[tag].items():
        if _is_nonconsolidated_duration(ctx):
            if _is_pure_nonconsolidated_context(ctx, DURATION_CONTEXT_PATTERNS):
                current_pure = val
            else:
                current = val
        elif _is_nonconsolidated_prior_duration(ctx):
            if _is_pure_nonconsolidated_context(ctx, PRIOR_DURATION_CONTEXT_PATTERNS):
                prior_pure = val
            else:
                prior = val
    return (
        current_pure if current_pure is not None else current,
        prior_pure if prior_pure is not None else prior,
    )


def _extract_sales_for_yoy(tag_elements: XbrlTagElements) -> tuple[float | None, float | None]:
    """売上高の当期・前期値を返す（YoY比較用）。連結優先、個別フォールバック。

    当期・前期が両方揃うタグを優先する。両方揃うタグがなければ、
    最初に見つかった片側候補を返す。
    """
    sales_tags = next(
        (comp["tags"] for comp in GROSS_PROFIT_COMPONENT_DEFINITIONS if comp["label"] == "売上高"),
        [],
    ) + ORDINARY_REVENUE_TAGS
    for consolidated in (True, False):
        partial_c: float | None = None
        partial_p: float | None = None
        for tag in sales_tags:
            if consolidated:
                c, p = _find_consolidated_duration_value(tag_elements, tag)
            else:
                c, p = _find_nonconsolidated_duration_value(tag_elements, tag)
            if c is not None and p is not None:
                return c, p
            if (c is not None or p is not None) and partial_c is None and partial_p is None:
                partial_c, partial_p = c, p
        if partial_c is not None or partial_p is not None:
            return partial_c, partial_p
    return None, None


def _extract_business_gross_profit(tag_elements: XbrlTagElements) -> GrossProfitResult | None:
    """銀行等の連結業務粗利益を構成要素から算出する。"""
    comp_results: list[MetricComponent] = []
    current_total = prior_total = 0.0
    has_current = has_prior = False

    for comp_def in BUSINESS_GROSS_PROFIT_COMPONENT_DEFINITIONS:
        found_tag = None
        current = prior = None
        for tag in comp_def["tags"]:
            current, prior = _find_consolidated_duration_value(tag_elements, tag)
            if current is not None or prior is not None:
                found_tag = tag
                break

        sign = comp_def["sign"]
        if current is not None:
            current_total += sign * current
            has_current = True
        if prior is not None:
            prior_total += sign * prior
            has_prior = True

        comp_results.append({
            "label": comp_def["label"],
            "tag": found_tag,
            "current": sign * current if current is not None else None,
            "prior": sign * prior if prior is not None else None,
        })

    if not has_current and not has_prior:
        return None

    sales_c, sales_p = _extract_sales_for_yoy(tag_elements)
    result: GrossProfitResult = {
        "current": current_total if has_current else None,
        "prior": prior_total if has_prior else None,
        "method": "business_gross_profit",
        "accounting_standard": "J-GAAP",
        "components": comp_results,
    }
    if sales_c is not None or sales_p is not None:
        result["current_sales"] = sales_c
        result["prior_sales"] = sales_p
    return result


def _extract_usgaap_gp_from_html(xbrl_dir: Path) -> GrossProfitResult | None:
    """US-GAAP企業の連結損益計算書(0105010)HTMLから売上総利益を抽出する。"""
    if not _BS4_AVAILABLE:
        return None

    target_file = None
    for f in sorted(xbrl_dir.rglob("*.htm")) + sorted(xbrl_dir.rglob("*.html")):
        if "0105010" in f.name:
            target_file = f
            break
    if target_file is None:
        return None

    content = target_file.read_text(encoding="utf-8", errors="ignore")
    if "売上総利益" not in content:
        return None

    soup = BeautifulSoup(content, "html.parser")
    _HEADER_MARKERS = ("前連結", "当連結", "前期", "当期", "第")

    for table in soup.find_all("table"):
        if "売上総利益" not in table.get_text():
            continue

        rows = table.find_all("tr")
        if not rows:
            continue

        # ヘッダー行から列順を決定（colspan展開後の物理列インデックス）
        prior_col_idx = current_col_idx = None
        for row in rows:
            cells = row.find_all(["td", "th"])
            texts = [c.get_text(strip=True) for c in cells]
            if not any(any(m in t for m in _HEADER_MARKERS) for t in texts):
                continue
            col_offset = 0
            for cell in cells:
                text = cell.get_text(strip=True)
                span = parse_html_int_attribute(cell, "colspan")
                # colspan=2 の場合、合計値は右側（最終）列に入る
                last_col = col_offset + span - 1
                if "当連結" in text or "当期" in text:
                    current_col_idx = last_col
                elif "前連結" in text or "前期" in text:
                    prior_col_idx = last_col
                col_offset += span
            if current_col_idx is not None:
                break

        # 売上総利益行を探して値を抽出
        for row in rows:
            cells = row.find_all(["td", "th"])
            if not cells:
                continue
            label = cells[0].get_text(strip=True)
            if "売上総利益" not in label:
                continue

            # 数値付きセル（インデックス, 値）のリスト（ラベル列を除く）
            numerics = [
                (i, parse_html_number(c.get_text(strip=True)))
                for i, c in enumerate(cells)
                if i > 0 and parse_html_number(c.get_text(strip=True)) is not None
            ]
            if len(numerics) < 2:
                continue

            if prior_col_idx is not None and current_col_idx is not None:
                def _find_nearest(target_col):
                    best_val, best_dist = None, float("inf")
                    for i, v in numerics:
                        d = abs(i - target_col)
                        if d < best_dist:
                            best_dist, best_val = d, v
                    return best_val if best_dist <= 2 else None
                prior_val = _find_nearest(prior_col_idx)
                current_val = _find_nearest(current_col_idx)
            else:
                prior_val = numerics[0][1]
                current_val = numerics[-1][1]

            def _to_yen(v: float | None) -> float | None:
                return v * MILLION_YEN if v is not None else None

            return {
                "current": _to_yen(current_val),
                "prior": _to_yen(prior_val),
                "method": "usgaap_html",
                "accounting_standard": "US-GAAP",
                "components": [
                    {
                        "label": "売上総利益",
                        "tag": "USGAAP_GrossProfit",
                        "current": _to_yen(current_val),
                        "prior": _to_yen(prior_val),
                    }
                ],
            }

    return None


def _detect_accounting_standard(tag_elements: XbrlTagElements) -> str:
    """会計基準を判定: 'J-GAAP' | 'IFRS' | 'US-GAAP'"""
    if any(t in tag_elements for t in USGAAP_MARKER_TAGS) and not any(
        t in tag_elements for t in IFRS_PL_MARKER_TAGS
    ):
        return "US-GAAP"
    if any(t in tag_elements for t in IFRS_PL_MARKER_TAGS):
        return "IFRS"
    return "J-GAAP"


def extract_gross_profit(
    xbrl_dir: Path,
    *,
    pre_parsed: XbrlTagElements | None = None,
) -> GrossProfitResult:
    """
    XBRLディレクトリから連結損益計算書の売上総利益を抽出する。

    Returns:
        {
            "current": float | None,      # 当期（円）
            "prior":   float | None,      # 前期（円）
            "method":  str,               # "direct" | "computed" | "business_gross_profit" | "usgaap_html" | "not_found"
            "reason":  str | None,        # not_found 時のみ失敗理由を格納、それ以外は None
            "accounting_standard": str,   # "J-GAAP" | "IFRS" | "US-GAAP"
            "components": [
                {
                    "label": str,
                    "tag":   str | None,
                    "current": float | None,
                    "prior":   float | None,
                }
            ]
        }
    """
    if pre_parsed is not None:
        tag_elements: XbrlTagElements = {
            tag: ctx for tag, ctx in pre_parsed.items() if tag in _GP_RELEVANT_TAGS
        }
    else:
        tag_elements = {}
        for f in find_xbrl_files(xbrl_dir):
            for tag, ctx_map in collect_numeric_elements(f, allowed_tags=_GP_RELEVANT_TAGS).items():
                if tag not in tag_elements:
                    tag_elements[tag] = {}
                tag_elements[tag].update(ctx_map)

    accounting_standard = _detect_accounting_standard(tag_elements)

    # US-GAAP 企業: 連結損益計算書HTML(0105010)から直接解析
    if accounting_standard == "US-GAAP":
        usgaap_result = _extract_usgaap_gp_from_html(xbrl_dir)
        if usgaap_result is not None:
            sales_c, sales_p = _extract_sales_for_yoy(tag_elements)
            if sales_c is not None or sales_p is not None:
                usgaap_result["current_sales"] = sales_c
                usgaap_result["prior_sales"] = sales_p
            return usgaap_result
        return {
            "current": None, "prior": None,
            "method": "not_found", "accounting_standard": "US-GAAP", "components": [],
            "reason": "US-GAAP 連結損益計算書 HTML (0105010) で売上総利益を取得できない",
        }

    # 直接法: GrossProfit タグを検索
    for gp_tag in GROSS_PROFIT_DIRECT_TAGS:
        current, prior = _find_consolidated_duration_value(tag_elements, gp_tag)
        if current is None and prior is None:
            current, prior = _find_nonconsolidated_duration_value(tag_elements, gp_tag)
        if current is not None or prior is not None:
            sales_c, sales_p = _extract_sales_for_yoy(tag_elements)
            result: GrossProfitResult = {
                "current": current,
                "prior": prior,
                "method": "direct",
                "accounting_standard": accounting_standard,
                "components": [
                    {"label": "売上総利益", "tag": gp_tag, "current": current, "prior": prior}
                ],
            }
            if sales_c is not None or sales_p is not None:
                result["current_sales"] = sales_c
                result["prior_sales"] = sales_p
            return result

    business_gross_profit = _extract_business_gross_profit(tag_elements)
    if business_gross_profit is not None:
        return business_gross_profit

    # 直接法: OperatingGrossProfit タグを検索
    for gp_tag in OPERATING_GROSS_PROFIT_DIRECT_TAGS:
        current, prior = _find_consolidated_duration_value(tag_elements, gp_tag)
        if current is None and prior is None:
            current, prior = _find_nonconsolidated_duration_value(tag_elements, gp_tag)
        if current is not None or prior is not None:
            sales_c, sales_p = _extract_sales_for_yoy(tag_elements)
            result: GrossProfitResult = {
                "current": current,
                "prior": prior,
                "method": "operating_gross_profit",
                "accounting_standard": accounting_standard,
                "components": [
                    {"label": "営業総利益", "tag": gp_tag, "current": current, "prior": prior}
                ],
            }
            if sales_c is not None or sales_p is not None:
                result["current_sales"] = sales_c
                result["prior_sales"] = sales_p
            return result

    # 計算法: 売上高タグ・売上原価タグをそれぞれ取得して差し引く
    comp_results: list[MetricComponent] = []
    for comp_def in GROSS_PROFIT_COMPONENT_DEFINITIONS:
        found_tag = None
        current = prior = None
        for tag in comp_def["tags"]:
            c, p = _find_consolidated_duration_value(tag_elements, tag)
            if c is not None or p is not None:
                found_tag = tag
                current, prior = c, p
                break
        comp_results.append({
            "label": comp_def["label"],
            "tag": found_tag,
            "current": current,
            "prior": prior,
        })

    # 連結値が全くなければ個別にフォールバック
    has_consolidated = any(c["current"] is not None or c["prior"] is not None for c in comp_results)
    if not has_consolidated:
        comp_results = []
        for comp_def in GROSS_PROFIT_COMPONENT_DEFINITIONS:
            found_tag = None
            current = prior = None
            for tag in comp_def["tags"]:
                c, p = _find_nonconsolidated_duration_value(tag_elements, tag)
                if c is not None or p is not None:
                    found_tag = tag
                    current, prior = c, p
                    break
            comp_results.append({
                "label": comp_def["label"],
                "tag": found_tag,
                "current": current,
                "prior": prior,
            })

    sales = next((c for c in comp_results if c["label"] == "売上高"), None)
    cogs = next((c for c in comp_results if c["label"] == "売上原価"), None)

    if sales is None or (sales["current"] is None and sales["prior"] is None):
        return {
            "current": None,
            "prior": None,
            "method": "not_found",
            "accounting_standard": accounting_standard,
            "components": comp_results,
            "reason": "売上高タグが見つからない",
        }

    def _subtract(a: float | None, b: float | None) -> float | None:
        if a is None:
            return None
        return a - (b or 0.0)

    cogs_current = cogs["current"] if cogs else None
    cogs_prior = cogs["prior"] if cogs else None
    gp_current = _subtract(sales["current"], cogs_current)
    gp_prior = _subtract(sales["prior"], cogs_prior)

    if gp_current is None and gp_prior is None:
        return {
            "current": None,
            "prior": None,
            "method": "not_found",
            "accounting_standard": accounting_standard,
            "components": comp_results,
            "reason": "売上高タグは存在するが当期・前期ともに値なし",
            "current_sales": sales["current"],
            "prior_sales": sales["prior"],
        }

    return {
        "current": gp_current,
        "prior": gp_prior,
        "method": "computed",
        "accounting_standard": accounting_standard,
        "components": comp_results,
        "current_sales": sales["current"],
        "prior_sales": sales["prior"],
    }
