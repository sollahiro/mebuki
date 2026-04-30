"""
US-GAAP 有利子負債 HTML パースモジュール

US-GAAP採用企業の iXBRL ファイルから借入金注記セクションを解析し、
有利子負債の構成要素を抽出する。
"""

import re
from pathlib import Path

try:
    from bs4 import BeautifulSoup
    _BS4_AVAILABLE = True
except ImportError:
    _BS4_AVAILABLE = False

from mebuki.analysis.xbrl_utils import parse_html_number
from mebuki.constants.financial import MILLION_YEN
from mebuki.constants.xbrl import COMPONENT_DEFINITIONS


def _safe_sum(vals: list[float | None]) -> float | None:
    vs = [v for v in vals if v is not None]
    return sum(vs) if vs else None


def _determine_column_order(headers: list[str]) -> tuple[int | None, int]:
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


def _parse_loan_tables(tables: list) -> dict[str, tuple[float | None, float | None]]:
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


def _extract_usgaap_from_html(htm_file: Path) -> dict | None:
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

    # 合計＋差引計が揃っていればUS-GAAP連結注記形式として処理（富士フイルム等）
    if st_total_current is not None and lt_net_current is not None:
        components = [
            {"label": "社債及び短期借入金（合計）",     "tag": "USGAAP_STTotal",
             "current": _to_yen(st_total_current), "prior": _to_yen(st_total_prior)},
            {"label": "長期の社債及び借入金（差引計）", "tag": "USGAAP_LTNet",
             "current": _to_yen(lt_net_current),   "prior": _to_yen(lt_net_prior)},
        ]
        return {
            "current": _safe_sum([c["current"] for c in components]),
            "prior":   _safe_sum([c["prior"]   for c in components]),
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
        "current": _safe_sum([c["current"] for c in components]),
        "prior":   _safe_sum([c["prior"]   for c in components]),
        "method":  "usgaap_html",
        "accounting_standard": "US-GAAP",
        "components": components,
    }
