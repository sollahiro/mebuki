"""
有利子負債（IBD）XBRL抽出モジュール

XBRLインスタンス文書から有利子負債を構成要素ごとに抽出する。

有利子負債の定義:
  短期借入金
  + コマーシャル・ペーパー
  + 1年内償還予定の社債
  + 1年内返済予定の長期借入金
  + 社債
  + 長期借入金

タグ体系:
  J-GAAP: ShortTermLoansPayable, BondsPayable, LongTermLoansPayable, ...
  IFRS連結: BorrowingsCLIFRS, BondsPayableNCLIFRS, BorrowingsNCLIFRS, ...
  US-GAAP: HTML借入金ノートから解析

抽出戦略:
  1. 直接法: InterestBearingDebt タグを検索
  2. 積み上げ法: 各コンポーネントを個別に取得して合算
"""

import re
from pathlib import Path
from typing import Any, Dict, Optional

try:
    from bs4 import BeautifulSoup
    _BS4_AVAILABLE = True
except ImportError:
    _BS4_AVAILABLE = False

from mebuki.analysis.xbrl_utils import parse_xbrl_value, collect_numeric_elements, find_xbrl_files, parse_html_number
from mebuki.constants.financial import MILLION_YEN
from mebuki.constants.xbrl import (
    INTEREST_BEARING_DEBT_TAGS,
    COMPONENT_DEFINITIONS,
    AGGREGATE_IFRS_DEFINITIONS,
)

# XBRL解析で収集対象とするローカルタグ名のセット（不要要素のスキップに使用）
_IBD_RELEVANT_TAGS: frozenset[str] = frozenset(
    INTEREST_BEARING_DEBT_TAGS
    + [tag for comp in COMPONENT_DEFINITIONS for tag in comp["tags"]]
    + [agg["tag"] for agg in AGGREGATE_IFRS_DEFINITIONS]
    + [
        # US-GAAP判定用
        "TotalAssetsUSGAAPSummaryOfBusinessResults",
        "EquityAttributableToOwnersOfParentUSGAAPSummaryOfBusinessResults",
        "CashAndCashEquivalentsUSGAAPSummaryOfBusinessResults",
        # IFRSマーカー判定用
        "InterestBearingLiabilitiesCLIFRS",
        "InterestBearingLiabilitiesNCLIFRS",
        "BorrowingsCLIFRS",
        "BondsPayableNCLIFRS",
        "BorrowingsNCLIFRS",
    ]
)

# contextRef で連結期末時点を表すパターン
INSTANT_CONTEXT_PATTERNS = [
    "CurrentYearInstant",
    "FilingDateInstant",
]

PRIOR_CONTEXT_PATTERNS = [
    "Prior1YearInstant",
    "PriorYearInstant",
]


def _is_consolidated_instant(ctx: str) -> bool:
    """連結の期末残高コンテキストかどうか。"""
    return (
        any(p in ctx for p in INSTANT_CONTEXT_PATTERNS)
        and "_NonConsolidated" not in ctx
    )


def _is_consolidated_prior(ctx: str) -> bool:
    """連結の前期末残高コンテキストかどうか。"""
    return (
        any(p in ctx for p in PRIOR_CONTEXT_PATTERNS)
        and "_NonConsolidated" not in ctx
    )


def _is_nonconsolidated_instant(ctx: str) -> bool:
    """個別の期末残高コンテキストかどうか。"""
    return (
        any(p in ctx for p in INSTANT_CONTEXT_PATTERNS)
        and "_NonConsolidated" in ctx
    )


def _is_nonconsolidated_prior(ctx: str) -> bool:
    """個別の前期末残高コンテキストかどうか。"""
    return (
        any(p in ctx for p in PRIOR_CONTEXT_PATTERNS)
        and "_NonConsolidated" in ctx
    )



def _find_consolidated_value(tag_elements: dict, tag: str) -> tuple[Optional[float], Optional[float]]:
    """指定タグの連結当期・前期値のみを返す（個別へのフォールバックなし）。"""
    if tag not in tag_elements:
        return None, None
    current = prior = None
    for ctx, val in tag_elements[tag].items():
        if _is_consolidated_instant(ctx):
            current = val
        elif _is_consolidated_prior(ctx):
            prior = val
    return current, prior


