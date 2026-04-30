"""
営業利益・経常利益 XBRL抽出モジュール

抽出優先順:
  1. 営業利益（IFRS: OperatingProfitLossIFRS / J-GAAP: OperatingIncomeLoss → OperatingIncome）
     連結優先、連結タグがなければ個別にフォールバック
  2. 経常利益（J-GAAP: OrdinaryIncome）— 金融機関向けフォールバック
  3. US-GAAP: 連結損益計算書HTML(0105010/0105020)から抽出
"""

from pathlib import Path
from typing import Any

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
)
from mebuki.analysis.xbrl_utils import collect_numeric_elements, find_xbrl_files, parse_html_number
from mebuki.constants.financial import MILLION_YEN
from mebuki.constants.xbrl import OPERATING_PROFIT_DIRECT_TAGS, ORDINARY_INCOME_TAGS

_OP_RELEVANT_TAGS: frozenset[str] = frozenset(
    OPERATING_PROFIT_DIRECT_TAGS
    + ORDINARY_INCOME_TAGS
    + [
        "TotalAssetsUSGAAPSummaryOfBusinessResults",
        "EquityAttributableToOwnersOfParentUSGAAPSummaryOfBusinessResults",
        "InterestBearingLiabilitiesCLIFRS",
        "BorrowingsCLIFRS",
        "BondsPayableNCLIFRS",
        "BorrowingsNCLIFRS",
    ]
)


def _find_duration_value(
    tag_elements: dict, tag: str, consolidated: bool
) -> tuple[float | None, float | None]:
    if tag not in tag_elements:
        return None, None
    is_cur = _is_consolidated_duration if consolidated else _is_nonconsolidated_duration
    is_pri = _is_consolidated_prior_duration if consolidated else _is_nonconsolidated_prior_duration
    current = prior = None
    for ctx, val in tag_elements[tag].items():
        if is_cur(ctx):
            current = val
        elif is_pri(ctx):
            prior = val
    return current, prior


def _try_tags(
    tag_elements: dict, tags: list[str], consolidated: bool
) -> tuple[str | None, float | None, float | None]:
    """指定した連結/個別モードでタグリストを試す。"""
    for tag in tags:
        c, p = _find_duration_value(tag_elements, tag, consolidated)
        if c is not None or p is not None:
            return tag, c, p
    return None, None, None


def _detect_accounting_standard(tag_elements: dict) -> str:
    usgaap_tags = {
        "TotalAssetsUSGAAPSummaryOfBusinessResults",
        "EquityAttributableToOwnersOfParentUSGAAPSummaryOfBusinessResults",
    }
    ifrs_markers = [
        "InterestBearingLiabilitiesCLIFRS",
        "BorrowingsCLIFRS",
        "BondsPayableNCLIFRS",
        "BorrowingsNCLIFRS",
    ]
    if any(t in tag_elements for t in usgaap_tags) and not any(
        t in tag_elements for t in ifrs_markers
    ):
        return "US-GAAP"
    if any(t in tag_elements for t in ifrs_markers):
        return "IFRS"
    return "J-GAAP"


def _extract_usgaap_op_from_html(xbrl_dir: Path) -> dict | None:
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
    found_text = found_method = found_label = None
    for label_text, method, label in search_labels:
        if label_text in content:
            found_text, found_method, found_label = label_text, method, label
            break
    if found_text is None:
        return None

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
                span = int(cell.get("colspan", 1))
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


def extract_operating_profit(xbrl_dir: Path, *, pre_parsed: dict | None = None) -> dict[str, Any]:
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
        tag_elements: dict = {tag: ctx for tag, ctx in pre_parsed.items() if tag in _OP_RELEVANT_TAGS}
    else:
        tag_elements = {}
        for f in find_xbrl_files(xbrl_dir):
            for tag, ctx_map in collect_numeric_elements(f, allowed_tags=_OP_RELEVANT_TAGS).items():
                if tag not in tag_elements:
                    tag_elements[tag] = {}
                tag_elements[tag].update(ctx_map)

    accounting_standard = _detect_accounting_standard(tag_elements)

    if accounting_standard == "US-GAAP":
        result = _extract_usgaap_op_from_html(xbrl_dir)
        if result is not None:
            return result
        return {
            "current": None, "prior": None,
            "method": "not_found", "label": "営業利益",
            "accounting_standard": "US-GAAP",
            "reason": "US-GAAP 連結損益計算書 HTML で営業利益・経常利益を取得できない",
        }

    # 連結優先、非連結フォールバック。連結スコープを確定してから個別に落ちる。
    for consolidated in (True, False):
        _, current, prior = _try_tags(tag_elements, OPERATING_PROFIT_DIRECT_TAGS, consolidated)
        if current is not None or prior is not None:
            return {
                "current": current, "prior": prior,
                "method": "direct", "label": "営業利益",
                "accounting_standard": accounting_standard,
            }
        _, current, prior = _try_tags(tag_elements, ORDINARY_INCOME_TAGS, consolidated)
        if current is not None or prior is not None:
            return {
                "current": current, "prior": prior,
                "method": "ordinary_income", "label": "経常利益",
                "accounting_standard": accounting_standard,
            }

    return {
        "current": None, "prior": None,
        "method": "not_found", "label": "営業利益",
        "accounting_standard": accounting_standard,
        "reason": "営業利益・経常利益タグが見つからない",
    }
