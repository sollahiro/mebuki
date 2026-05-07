"""
支払利息 XBRL抽出モジュール

XBRLインスタンス文書から連結損益計算書の支払利息（金融費用）を抽出する。

タグ体系:
  J-GAAP:  InterestExpensesNOE（営業外費用の支払利息）
  IFRS:    FinanceCostsIFRS（金融費用）
  US-GAAP: 連結損益計算書HTML(0105010)から「支払利息」行を解析

コンテキスト:
  損益計算書はフロー項目なので Duration コンテキストを使用する。
"""

from pathlib import Path
import html
import re

try:
    from bs4 import BeautifulSoup
    _BS4_AVAILABLE = True
except ImportError:
    _BS4_AVAILABLE = False

from blue_ticker.analysis.context_helpers import (
    _is_consolidated_duration,
    _is_consolidated_prior_duration,
    _is_nonconsolidated_duration,
    _is_nonconsolidated_prior_duration,
    _is_pure_context,
    _is_pure_nonconsolidated_context,
)
from blue_ticker.utils.xbrl_result_types import InterestExpenseResult, XbrlTagElements
from blue_ticker.analysis.xbrl_utils import (
    collect_numeric_elements,
    find_xbrl_files,
    parse_html_int_attribute,
    parse_html_number,
)
from blue_ticker.constants.financial import MILLION_YEN
from blue_ticker.constants.xbrl import (
    DURATION_CONTEXT_PATTERNS,
    IFRS_INTEREST_EXPENSE_MARKER_TAGS,
    INTEREST_EXPENSE_IFRS_TAGS,
    INTEREST_EXPENSE_JGAAP_TAGS,
    PRIOR_DURATION_CONTEXT_PATTERNS,
    USGAAP_MARKER_TAGS,
)

_IE_RELEVANT_TAGS: frozenset[str] = frozenset(
    INTEREST_EXPENSE_JGAAP_TAGS
    + INTEREST_EXPENSE_IFRS_TAGS
    + USGAAP_MARKER_TAGS
    + IFRS_INTEREST_EXPENSE_MARKER_TAGS
)


def _find_consolidated_duration_value(
    tag_elements: XbrlTagElements, tag: str
) -> tuple[float | None, float | None]:
    """連結当期・前期の値を返す。純コンテキスト（セグメント修飾なし）を優先する。"""
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
    """個別当期・前期の値を返す。純コンテキストを優先する。"""
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


def _detect_accounting_standard(tag_elements: XbrlTagElements) -> str:
    """会計基準を判定: 'J-GAAP' | 'IFRS' | 'US-GAAP'"""
    if any(t in tag_elements for t in USGAAP_MARKER_TAGS) and not any(
        t in tag_elements for t in IFRS_INTEREST_EXPENSE_MARKER_TAGS
    ):
        return "US-GAAP"
    if any(t in tag_elements for t in IFRS_INTEREST_EXPENSE_MARKER_TAGS):
        return "IFRS"
    return "J-GAAP"


def _extract_usgaap_ie_from_html(xbrl_dir: Path) -> InterestExpenseResult | None:
    """US-GAAP企業の連結損益計算書(0105010)HTMLから支払利息を抽出する。"""
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
    if "支払利息" not in content:
        return None

    soup = BeautifulSoup(content, "html.parser")
    _HEADER_MARKERS = ("前連結", "当連結", "前期", "当期", "第")

    for table in soup.find_all("table"):
        if "支払利息" not in table.get_text():
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
                if "当連結" in text or ("当期" in text and "前期" not in text):
                    current_col_idx = last_col
                elif "前連結" in text or "前期" in text:
                    prior_col_idx = last_col
                col_offset += span
            if current_col_idx is not None:
                break

        for row in rows:
            cells = row.find_all(["td", "th"])
            if not cells:
                continue
            label = cells[0].get_text(strip=True)
            if "支払利息" not in label:
                continue
            if any(kw in label for kw in ["受取", "未払"]):
                continue

            numerics = [
                (i, parse_html_number(c.get_text(strip=True)))
                for i, c in enumerate(cells)
                if i > 0 and parse_html_number(c.get_text(strip=True)) is not None
            ]
            if not numerics:
                continue

            if prior_col_idx is not None and current_col_idx is not None:
                def _find_nearest(target_col, _nums=numerics):
                    best_val, best_dist = None, float("inf")
                    for i, v in _nums:
                        d = abs(i - target_col)
                        if d < best_dist:
                            best_dist, best_val = d, v
                    return best_val if best_dist <= 2 else None
                prior_val = _find_nearest(prior_col_idx)
                current_val = _find_nearest(current_col_idx)
            else:
                prior_val = numerics[0][1] if len(numerics) >= 2 else None
                current_val = numerics[-1][1]

            if current_val is None and prior_val is None:
                continue

            # 支払利息は P&L 上 △ で表示されるが費用の絶対値として返す
            return {
                "current": abs(current_val) * MILLION_YEN if current_val is not None else None,
                "prior": abs(prior_val) * MILLION_YEN if prior_val is not None else None,
                "method": "usgaap_html",
                "accounting_standard": "US-GAAP",
            }

    return None