def _find_nonconsolidated_value(tag_elements: dict, tag: str) -> tuple[Optional[float], Optional[float]]:
    """指定タグの個別当期・前期値のみを返す。"""
    if tag not in tag_elements:
        return None, None
    current = prior = None
    for ctx, val in tag_elements[tag].items():
        if _is_nonconsolidated_instant(ctx):
            current = val
        elif _is_nonconsolidated_prior(ctx):
            prior = val
    return current, prior



def _determine_column_order(headers: list[str]) -> tuple[int, int]:
    """
    ['第87期末（百万円）', '第88期末（百万円）'] のようなヘッダリストから
    (prior_col_idx, current_col_idx) を返す。

    US-GAAP連結注記形式 ['前連結会計年度末(百万円)', '', '当連結会計年度末(百万円)'] にも対応。
    """
    period_nums = []
    for h in headers:
        m = re.search(r'第(\d+)期', h)
        period_nums.append(int(m.group(1)) if m else -1)

    if any(n >= 0 for n in period_nums):
        if len(period_nums) < 2:
            return None, 0
        if period_nums[0] > period_nums[1]:
            return 1, 0
        else:
            return 0, 1

    # 前連結/当連結 パターン（US-GAAP企業の連結財務諸表注記）
    prior_idx = current_idx = None
    for i, h in enumerate(headers):
        if "当連結会計年度" in h or "当連結決算" in h:
            current_idx = i
        elif "前連結会計年度" in h or "前連結決算" in h:
            prior_idx = i
    if current_idx is not None:
        return prior_idx, current_idx

    if len(period_nums) < 2:
        return None, 0
    return 0, 1


def _find_loan_section_pos(content: str) -> int:
    """借入金ノートセクションの開始位置を返す。見つからない場合 -1。"""
    for keyword in ["短期借入金の残高", "短期の社債及び借入金"]:
        idx = content.find(keyword)
        if idx >= 0:
            nearby = content[idx: idx + 200]
            if "該当事項" not in nearby:
                return idx
    return -1


def _parse_loan_tables(tables: list) -> Dict[str, Any]:
    """パース済みテーブルリストから借入金各要素を抽出して返す。"""
    short_term_current = short_term_prior = None
    lt_total_current = lt_total_prior = None
    lt_1yr_current = lt_1yr_prior = None
    bonds_current = bonds_prior = None
    st_total_current = st_total_prior = None  # 合計行（US-GAAP形式）
    lt_net_current = lt_net_prior = None       # 差引計行（US-GAAP形式）

    for tbl in tables:
        headers = tbl["headers"]
        rows = tbl["rows"]
        if not rows:
            continue

        prior_idx, current_idx = _determine_column_order(headers[1:])

        for row in rows:
            if not row or len(row) < 2:
                continue
            label = row[0]
            vals = row[1:]

            def _get(idx, _vals=vals):
                if idx is None or idx >= len(_vals):
                    return None
                return parse_html_number(_vals[idx])

            if "短期借入金" in label and "（" not in label and "１年" not in label and "1年" not in label:
                short_term_current = short_term_current or _get(current_idx)
                short_term_prior   = short_term_prior   or _get(prior_idx)

            elif re.match(r'^長期借入金$', label):
                lt_total_current = lt_total_current or _get(current_idx)
                lt_total_prior   = lt_total_prior   or _get(prior_idx)

            elif "１年以内返済" in label or "1年以内返済" in label or "うち１年" in label:
                lt_1yr_current = lt_1yr_current or _get(current_idx)
                lt_1yr_prior   = lt_1yr_prior   or _get(prior_idx)

            elif "社債計" in label:
                bonds_current = bonds_current or _get(current_idx)
                bonds_prior   = bonds_prior   or _get(prior_idx)

            elif re.match(r'^合計$', label):
                st_total_current = st_total_current or _get(current_idx)
                st_total_prior   = st_total_prior   or _get(prior_idx)

            elif re.match(r'^差引計$', label):
                lt_net_current = lt_net_current or _get(current_idx)
                lt_net_prior   = lt_net_prior   or _get(prior_idx)

    return {
        "short_term": (short_term_current, short_term_prior),
        "lt_total":   (lt_total_current,   lt_total_prior),
        "lt_1yr":     (lt_1yr_current,     lt_1yr_prior),
        "bonds":      (bonds_current,      bonds_prior),
        "st_total":   (st_total_current,   st_total_prior),
        "lt_net":     (lt_net_current,     lt_net_prior),
    }


