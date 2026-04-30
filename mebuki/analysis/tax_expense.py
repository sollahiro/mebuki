"""
実効税率 XBRL抽出モジュール

XBRLインスタンス文書から連結損益計算書の税引前利益・法人税等を抽出し、
実効税率を計算する。

タグ体系:
  J-GAAP:  IncomeBeforeIncomeTaxes / IncomeTaxes
  IFRS:    ProfitLossBeforeTaxIFRS / IncomeTaxExpenseIFRS
  US-GAAP: 連結損益計算書HTML(0105010)から「税引前当期純利益」「法人税等合計」行を解析
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
from mebuki.analysis.xbrl_utils import collect_numeric_elements, find_xbrl_files, parse_html_number
from mebuki.constants.financial import MILLION_YEN
from mebuki.constants.xbrl import (
    DURATION_CONTEXT_PATTERNS,
    INCOME_TAX_IFRS_TAGS,
    INCOME_TAX_JGAAP_TAGS,
    PRETAX_INCOME_IFRS_TAGS,
    PRETAX_INCOME_JGAAP_TAGS,
    PRIOR_DURATION_CONTEXT_PATTERNS,
)

_TAX_RELEVANT_TAGS: frozenset[str] = frozenset(
    PRETAX_INCOME_JGAAP_TAGS
    + PRETAX_INCOME_IFRS_TAGS
    + INCOME_TAX_JGAAP_TAGS
    + INCOME_TAX_IFRS_TAGS
    + [
        "TotalAssetsUSGAAPSummaryOfBusinessResults",
        "EquityAttributableToOwnersOfParentUSGAAPSummaryOfBusinessResults",
        "InterestBearingLiabilitiesCLIFRS",
        "BorrowingsCLIFRS",
        "BondsPayableNCLIFRS",
        "BorrowingsNCLIFRS",
        "ProfitLossBeforeTaxIFRS",
        "IncomeTaxExpenseIFRS",
    ]
)



def _find_consolidated_duration_value(
    tag_elements: dict, tag: str
) -> tuple[float | None, float | None]:
    if tag not in tag_elements:
        return None, None
    current = prior = None
    current_pure = prior_pure = None
    for ctx, val in tag_elements[tag].items():
        if _is_consolidated_duration(ctx):
            if any(ctx == p for p in DURATION_CONTEXT_PATTERNS):
                current_pure = val
            else:
                current = val
        elif _is_consolidated_prior_duration(ctx):
            if any(ctx == p for p in PRIOR_DURATION_CONTEXT_PATTERNS):
                prior_pure = val
            else:
                prior = val
    return (
        current_pure if current_pure is not None else current,
        prior_pure if prior_pure is not None else prior,
    )


def _find_nonconsolidated_duration_value(
    tag_elements: dict, tag: str
) -> tuple[float | None, float | None]:
    if tag not in tag_elements:
        return None, None
    current = prior = None
    current_pure = prior_pure = None
    for ctx, val in tag_elements[tag].items():
        if _is_nonconsolidated_duration(ctx):
            if any(ctx == p for p in DURATION_CONTEXT_PATTERNS):
                current_pure = val
            else:
                current = val
        elif _is_nonconsolidated_prior_duration(ctx):
            if any(ctx == p for p in PRIOR_DURATION_CONTEXT_PATTERNS):
                prior_pure = val
            else:
                prior = val
    return (
        current_pure if current_pure is not None else current,
        prior_pure if prior_pure is not None else prior,
    )


def _extract_usgaap_tax_from_html(xbrl_dir: Path) -> dict | None:
    """US-GAAP企業の連結損益計算書(0105010)HTMLから税引前利益・法人税等を抽出する。"""
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
    if "税引前" not in content and "法人税" not in content:
        return None

    soup = BeautifulSoup(content, "html.parser")
    _HEADER_MARKERS = ("前連結", "当連結", "前期", "当期", "第")

    _PRETAX_KEYWORDS = ("税引前当期純利益", "税引前当期純損失", "税金等調整前当期純利益", "税金等調整前当期純損失")
    _TAX_AGGREGATE_KEYWORDS = ("法人税等合計",)
    _TAX_CURRENT_KEYWORDS = ("法人税、住民税及び事業税",)
    _TAX_DEFERRED_KEYWORDS = ("法人税等調整額",)

    for table in soup.find_all("table"):
        table_text = table.get_text()
        has_pretax = any(kw in table_text for kw in _PRETAX_KEYWORDS)
        has_tax = any(kw in table_text for kw in _TAX_AGGREGATE_KEYWORDS + _TAX_CURRENT_KEYWORDS)
        if not has_pretax and not has_tax:
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
                if "当連結" in text or ("当期" in text and "前期" not in text):
                    current_col_idx = last_col
                elif "前連結" in text or "前期" in text:
                    prior_col_idx = last_col
                col_offset += span
            if current_col_idx is not None:
                break

        def _extract_row(target_keywords, exclude_keywords=()):
            for row in rows:
                cells = row.find_all(["td", "th"])
                if not cells:
                    continue
                label = cells[0].get_text(strip=True)
                if not any(kw in label for kw in target_keywords):
                    continue
                if any(kw in label for kw in exclude_keywords):
                    continue
                numerics = [
                    (i, parse_html_number(c.get_text(strip=True)))
                    for i, c in enumerate(cells)
                    if i > 0 and parse_html_number(c.get_text(strip=True)) is not None
                ]
                if not numerics:
                    return None, None
                if prior_col_idx is not None and current_col_idx is not None:
                    def _find_nearest(target_col, _nums=numerics):
                        best_val, best_dist = None, float("inf")
                        for i, v in _nums:
                            d = abs(i - target_col)
                            if d < best_dist:
                                best_dist, best_val = d, v
                        return best_val if best_dist <= 2 else None
                    return _find_nearest(prior_col_idx), _find_nearest(current_col_idx)
                else:
                    pv = numerics[0][1] if len(numerics) >= 2 else None
                    return pv, numerics[-1][1]
            return None, None

        pretax_prior, pretax_cur = _extract_row(_PRETAX_KEYWORDS)

        tax_prior, tax_cur = _extract_row(_TAX_AGGREGATE_KEYWORDS)
        if tax_cur is None and tax_prior is None:
            cur_prior, cur_cur = _extract_row(_TAX_CURRENT_KEYWORDS)
            def_prior, def_cur = _extract_row(_TAX_DEFERRED_KEYWORDS)
            def _safe_add(a, b):
                if a is None and b is None:
                    return None
                return (a or 0.0) + (b or 0.0)
            tax_cur = _safe_add(cur_cur, def_cur)
            tax_prior = _safe_add(cur_prior, def_prior)

        if pretax_cur is None and pretax_prior is None and tax_cur is None and tax_prior is None:
            continue

        def _to_yen(v):
            return v * MILLION_YEN if v is not None else None

        def _tax_rate(pretax, tax):
            if pretax is not None and tax is not None and pretax != 0:
                return tax / pretax
            return None

        return {
            "pretax_income": _to_yen(pretax_cur),
            "income_tax": _to_yen(tax_cur),
            "effective_tax_rate": _tax_rate(pretax_cur, tax_cur),
            "prior_pretax_income": _to_yen(pretax_prior),
            "prior_income_tax": _to_yen(tax_prior),
            "prior_effective_tax_rate": _tax_rate(pretax_prior, tax_prior),
            "accounting_standard": "US-GAAP",
            "method": "usgaap_html",
        }

    return None


def _detect_accounting_standard(tag_elements: dict) -> str:
    usgaap_tags = {
        "TotalAssetsUSGAAPSummaryOfBusinessResults",
        "EquityAttributableToOwnersOfParentUSGAAPSummaryOfBusinessResults",
    }
    ifrs_marker_tags = [
        "InterestBearingLiabilitiesCLIFRS",
        "BorrowingsCLIFRS",
        "BondsPayableNCLIFRS",
        "BorrowingsNCLIFRS",
        "ProfitLossBeforeTaxIFRS",
        "IncomeTaxExpenseIFRS",
    ]
    if any(t in tag_elements for t in usgaap_tags) and not any(
        t in tag_elements for t in ifrs_marker_tags
    ):
        return "US-GAAP"
    if any(t in tag_elements for t in ifrs_marker_tags):
        return "IFRS"
    return "J-GAAP"


def _get_value(tag_elements: dict, tags: list[str]) -> tuple[float | None, float | None]:
    for tag in tags:
        current, prior = _find_consolidated_duration_value(tag_elements, tag)
        if current is None and prior is None:
            current, prior = _find_nonconsolidated_duration_value(tag_elements, tag)
        if current is not None or prior is not None:
            return current, prior
    return None, None


def extract_tax_expense(xbrl_dir: Path, *, pre_parsed: dict | None = None) -> dict:
    """
    XBRLディレクトリから税引前利益・法人税等を抽出し実効税率を計算する。

    Returns:
        {
            "pretax_income":    float | None,  # 当期税引前利益（円）
            "income_tax":       float | None,  # 当期法人税等（円）
            "effective_tax_rate": float | None,  # 実効税率（小数、例: 0.254）
            "prior_pretax_income":  float | None,
            "prior_income_tax":     float | None,
            "prior_effective_tax_rate": float | None,
            "accounting_standard": str,
            "method": str,   # "computed" | "not_found"
        }
    """
    if pre_parsed is not None:
        tag_elements: dict = {tag: ctx for tag, ctx in pre_parsed.items() if tag in _TAX_RELEVANT_TAGS}
    else:
        tag_elements = {}
        for f in find_xbrl_files(xbrl_dir):
            for tag, ctx_map in collect_numeric_elements(f, allowed_tags=_TAX_RELEVANT_TAGS).items():
                tag_elements.setdefault(tag, {}).update(ctx_map)

    accounting_standard = _detect_accounting_standard(tag_elements)

    if accounting_standard == "US-GAAP":
        result = _extract_usgaap_tax_from_html(xbrl_dir)
        if result is not None:
            return result
        return {
            "pretax_income": None, "income_tax": None, "effective_tax_rate": None,
            "prior_pretax_income": None, "prior_income_tax": None, "prior_effective_tax_rate": None,
            "accounting_standard": "US-GAAP", "method": "not_found",
            "reason": "US-GAAP 連結損益計算書 HTML (0105010) で税引前利益を取得できない",
        }

    if accounting_standard == "IFRS":
        pretax_tags = PRETAX_INCOME_IFRS_TAGS
        tax_tags = INCOME_TAX_IFRS_TAGS
    else:
        pretax_tags = PRETAX_INCOME_JGAAP_TAGS
        tax_tags = INCOME_TAX_JGAAP_TAGS

    pretax_cur, pretax_prior = _get_value(tag_elements, pretax_tags)
    tax_cur, tax_prior = _get_value(tag_elements, tax_tags)

    def _tax_rate(pretax: float | None, tax: float | None) -> float | None:
        if pretax is not None and tax is not None and pretax != 0:
            return tax / pretax
        return None

    if pretax_cur is None and tax_cur is None:
        return {
            "pretax_income": None, "income_tax": None, "effective_tax_rate": None,
            "prior_pretax_income": None, "prior_income_tax": None, "prior_effective_tax_rate": None,
            "accounting_standard": accounting_standard, "method": "not_found",
            "reason": f"{accounting_standard} 税引前利益タグが見つからない",
        }

    return {
        "pretax_income": pretax_cur,
        "income_tax": tax_cur,
        "effective_tax_rate": _tax_rate(pretax_cur, tax_cur),
        "prior_pretax_income": pretax_prior,
        "prior_income_tax": tax_prior,
        "prior_effective_tax_rate": _tax_rate(pretax_prior, tax_prior),
        "accounting_standard": accounting_standard,
        "method": "computed",
    }
