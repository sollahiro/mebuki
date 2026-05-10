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

from blue_ticker.analysis.sections import IncomeStatementSection
from blue_ticker.analysis.xbrl_utils import (
    parse_html_int_attribute,
    parse_html_number,
)
from blue_ticker.constants.financial import MILLION_YEN
from blue_ticker.constants.xbrl import (
    BUSINESS_GROSS_PROFIT_COMPONENT_DEFINITIONS,
    GROSS_PROFIT_COMPONENT_DEFINITIONS,
    GROSS_PROFIT_DIRECT_TAGS,
    OPERATING_GROSS_PROFIT_DIRECT_TAGS,
    ORDINARY_REVENUE_TAGS,
)
from blue_ticker.utils.xbrl_result_types import GrossProfitResult, MetricComponent


def _resolve_prefer_both(
    section: IncomeStatementSection, tags: list[str]
) -> tuple[float | None, float | None]:
    """両方（当期・前期）揃うタグを優先し、なければ片側のみでも返す。"""
    partial_c: float | None = None
    partial_p: float | None = None
    for tag in tags:
        if tag not in section:
            continue
        fv = section.field_value(tag)
        if fv is None:
            continue
        c, p = fv["current"], fv["prior"]
        if c is not None and p is not None:
            return c, p
        if (c is not None or p is not None) and partial_c is None and partial_p is None:
            partial_c, partial_p = c, p
    return partial_c, partial_p


def _extract_sales_for_yoy(section: IncomeStatementSection) -> tuple[float | None, float | None]:
    """売上高の当期・前期値を返す（YoY比較用）。当期・前期が両方揃うタグを優先する。"""
    sales_tags = next(
        (comp["tags"] for comp in GROSS_PROFIT_COMPONENT_DEFINITIONS if comp["label"] == "売上高"),
        [],
    ) + ORDINARY_REVENUE_TAGS
    return _resolve_prefer_both(section, sales_tags)


def _extract_business_gross_profit(section: IncomeStatementSection) -> GrossProfitResult | None:
    """銀行等の連結業務粗利益を構成要素から算出する。"""
    comp_results: list[MetricComponent] = []
    current_total = prior_total = 0.0
    has_current = has_prior = False

    for comp_def in BUSINESS_GROSS_PROFIT_COMPONENT_DEFINITIONS:
        item = section.resolve(comp_def["tags"])
        sign = comp_def["sign"]
        if item["current"] is not None:
            current_total += sign * item["current"]
            has_current = True
        if item["prior"] is not None:
            prior_total += sign * item["prior"]
            has_prior = True

        comp_results.append({
            "label": comp_def["label"],
            "tag": item["tag"],
            "current": sign * item["current"] if item["current"] is not None else None,
            "prior": sign * item["prior"] if item["prior"] is not None else None,
        })

    if not has_current and not has_prior:
        return None

    sales_c, sales_p = _extract_sales_for_yoy(section)
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


def extract_gross_profit(section: IncomeStatementSection) -> GrossProfitResult:
    """
    損益計算書セクションから売上総利益を抽出する。

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
    accounting_standard = section.accounting_standard

    # US-GAAP 企業: 連結損益計算書HTML(0105010)から直接解析
    if accounting_standard == "US-GAAP":
        if section.xbrl_dir is not None:
            usgaap_result = _extract_usgaap_gp_from_html(section.xbrl_dir)
            if usgaap_result is not None:
                sales_c, sales_p = _extract_sales_for_yoy(section)
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
    gp_item = section.resolve(GROSS_PROFIT_DIRECT_TAGS)
    if gp_item["tag"] is not None:
        sales_c, sales_p = _extract_sales_for_yoy(section)
        result: GrossProfitResult = {
            "current": gp_item["current"],
            "prior": gp_item["prior"],
            "method": "direct",
            "accounting_standard": accounting_standard,
            "components": [
                {"label": "売上総利益", "tag": gp_item["tag"], "current": gp_item["current"], "prior": gp_item["prior"]}
            ],
        }
        if sales_c is not None or sales_p is not None:
            result["current_sales"] = sales_c
            result["prior_sales"] = sales_p
        return result

    business_gross_profit = _extract_business_gross_profit(section)
    if business_gross_profit is not None:
        return business_gross_profit

    # 直接法: OperatingGrossProfit タグを検索
    ogp_item = section.resolve(OPERATING_GROSS_PROFIT_DIRECT_TAGS)
    if ogp_item["tag"] is not None:
        sales_c, sales_p = _extract_sales_for_yoy(section)
        result = {
            "current": ogp_item["current"],
            "prior": ogp_item["prior"],
            "method": "operating_gross_profit",
            "accounting_standard": accounting_standard,
            "components": [
                {"label": "営業総利益", "tag": ogp_item["tag"], "current": ogp_item["current"], "prior": ogp_item["prior"]}
            ],
        }
        if sales_c is not None or sales_p is not None:
            result["current_sales"] = sales_c
            result["prior_sales"] = sales_p
        return result

    # 計算法: 売上高タグ・売上原価タグをそれぞれ取得して差し引く
    comp_results: list[MetricComponent] = []
    for comp_def in GROSS_PROFIT_COMPONENT_DEFINITIONS:
        item = section.resolve(comp_def["tags"])
        comp_results.append({
            "label": comp_def["label"],
            "tag": item["tag"],
            "current": item["current"],
            "prior": item["prior"],
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