def _extract_usgaap_from_html(htm_file: Path) -> Optional[Dict[str, Any]]:
    """US-GAAP iXBRLファイルから借入金ノートセクションを解析し、有利子負債の構成要素を返す。"""
    if not _BS4_AVAILABLE:
        return None

    content = htm_file.read_text(encoding="utf-8", errors="ignore")

    idx = _find_loan_section_pos(content)
    if idx < 0:
        return None

    section_html = content[max(0, idx - 200): idx + 40000]
    soup = BeautifulSoup(section_html, "html.parser")
    tables = soup.find_all("table")
    if not tables:
        return None

    parsed_tables = []
    _HEADER_MARKERS = ("第", "前連結会計年度", "当連結会計年度", "前連結決算", "当連結決算")

    for tbl in tables:
        rows = tbl.find_all("tr")
        if not rows:
            continue
        # 実際のヘッダー行を検出（空行をスキップ）
        header_idx = 0
        for i, row in enumerate(rows):
            cells = [c.get_text(strip=True) for c in row.find_all(["td", "th"])]
            if any(any(m in c for m in _HEADER_MARKERS) for c in cells):
                header_idx = i
                break
        header_row = [c.get_text(strip=True) for c in rows[header_idx].find_all(["td", "th"])]
        data_rows = []
        for row in rows[header_idx + 1:]:
            cells = [c.get_text(strip=True) for c in row.find_all(["td", "th"])]
            if cells:
                data_rows.append(cells)
        parsed_tables.append({"headers": header_row, "rows": data_rows})

    extracted = _parse_loan_tables(parsed_tables)
    short_term_current, short_term_prior = extracted["short_term"]
    lt_total_current,   lt_total_prior   = extracted["lt_total"]
    lt_1yr_current,     lt_1yr_prior     = extracted["lt_1yr"]
    bonds_current,      bonds_prior      = extracted["bonds"]
    st_total_current,   st_total_prior   = extracted["st_total"]
    lt_net_current,     lt_net_prior     = extracted["lt_net"]

    def _to_yen(v):
        return v * MILLION_YEN if v is not None else None

    def safe_sum(vals):
        vs = [v for v in vals if v is not None]
        return sum(vs) if vs else None

    # 合計＋差引計が揃っていればUS-GAAP連結注記形式として処理（富士フイルム等）
    if st_total_current is not None and lt_net_current is not None:
        components = [
            {"label": "社債及び短期借入金（合計）",     "tag": "USGAAP_STTotal",
             "current": _to_yen(st_total_current), "prior": _to_yen(st_total_prior)},
            {"label": "長期の社債及び借入金（差引計）", "tag": "USGAAP_LTNet",
             "current": _to_yen(lt_net_current),   "prior": _to_yen(lt_net_prior)},
        ]
        return {
            "current": safe_sum([c["current"] for c in components]),
            "prior":   safe_sum([c["prior"]   for c in components]),
            "method":  "usgaap_html",
            "accounting_standard": "US-GAAP",
            "components": components,
        }

    if all(v is None for v in [short_term_current, lt_total_current, bonds_current]):
        return None

    def _subtract(a, b):
        return None if a is None else a - (b or 0)

    lt_longterm_current = _subtract(lt_total_current, lt_1yr_current)
    lt_longterm_prior   = _subtract(lt_total_prior,   lt_1yr_prior)

    components = [
        {"label": "短期借入金",               "tag": "USGAAP_ShortTermLoans",        "current": _to_yen(short_term_current),  "prior": _to_yen(short_term_prior)},
        {"label": "コマーシャル・ペーパー",    "tag": None,                            "current": None,                         "prior": None},
        {"label": "1年内償還予定の社債",       "tag": None,                            "current": None,                         "prior": None},
        {"label": "1年内返済予定の長期借入金", "tag": "USGAAP_CurrentPortionLTLoans",  "current": _to_yen(lt_1yr_current),      "prior": _to_yen(lt_1yr_prior)},
        {"label": "社債",                     "tag": "USGAAP_Bonds",                  "current": _to_yen(bonds_current),       "prior": _to_yen(bonds_prior)},
        {"label": "長期借入金",               "tag": "USGAAP_LTLoans",                "current": _to_yen(lt_longterm_current), "prior": _to_yen(lt_longterm_prior)},
    ]

    return {
        "current": safe_sum([c["current"] for c in components]),
        "prior":   safe_sum([c["prior"]   for c in components]),
        "method":  "usgaap_html",
        "accounting_standard": "US-GAAP",
        "components": components,
    }


