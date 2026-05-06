"""
営業利益・経常利益 XBRL抽出モジュール

抽出優先順:
  1. 営業利益（IFRS: OperatingProfitLossIFRS / J-GAAP: OperatingIncomeLoss → OperatingIncome）
     連結優先、連結タグがなければ個別にフォールバック
  2. 経常利益（J-GAAP: OrdinaryIncome）— 金融機関向けフォールバック
  3. US-GAAP: 連結損益計算書HTML(0105010/0105020)から抽出
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
    collect_numeric_elements,
    find_xbrl_files,
    parse_html_int_attribute,
    parse_html_number,
)
from mebuki.constants.financial import MILLION_YEN
from mebuki.constants.xbrl import (
    DURATION_CONTEXT_PATTERNS,
    GROSS_PROFIT_DIRECT_TAGS,
    IFRS_PL_MARKER_TAGS,
    OPERATING_PROFIT_DIRECT_TAGS,
    ORDINARY_REVENUE_TAGS,
    ORDINARY_INCOME_TAGS,
    PRIOR_DURATION_CONTEXT_PATTERNS,
    SGA_DIRECT_TAGS,
    USGAAP_MARKER_TAGS,
)
from mebuki.utils.xbrl_result_types import OperatingProfitResult, XbrlTagElements

_OP_RELEVANT_TAGS: frozenset[str] = frozenset(
    OPERATING_PROFIT_DIRECT_TAGS
    + ORDINARY_INCOME_TAGS
    + ORDINARY_REVENUE_TAGS
    + GROSS_PROFIT_DIRECT_TAGS
    + SGA_DIRECT_TAGS
    + USGAAP_MARKER_TAGS
    + IFRS_PL_MARKER_TAGS
)


def _find_duration_value(
    tag_elements: XbrlTagElements, tag: str, consolidated: bool
) -> tuple[float | None, float | None]:
    if tag not in tag_elements:
        return None, None
    is_cur = _is_consolidated_duration if consolidated else _is_nonconsolidated_duration
    is_pri = _is_consolidated_prior_duration if consolidated else _is_nonconsolidated_prior_duration
    current = prior = None
    current_pure = prior_pure = None
    current_patterns = DURATION_CONTEXT_PATTERNS
    prior_patterns = PRIOR_DURATION_CONTEXT_PATTERNS
    is_pure = _is_pure_context if consolidated else _is_pure_nonconsolidated_context
    for ctx, val in tag_elements[tag].items():
        if is_cur(ctx):
            if is_pure(ctx, current_patterns):
                current_pure = val
            else:
                current = val
        elif is_pri(ctx):
            if is_pure(ctx, prior_patterns):
                prior_pure = val
            else:
                prior = val
    return (
        current_pure if current_pure is not None else current,
        prior_pure if prior_pure is not None else prior,
    )


def _try_tags(
    tag_elements: XbrlTagElements, tags: list[str], consolidated: bool
) -> tuple[str | None, float | None, float | None]:
    """指定した連結/個別モードでタグリストを試す。"""
    for tag in tags:
        c, p = _find_duration_value(tag_elements, tag, consolidated)
        if c is not None or p is not None:
            return tag, c, p
    return None, None, None


def _extract_ordinary_revenue(tag_elements: XbrlTagElements) -> tuple[float | None, float | None]:
    """金融機関向けに経常収益の当期・前期値を返す。"""
    for consolidated in (True, False):
        for tag in ORDINARY_REVENUE_TAGS:
            current, prior = _find_duration_value(tag_elements, tag, consolidated)
            if current is not None or prior is not None:
                return current, prior
    return None, None


def _try_sga(
    tag_elements: XbrlTagElements, consolidated: bool
) -> tuple[float | None, float | None]:
    """販管費の当期・前期を取得する。"""
    for tag in SGA_DIRECT_TAGS:
        c, p = _find_duration_value(tag_elements, tag, consolidated)
        if c is not None or p is not None:
            return c, p
    return None, None


def _try_computed_op(
    tag_elements: XbrlTagElements, consolidated: bool
) -> tuple[float | None, float | None, float | None, float | None]:
    """GrossProfit - SGA で営業利益の当期・前期を計算する。

    OperatingProfitLossIFRS が存在しない IFRS 企業（日立等）向けフォールバック。
    """
    gp_c = gp_p = None
    for tag in GROSS_PROFIT_DIRECT_TAGS:
        c, p = _find_duration_value(tag_elements, tag, consolidated)
        if c is not None or p is not None:
            gp_c, gp_p = c, p
            break

    sga_c, sga_p = _try_sga(tag_elements, consolidated)

    current = (gp_c - sga_c) if gp_c is not None and sga_c is not None else None
    prior = (gp_p - sga_p) if gp_p is not None and sga_p is not None else None
    return current, prior, sga_c, sga_p


def _detect_accounting_standard(tag_elements: XbrlTagElements) -> str:
    if any(t in tag_elements for t in USGAAP_MARKER_TAGS) and not any(
        t in tag_elements for t in IFRS_PL_MARKER_TAGS
    ):
        return "US-GAAP"
    if any(t in tag_elements for t in IFRS_PL_MARKER_TAGS):
        return "IFRS"
    return "J-GAAP"


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


def extract_operating_profit(
    xbrl_dir: Path,
    *,
    pre_parsed: XbrlTagElements | None = None,
) -> OperatingProfitResult:
    """
    XBRLディレクトリから連結損益計算書の営業利益（または経常利益）を抽出する。

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
    if pre_parsed is not None:
        tag_elements: XbrlTagElements = {
            tag: ctx for tag, ctx in pre_parsed.items() if tag in _OP_RELEVANT_TAGS
        }
    else:
        tag_elements = {}
        for f in find_xbrl_files(xbrl_dir):
            for tag, ctx_map in collect_numeric_elements(f, allowed_tags=_OP_RELEVANT_TAGS).items():
                if tag not in tag_elements:
                    tag_elements[tag] = {}
                tag_elements[tag].update(ctx_map)

    accounting_standard = _detect_accounting_standard(tag_elements)

    if accounting_standard == "US-GAAP":
        usgaap_result = _extract_usgaap_op_from_html(xbrl_dir)
        if usgaap_result is not None:
            return usgaap_result
        return {
            "current": None, "prior": None,
            "method": "not_found", "label": "営業利益",
            "accounting_standard": "US-GAAP",
            "reason": "US-GAAP 連結損益計算書 HTML で営業利益・経常利益を取得できない",
        }

    # 連結優先、非連結フォールバック。
    # 各スコープで: 直接法 → 計算法(GP-SGA) → 経常利益 の順に試みる。
    for consolidated in (True, False):
        _, current, prior = _try_tags(tag_elements, OPERATING_PROFIT_DIRECT_TAGS, consolidated)
        if current is not None or prior is not None:
            sga_c, sga_p = _try_sga(tag_elements, consolidated)
            result: OperatingProfitResult = {
                "current": current, "prior": prior,
                "method": "direct", "label": "営業利益",
                "accounting_standard": accounting_standard,
            }
            if sga_c is not None or sga_p is not None:
                result["current_sga"] = sga_c
                result["prior_sga"] = sga_p
            return result

        current, prior, sga_c, sga_p = _try_computed_op(tag_elements, consolidated)
        if current is not None or prior is not None:
            result = {
                "current": current, "prior": prior,
                "method": "computed", "label": "営業利益",
                "accounting_standard": accounting_standard,
            }
            if sga_c is not None or sga_p is not None:
                result["current_sga"] = sga_c
                result["prior_sga"] = sga_p
            return result

        _, current, prior = _try_tags(tag_elements, ORDINARY_INCOME_TAGS, consolidated)
        if current is not None or prior is not None:
            ordinary_result: OperatingProfitResult = {
                "current": current, "prior": prior,
                "method": "ordinary_income", "label": "経常利益",
                "accounting_standard": accounting_standard,
            }
            sales_c, sales_p = _extract_ordinary_revenue(tag_elements)
            if sales_c is not None or sales_p is not None:
                ordinary_result["current_sales"] = sales_c
                ordinary_result["prior_sales"] = sales_p
            return ordinary_result

    return {
        "current": None, "prior": None,
        "method": "not_found", "label": "営業利益",
        "accounting_standard": accounting_standard,
        "reason": "営業利益・経常利益タグが見つからない",
    }
