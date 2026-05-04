"""
減価償却費 XBRL抽出モジュール

XBRLインスタンス文書から連結キャッシュ・フロー計算書の減価償却費を抽出する。

タグ体系:
  J-GAAP: DepreciationAndAmortizationOpeCF
  IFRS:   DepreciationAndAmortizationOpeCFIFRS

コンテキスト:
  CF計算書はフロー項目なので Duration コンテキストを使用する。
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
)
from mebuki.analysis.xbrl_utils import (
    collect_numeric_elements,
    find_xbrl_files,
    parse_html_int_attribute,
    parse_html_number,
)
from mebuki.constants.financial import MILLION_YEN
from mebuki.constants.xbrl import (
    CF_DEPRECIATION_IFRS_TAGS,
    CF_DEPRECIATION_JGAAP_TAGS,
    DURATION_CONTEXT_PATTERNS,
    PRIOR_DURATION_CONTEXT_PATTERNS,
)
from mebuki.utils.xbrl_result_types import DepreciationResult, XbrlTagElements

_CF_DA_RELEVANT_TAGS: frozenset[str] = frozenset(
    CF_DEPRECIATION_JGAAP_TAGS
    + CF_DEPRECIATION_IFRS_TAGS
    + [
        "TotalAssetsUSGAAPSummaryOfBusinessResults",
        "EquityAttributableToOwnersOfParentUSGAAPSummaryOfBusinessResults",
        "InterestBearingLiabilitiesCLIFRS",
        "BorrowingsCLIFRS",
        "BondsPayableNCLIFRS",
        "BorrowingsNCLIFRS",
    ]
)


def _is_pure_context(ctx: str, patterns: list[str]) -> bool:
    return any(ctx == p for p in patterns)


def _find_consolidated_duration_value(
    tag_elements: XbrlTagElements,
    tag: str,
) -> tuple[float | None, float | None]:
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
    tag_elements: XbrlTagElements,
    tag: str,
) -> tuple[float | None, float | None]:
    if tag not in tag_elements:
        return None, None
    current = prior = None
    current_pure = prior_pure = None
    for ctx, val in tag_elements[tag].items():
        if _is_nonconsolidated_duration(ctx):
            if _is_pure_context(ctx, DURATION_CONTEXT_PATTERNS):
                current_pure = val
            else:
                current = val
        elif _is_nonconsolidated_prior_duration(ctx):
            if _is_pure_context(ctx, PRIOR_DURATION_CONTEXT_PATTERNS):
                prior_pure = val
            else:
                prior = val
    return (
        current_pure if current_pure is not None else current,
        prior_pure if prior_pure is not None else prior,
    )


def _detect_accounting_standard(tag_elements: XbrlTagElements) -> str:
    usgaap_tags = {
        "TotalAssetsUSGAAPSummaryOfBusinessResults",
        "EquityAttributableToOwnersOfParentUSGAAPSummaryOfBusinessResults",
    }
    ifrs_marker_tags = [
        "InterestBearingLiabilitiesCLIFRS",
        "BorrowingsCLIFRS",
        "BondsPayableNCLIFRS",
        "BorrowingsNCLIFRS",
        "DepreciationAndAmortizationOpeCFIFRS",  # DA タグ自身で IFRS 判定（集約型 IBD タグしか持たない企業に対応）
    ]
    if any(t in tag_elements for t in usgaap_tags) and not any(
        t in tag_elements for t in ifrs_marker_tags
    ):
        return "US-GAAP"
    if any(t in tag_elements for t in ifrs_marker_tags):
        return "IFRS"
    return "J-GAAP"


def _extract_usgaap_da_from_html(xbrl_dir: Path) -> DepreciationResult | None:
    """US-GAAP企業の連結CF計算書(0105010)HTMLから減価償却費を抽出する。"""
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
    if "減価償却費" not in content or "キャッシュ・フロー" not in content:
        return None

    soup = BeautifulSoup(content, "html.parser")
    header_markers = ("前連結", "当連結", "前期", "当期", "第")

    for table in soup.find_all("table"):
        table_text = table.get_text()
        if "減価償却費" not in table_text or "キャッシュ・フロー" not in table_text:
            continue

        rows = table.find_all("tr")
        if not rows:
            continue

        prior_col_idx = current_col_idx = None
        for row in rows:
            cells = row.find_all(["td", "th"])
            texts = [c.get_text(strip=True) for c in cells]
            if not any(any(m in t for m in header_markers) for t in texts):
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
            if "減価償却費" not in label:
                continue

            numerics = [
                (i, parse_html_number(c.get_text(strip=True)))
                for i, c in enumerate(cells)
                if i > 0 and parse_html_number(c.get_text(strip=True)) is not None
            ]
            if not numerics:
                continue

            if prior_col_idx is not None and current_col_idx is not None:
                def _find_nearest(
                    target_col: int,
                    _nums: list[tuple[int, float]] = numerics,
                ) -> float | None:
                    best_val: float | None = None
                    best_dist = float("inf")
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

            return {
                "current": current_val * MILLION_YEN if current_val is not None else None,
                "prior": prior_val * MILLION_YEN if prior_val is not None else None,
                "method": "usgaap_html",
                "accounting_standard": "US-GAAP",
            }

    return None


def extract_depreciation(
    xbrl_dir: Path,
    *,
    pre_parsed: XbrlTagElements | None = None,
) -> DepreciationResult:
    """
    XBRLディレクトリから連結CF計算書の減価償却費を抽出する。

    Returns:
        {
            "current": float | None,
            "prior":   float | None,
            "method":  str,
            "accounting_standard": str,
        }
    """
    if pre_parsed is not None:
        tag_elements: XbrlTagElements = {
            tag: ctx for tag, ctx in pre_parsed.items() if tag in _CF_DA_RELEVANT_TAGS
        }
    else:
        tag_elements = {}
        for file_path in find_xbrl_files(xbrl_dir):
            for tag, ctx_map in collect_numeric_elements(
                file_path,
                allowed_tags=_CF_DA_RELEVANT_TAGS,
            ).items():
                if tag not in tag_elements:
                    tag_elements[tag] = {}
                tag_elements[tag].update(ctx_map)

    accounting_standard = _detect_accounting_standard(tag_elements)

    if accounting_standard == "US-GAAP":
        result = _extract_usgaap_da_from_html(xbrl_dir)
        if result is not None:
            return result
        return {
            "current": None,
            "prior": None,
            "method": "not_found",
            "accounting_standard": "US-GAAP",
            "reason": "US-GAAP 連結CF計算書 HTML (0105010) で減価償却費を取得できない",
        }

    candidate_tags = (
        CF_DEPRECIATION_IFRS_TAGS
        if accounting_standard == "IFRS"
        else CF_DEPRECIATION_JGAAP_TAGS
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

    return {
        "current": None,
        "prior": None,
        "method": "not_found",
        "accounting_standard": accounting_standard,
        "reason": f"{accounting_standard} 減価償却費タグが見つからない",
    }