def _detect_accounting_standard(tag_elements: dict) -> str:
    """会計基準を判定: 'J-GAAP' | 'IFRS' | 'US-GAAP'"""
    if _is_usgaap_xbrl(tag_elements):
        return "US-GAAP"
    ifrs_marker_tags = [
        "InterestBearingLiabilitiesCLIFRS",
        "InterestBearingLiabilitiesNCLIFRS",
        "BorrowingsCLIFRS",
        "BondsPayableNCLIFRS",
        "BorrowingsNCLIFRS",
        "BondsAndBorrowingsCLIFRS",
        "BondsAndBorrowingsNCLIFRS",
    ]
    if any(t in tag_elements for t in ifrs_marker_tags):
        return "IFRS"
    return "J-GAAP"


def _is_usgaap_xbrl(tag_elements: dict) -> bool:
    """XBRLインスタンスのタグ群がUS-GAAP企業かどうかを判定。"""
    usgaap_summary_tags = {
        "TotalAssetsUSGAAPSummaryOfBusinessResults",
        "EquityAttributableToOwnersOfParentUSGAAPSummaryOfBusinessResults",
        "CashAndCashEquivalentsUSGAAPSummaryOfBusinessResults",
    }
    has_usgaap = any(t in tag_elements for t in usgaap_summary_tags)
    if not has_usgaap:
        return False

    # IFRSマーカータグが存在する場合は、*USGAAPSummaryOfBusinessResults タグが
    # 旧期間比較データとして残存しているだけ（IFRS移行後の企業）と判断する
    ifrs_marker_tags = [
        "InterestBearingLiabilitiesCLIFRS",
        "InterestBearingLiabilitiesNCLIFRS",
        "BorrowingsCLIFRS",
        "BondsPayableNCLIFRS",
        "BorrowingsNCLIFRS",
        "BondsAndBorrowingsCLIFRS",
        "BondsAndBorrowingsNCLIFRS",
    ]
    if any(t in tag_elements for t in ifrs_marker_tags):
        return False

    debt_tags = [
        "ShortTermLoansPayable", "BorrowingsCLIFRS",
        "BondsPayable", "LongTermLoansPayable",
    ]
    for tag in debt_tags:
        c, _ = _find_consolidated_value(tag_elements, tag)
        if c is not None:
            return False
    return True