def _extract_ifrs_ie_from_textblock(xbrl_dir: Path) -> InterestExpenseResult | None:
    """IFRS注記テキストブロックから支払利息を抽出する。"""
    # トヨタ自動車のIFRS注記のように、支払利息がnumericタグではなく文章中に出るケースを拾う。
    pattern = re.compile(
        r"支払利息は、.*?それぞれ\s*([0-9,]+)百万円\s*および\s*([0-9,]+)百万円",
        re.DOTALL,
    )

    candidates = sorted(xbrl_dir.rglob("*.htm")) + sorted(xbrl_dir.rglob("*.html")) + sorted(xbrl_dir.rglob("*.xbrl"))
    for file in candidates:
        content = file.read_text(encoding="utf-8", errors="ignore")
        if "支払利息" not in content or "百万円" not in content:
            continue
        text = html.unescape(content)
        if _BS4_AVAILABLE:
            text = BeautifulSoup(text, "html.parser").get_text(" ")
        match = pattern.search(text)
        if not match:
            continue
        prior = float(match.group(1).replace(",", "")) * MILLION_YEN
        current = float(match.group(2).replace(",", "")) * MILLION_YEN
        return {
            "current": current,
            "prior": prior,
            "method": "ifrs_textblock",
            "accounting_standard": "IFRS",
        }
    return None


def extract_interest_expense(
    xbrl_dir: Path,
    *,
    pre_parsed: XbrlTagElements | None = None,
) -> InterestExpenseResult:
    """
    XBRLディレクトリから連結損益計算書の支払利息（金融費用）を抽出する。

    Returns:
        {
            "current": float | None,      # 当期（円）
            "prior":   float | None,      # 前期（円）
            "method":  str,               # "direct" | "not_found"
            "reason":  str | None,        # not_found 時のみ
            "accounting_standard": str,   # "J-GAAP" | "IFRS" | "US-GAAP"
        }
    """
    if pre_parsed is not None:
        tag_elements: XbrlTagElements = {
            tag: ctx for tag, ctx in pre_parsed.items() if tag in _IE_RELEVANT_TAGS
        }
    else:
        tag_elements = {}
        for f in find_xbrl_files(xbrl_dir):
            for tag, ctx_map in collect_numeric_elements(f, allowed_tags=_IE_RELEVANT_TAGS).items():
                if tag not in tag_elements:
                    tag_elements[tag] = {}
                tag_elements[tag].update(ctx_map)

    accounting_standard = _detect_accounting_standard(tag_elements)

    if accounting_standard == "US-GAAP":
        result = _extract_usgaap_ie_from_html(xbrl_dir)
        if result is not None:
            return result
        return {
            "current": None, "prior": None,
            "method": "not_found", "accounting_standard": "US-GAAP",
            "reason": "US-GAAP 連結損益計算書 HTML (0105010) で支払利息を取得できない",
        }

    candidate_tags = (
        INTEREST_EXPENSE_IFRS_TAGS if accounting_standard == "IFRS"
        else INTEREST_EXPENSE_JGAAP_TAGS
    )

    for tag in candidate_tags:
        current, prior = _find_consolidated_duration_value(tag_elements, tag)
        if current is None and prior is None:
            current, prior = _find_nonconsolidated_duration_value(tag_elements, tag)
        if current is not None or prior is not None:
            return {
                "current": current,
                "prior": prior,
                "method": "direct",
                "accounting_standard": accounting_standard,
            }

    result = _extract_ifrs_ie_from_textblock(xbrl_dir)
    if result is not None:
        return result

    return {
        "current": None, "prior": None,
        "method": "not_found", "accounting_standard": accounting_standard,
        "reason": f"{accounting_standard} 支払利息タグが見つからない",
    }
