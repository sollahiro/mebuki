"""
営業利益・経常利益 XBRL抽出モジュール

抽出優先順:
  1. 営業利益（IFRS: OperatingProfitLossIFRS / J-GAAP: OperatingIncomeLoss → OperatingIncome）
     連結優先、連結タグがなければ個別にフォールバック
  2. 経常利益（J-GAAP: OrdinaryIncome）— 金融機関向けフォールバック
  3. US-GAAP: 連結損益計算書HTML(0105010/0105020)から抽出
"""

import re
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
    GROSS_PROFIT_DIRECT_TAGS,
    OPERATING_PROFIT_DIRECT_TAGS,
    ORDINARY_INCOME_TAGS,
    ORDINARY_REVENUE_TAGS,
    SGA_DIRECT_TAGS,
)
from blue_ticker.utils.xbrl_result_types import OperatingProfitResult


def _extract_usgaap_op_from_html(xbrl_dir: Path) -> OperatingProfitResult | None:
    if not _BS4_AVAILABLE:
        return None

    candidates = sorted(xbrl_dir.rglob("*.htm")) + sorted(xbrl_dir.rglob("*.html"))
    target_file = None
    for priority in ("0105010", "0105020"):
        for f in candidates:
            if priority in f.name:
                target_file = f
                break
        if target_file:
            break
    if target_file is None:
        return None

    content = target_file.read_text(encoding="utf-8", errors="ignore")
    search_labels = [("営業利益", "operating_profit", "営業利益"), ("経常利益", "ordinary_income", "経常利益")]
    found: tuple[str, str, str] | None = None
    for label_text, method, label in search_labels:
        if label_text in content:
            found = (label_text, method, label)
            break
    if found is None:
        return None
    found_text, _found_method, found_label = found

    soup = BeautifulSoup(content, "html.parser")
    _HEADER_MARKERS = ("前連結", "当連結", "前期", "当期", "第")

    for table in soup.find_all("table"):
        if found_text not in table.get_text():
            continue
        rows = table.find_all("tr")
        if not rows:
            continue

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
                last_col = col_offset + span - 1
                if "当連結" in text or "当期" in text:
                    current_col_idx = last_col
                elif "前連結" in text or "前期" in text:
                    prior_col_idx = last_col
                elif re.search(r"第\d+期", text):
                    # 「第N期」形式: colspan 内の先頭列（金額列）を使う。出現順に前期→当期。
                    if prior_col_idx is None:
                        prior_col_idx = col_offset
                    else:
                        current_col_idx = col_offset
                col_offset += span
            if current_col_idx is not None:
                break

        for row in rows:
            cells = row.find_all(["td", "th"])
            if not cells:
                continue
            if found_text not in cells[0].get_text(strip=True):
                continue

            numerics = [
                (i, parse_html_number(c.get_text(strip=True)))
                for i, c in enumerate(cells)
                if i > 0 and parse_html_number(c.get_text(strip=True)) is not None
            ]
            if len(numerics) < 2:
                continue

            if prior_col_idx is not None and current_col_idx is not None:
                def _nearest(target_col):
                    best_val, best_dist = None, float("inf")
                    for i, v in numerics:
                        d = abs(i - target_col)
                        if d < best_dist:
                            best_dist, best_val = d, v
                    return best_val if best_dist <= 2 else None
                prior_val = _nearest(prior_col_idx)
                current_val = _nearest(current_col_idx)
            else:
                prior_val = numerics[0][1]
                current_val = numerics[-1][1]

            def _to_yen(v: float | None) -> float | None:
                return v * MILLION_YEN if v is not None else None

            return {
                "current": _to_yen(current_val),
                "prior": _to_yen(prior_val),
                "method": "usgaap_html",
                "label": found_label,
                "accounting_standard": "US-GAAP",
            }

    return None


def extract_operating_profit(section: IncomeStatementSection) -> OperatingProfitResult:
    """
    損益計算書セクションから営業利益（または経常利益）を抽出する。

    金融機関など営業利益が存在しない場合は経常利益にフォールバックする。

    Returns:
        {
            "current": float | None,
            "prior":   float | None,
            "method":  "direct" | "ordinary_income" | "usgaap_html" | "not_found",
            "label":   "営業利益" | "経常利益",
            "accounting_standard": str,
            "reason":  str | None,   # not_found 時のみ
        }
    """
    accounting_standard = section.accounting_standard

    if accounting_standard == "US-GAAP":
        if section.xbrl_dir is not None:
            usgaap_result = _extract_usgaap_op_from_html(section.xbrl_dir)
            if usgaap_result is not None:
                return usgaap_result
        return {
            "current": None, "prior": None,
            "method": "not_found", "label": "営業利益",
            "accounting_standard": "US-GAAP",
            "reason": "US-GAAP 連結損益計算書 HTML で営業利益・経常利益を取得できない",
        }

    # 直接法: OPERATING_PROFIT_DIRECT_TAGS
    op_item = section.resolve(OPERATING_PROFIT_DIRECT_TAGS)
    if op_item["tag"] is not None:
        sga_item = section.resolve(SGA_DIRECT_TAGS)
        result: OperatingProfitResult = {
            "current": op_item["current"], "prior": op_item["prior"],
            "method": "direct", "label": "営業利益",
            "accounting_standard": accounting_standard,
        }
        if sga_item["tag"] is not None:
            result["current_sga"] = sga_item["current"]
            result["prior_sga"] = sga_item["prior"]
        return result

    # 計算法: GrossProfit - SGA（OperatingProfitLossIFRS が存在しない IFRS 企業向け）
    computed = section.derive_subtraction(GROSS_PROFIT_DIRECT_TAGS, SGA_DIRECT_TAGS)
    if computed["current"] is not None or computed["prior"] is not None:
        sga_item = section.resolve(SGA_DIRECT_TAGS)
        result = {
            "current": computed["current"], "prior": computed["prior"],
            "method": "computed", "label": "営業利益",
            "accounting_standard": accounting_standard,
        }
        if sga_item["tag"] is not None:
            result["current_sga"] = sga_item["current"]
            result["prior_sga"] = sga_item["prior"]
        return result

    # 経常利益フォールバック（J-GAAP 金融機関向け）
    # IFRS企業では連結コンテキストに経常利益タグが残存しても使わない。
    # _apply_net_revenue が BusinessProfitIFRSSummaryOfBusinessResults を使うため。
    if accounting_standard == "IFRS":
        return {
            "current": None, "prior": None,
            "method": "not_found", "label": "営業利益",
            "accounting_standard": accounting_standard,
            "reason": "IFRS企業では経常利益フォールバックを適用しない",
        }
    oi_item = section.resolve(ORDINARY_INCOME_TAGS)
    if oi_item["tag"] is not None:
        ordinary_result: OperatingProfitResult = {
            "current": oi_item["current"], "prior": oi_item["prior"],
            "method": "ordinary_income", "label": "経常利益",
            "accounting_standard": accounting_standard,
        }
        sales_item = section.resolve(ORDINARY_REVENUE_TAGS)
        if sales_item["tag"] is not None:
            ordinary_result["current_sales"] = sales_item["current"]
            ordinary_result["prior_sales"] = sales_item["prior"]
        return ordinary_result

    return {
        "current": None, "prior": None,
        "method": "not_found", "label": "営業利益",
        "accounting_standard": accounting_standard,
        "reason": "営業利益・経常利益タグが見つからない",
    }