def extract_interest_bearing_debt(xbrl_dir: Path) -> dict:
    """
    XBRLディレクトリから有利子負債を構成要素ごとに抽出する。

    Returns:
        {
            "current": float | None,      # 合計 当期末（円）
            "prior":   float | None,      # 合計 前期末（円）
            "method":  str,               # "direct" | "computed" | "usgaap_html" | "not_found"
            "reason":  str | None,        # not_found 時のみ失敗理由を格納、それ以外は None
            "accounting_standard": str,   # "J-GAAP" | "IFRS" | "US-GAAP"
            "components": [               # 各コンポーネント
                {
                    "label": str,
                    "tag":   str | None,
                    "current": float | None,
                    "prior":   float | None,
                }
            ]
        }
    """
    tag_elements: dict = {}
    for f in find_xbrl_files(xbrl_dir):
        for tag, ctx_map in collect_numeric_elements(f, allowed_tags=_IBD_RELEVANT_TAGS).items():
            if tag not in tag_elements:
                tag_elements[tag] = {}
            tag_elements[tag].update(ctx_map)

    accounting_standard = _detect_accounting_standard(tag_elements)

    # US-GAAP 企業: HTML解析にフォールバック
    if _is_usgaap_xbrl(tag_elements):
        htm_files = list(xbrl_dir.rglob("*.htm")) + list(xbrl_dir.rglob("*.html"))
        for htm_file in htm_files:
            result = _extract_usgaap_from_html(htm_file)
            if result is not None:
                return result
        for htm_file in htm_files:
            content = htm_file.read_text(encoding="utf-8", errors="ignore")
            if "借入金等明細表" in content and "該当事項はありません" in content:
                zero_comps = [{"label": d["label"], "tag": None, "current": 0.0, "prior": 0.0}
                              for d in COMPONENT_DEFINITIONS]
                return {"current": 0.0, "prior": 0.0, "method": "usgaap_zero", "accounting_standard": "US-GAAP", "components": zero_comps}
        return {"current": None, "prior": None, "method": "not_found", "accounting_standard": "US-GAAP", "components": [],
                "reason": "US-GAAP 連結財務諸表注記 HTML (0105020) で借入金を取得できない"}

    # 直接法
    for ibd_tag in INTEREST_BEARING_DEBT_TAGS:
        current, prior = _find_consolidated_value(tag_elements, ibd_tag)
        if current is None and prior is None:
            current, prior = _find_nonconsolidated_value(tag_elements, ibd_tag)
        if current is not None or prior is not None:
            return {
                "current": current,
                "prior": prior,
                "method": "direct",
                "accounting_standard": accounting_standard,
                "components": [{"label": "有利子負債合計", "tag": ibd_tag,
                                "current": current, "prior": prior}],
            }

    # 積み上げ法（コンポーネント別）
    # Pass 1: 連結値のみ収集
    components = []
    for comp_def in COMPONENT_DEFINITIONS:
        found_tag = None
        current = prior = None
        for tag in comp_def["tags"]:
            # IFRS企業ではJ-GAAPタグ（IFRS識別子を含まないタグ）をスキップ
            if accounting_standard == "IFRS" and "IFRS" not in tag:
                continue
            c, p = _find_consolidated_value(tag_elements, tag)
            if c is not None or p is not None:
                found_tag = tag
                current, prior = c, p
                break
        components.append({
            "label": comp_def["label"],
            "tag": found_tag,
            "current": current,
            "prior": prior,
        })

    # 連結財務諸表が存在するか判定。
    # 1つでも連結値があれば連結財務諸表のみを使用し、単体値との混入を防ぐ。
    has_consolidated = any(c["current"] is not None or c["prior"] is not None for c in components)

    # IFRS企業では集約タグが連結財務諸表の存在を示すため、Pass 2への落下を防ぐ
    if not has_consolidated and accounting_standard == "IFRS":
        for agg_def in AGGREGATE_IFRS_DEFINITIONS:
            agg_c, agg_p = _find_consolidated_value(tag_elements, agg_def["tag"])
            if agg_c is not None or agg_p is not None:
                has_consolidated = True
                break

    # Pass 2: 連結値が全くない場合のみ単体にフォールバック（単体のみ企業への対応）
    if not has_consolidated:
        components = []
        for comp_def in COMPONENT_DEFINITIONS:
            found_tag = None
            current = prior = None
            for tag in comp_def["tags"]:
                c, p = _find_nonconsolidated_value(tag_elements, tag)
                if c is not None or p is not None:
                    found_tag = tag
                    current, prior = c, p
                    break
            components.append({
                "label": comp_def["label"],
                "tag": found_tag,
                "current": current,
                "prior": prior,
            })

    # 集約IFRSタグによる後処理
    for agg_def in AGGREGATE_IFRS_DEFINITIONS:
        agg_c, agg_p = _find_consolidated_value(tag_elements, agg_def["tag"])
        if agg_c is None and agg_p is None:
            continue
        covered = [c for c in components if c["label"] in agg_def["covers"]]
        needs_override = [
            c for c in covered
            if c["tag"] is None
            or _find_consolidated_value(tag_elements, c["tag"]) == (None, None)
        ]
        if not needs_override:
            continue
        for c in covered:
            c["current"] = None
            c["prior"] = None
            c["tag"] = None
        first = next(c for c in components if c["label"] == agg_def["covers"][0])
        first["tag"] = agg_def["tag"]
        first["current"] = agg_c
        first["prior"] = agg_p
        first["label"] = agg_def["covers"][0] + "＋" + agg_def["covers"][1] + "（集約）"

    found = [c for c in components if c["current"] is not None or c["prior"] is not None]
    if not found:
        return {"current": None, "prior": None, "method": "not_found", "accounting_standard": accounting_standard, "components": components,
                "reason": "有利子負債タグが見つからない"}

    def safe_sum(vals):
        vs = [v for v in vals if v is not None]
        return sum(vs) if vs else None

    total_current = safe_sum([c["current"] for c in components])
    total_prior = safe_sum([c["prior"] for c in components])

    return {
        "current": total_current,
        "prior": total_prior,
        "method": "computed",
        "accounting_standard": accounting_standard,
        "components": components,
    }
