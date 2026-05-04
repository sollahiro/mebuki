"""
受注高・受注残高 XBRL 抽出モジュール

有価証券報告書の MD&A TextBlock に含まれる XHTML table から、
受注高と受注残高を抽出する。
"""

import html
import re
import xml.etree.ElementTree as ET
from pathlib import Path

try:
    from bs4 import BeautifulSoup
    _BS4_AVAILABLE = True
except ImportError:
    _BS4_AVAILABLE = False

from mebuki.analysis.xbrl_utils import find_xbrl_files, parse_html_int_attribute, parse_html_number
from mebuki.constants.financial import MILLION_YEN
from mebuki.constants.xbrl import XBRL_SECTIONS
from mebuki.utils.xbrl_result_types import OrderBookResult, XbrlTagElements

_MDA_TEXTBLOCK_ELEMENT_NAMES = frozenset(XBRL_SECTIONS["mda"]["xbrl_elements"])

_CURRENT_HEADER_MARKERS = (
    "当連結",
    "当期",
    "当年度",
    "当事業年度",
    "当連結会計年度",
    "当連結会計年度末",
    "当年度末",
    "当期末",
    "当事業年度末",
)
_PRIOR_HEADER_MARKERS = (
    "前連結",
    "前期",
    "前年度",
    "前事業年度",
    "前連結会計年度",
    "前連結会計年度末",
    "前年度末",
    "前期末",
    "前事業年度末",
)
_ORDER_INTAKE_MARKERS = ("受注高", "受注額", "新規受注高")
_ORDER_BACKLOG_MARKERS = ("受注残高", "受注残", "期末受注残高")
_TOTAL_ROW_MARKERS = ("合計", "計")
_HTML_TAG_RE = re.compile(r"<[^>]+>")
_INT_RE = re.compile(r"[0-9０-９][0-9０-９,，]*")


def _not_found(reason: str) -> OrderBookResult:
    return {
        "order_intake": None,
        "order_backlog": None,
        "order_intake_prior": None,
        "order_backlog_prior": None,
        "method": "not_found",
        "reason": reason,
    }


def _local_tag(tag: str) -> str:
    return tag.split("}", 1)[1] if "}" in tag else tag


def _normalized_text(element: ET.Element) -> str:
    text = "".join(element.itertext())
    return "".join(text.split()).replace("\xa0", "")


def _normalize_plain_text(text: str) -> str:
    return "".join(text.split()).replace("\xa0", "")


def _cell_text(element: ET.Element) -> str:
    return "".join(element.itertext()).strip()


def _has_any(text: str, markers: tuple[str, ...]) -> bool:
    return any(marker in text for marker in markers)


def _get_table_rows(table: ET.Element) -> list[ET.Element]:
    return [elem for elem in table.iter() if _local_tag(elem.tag).lower() == "tr"]


def _row_cells(row: ET.Element) -> list[ET.Element]:
    return [
        elem
        for elem in list(row)
        if _local_tag(elem.tag).lower() in ("td", "th")
    ]


def _expanded_cells(row: ET.Element) -> list[tuple[int, int, str]]:
    cells: list[tuple[int, int, str]] = []
    col_offset = 0
    for cell in _row_cells(row):
        span = parse_html_int_attribute(cell, "colspan")
        last_col = col_offset + span - 1
        cells.append((col_offset, last_col, _cell_text(cell)))
        col_offset += span
    return cells


def _find_header_columns(rows: list[ET.Element]) -> tuple[int | None, int | None]:
    current_col = prior_col = None
    for row in rows:
        expanded = _expanded_cells(row)
        if not expanded:
            continue
        row_text = "".join(text for _, _, text in expanded)
        if not (
            _has_any(row_text, _CURRENT_HEADER_MARKERS)
            or _has_any(row_text, _PRIOR_HEADER_MARKERS)
        ):
            continue
        for _, last_col, text in expanded:
            if _has_any(text, _CURRENT_HEADER_MARKERS):
                current_col = last_col
            if _has_any(text, _PRIOR_HEADER_MARKERS):
                prior_col = last_col
        if current_col is not None or prior_col is not None:
            return current_col, prior_col
    return None, None


def _numeric_cells(row: ET.Element) -> list[tuple[int, float]]:
    numerics: list[tuple[int, float]] = []
    for _, last_col, text in _expanded_cells(row):
        value = parse_html_number(text)
        if value is not None:
            numerics.append((last_col, value))
    return numerics


def _nearest_value(numerics: list[tuple[int, float]], target_col: int) -> float | None:
    best_value = None
    best_distance = 3
    for col, value in numerics:
        distance = abs(col - target_col)
        if distance < best_distance:
            best_distance = distance
            best_value = value
    return best_value


def _extract_row_values(
    row: ET.Element,
    current_col: int | None,
    prior_col: int | None,
) -> tuple[float | None, float | None]:
    numerics = _numeric_cells(row)
    if not numerics:
        return None, None

    if current_col is not None or prior_col is not None:
        numeric_min_col = numerics[0][0]
        header_cols = [col for col in (current_col, prior_col) if col is not None]
        header_min_col = min(header_cols) if header_cols else 0
        col_shift = numeric_min_col if header_min_col == 0 and numeric_min_col > 0 else 0
        current = _nearest_value(numerics, current_col + col_shift) if current_col is not None else None
        prior = _nearest_value(numerics, prior_col + col_shift) if prior_col is not None else None
        return current, prior

    if len(numerics) == 1:
        return numerics[0][1], None
    if len(numerics) in (2, 3):
        return numerics[1][1], numerics[0][1]
    return None, None


def _find_metric_row_values(
    rows: list[ET.Element],
    markers: tuple[str, ...],
    excluded_markers: tuple[str, ...],
    current_col: int | None,
    prior_col: int | None,
) -> tuple[float | None, float | None]:
    for row in rows:
        row_text = _normalized_text(row)
        if not _has_any(row_text, markers) or _has_any(row_text, excluded_markers):
            continue
        current, prior = _extract_row_values(row, current_col, prior_col)
        if current is not None or prior is not None:
            return current, prior
    return None, None


def _find_metric_header_columns(rows: list[ET.Element]) -> tuple[int | None, int | None]:
    intake_col = backlog_col = None
    for row in rows:
        row_text = _normalized_text(row)
        if not (
            _has_any(row_text, _ORDER_INTAKE_MARKERS)
            and _has_any(row_text, _ORDER_BACKLOG_MARKERS)
        ):
            continue
        for _, last_col, text in _expanded_cells(row):
            if _has_any(text, _ORDER_BACKLOG_MARKERS):
                backlog_col = last_col
            elif _has_any(text, _ORDER_INTAKE_MARKERS):
                intake_col = last_col
        if intake_col is not None or backlog_col is not None:
            return intake_col, backlog_col
    return None, None


def _find_total_row_values_by_metric_columns(
    rows: list[ET.Element],
) -> tuple[float | None, float | None]:
    intake_col, backlog_col = _find_metric_header_columns(rows)
    if intake_col is None and backlog_col is None:
        return None, None

    for row in rows:
        cells = _expanded_cells(row)
        if not cells:
            continue
        label = cells[0][2]
        if not any(marker == "".join(label.split()) for marker in _TOTAL_ROW_MARKERS):
            continue
        numerics = _numeric_cells(row)
        intake = _nearest_value(numerics, intake_col) if intake_col is not None else None
        backlog = _nearest_value(numerics, backlog_col) if backlog_col is not None else None
        if intake is not None or backlog is not None:
            return intake, backlog
    return None, None


def _to_yen(value: float | None) -> float | None:
    return value * MILLION_YEN if value is not None else None


def _plain_number(text: str) -> float | None:
    match = _INT_RE.search(text)
    return parse_html_number(match.group(0)) if match else None


def _text_after(text: str, marker: str, limit: int = 80) -> str:
    idx = text.find(marker)
    return text[idx: idx + limit] if idx >= 0 else ""


def _search_in_plain_text(text: str) -> tuple[float | None, float | None]:
    plain = _normalize_plain_text(_HTML_TAG_RE.sub("", html.unescape(text)))
    intake = None
    backlog = None

    intake_fragment = _text_after(plain, "受注高")
    if intake_fragment:
        intake = _plain_number(intake_fragment.removeprefix("受注高"))

    backlog_start = plain.find("繰越受注残")
    if backlog_start < 0:
        backlog_start = plain.find("受注残高")
    if backlog_start < 0:
        backlog_start = plain.find("受注残")
    if backlog_start >= 0:
        backlog_fragment = plain[backlog_start: backlog_start + 80]
        backlog = _plain_number(
            backlog_fragment
            .removeprefix("繰越受注残高")
            .removeprefix("繰越受注残")
            .removeprefix("受注残高")
            .removeprefix("受注残")
        )

    return intake, backlog


def _search_in_tables(root: ET.Element) -> OrderBookResult:
    for table in root.iter():
        if _local_tag(table.tag).lower() != "table":
            continue
        table_text = _normalized_text(table)
        if not (
            _has_any(table_text, _ORDER_INTAKE_MARKERS)
            or _has_any(table_text, _ORDER_BACKLOG_MARKERS)
        ):
            continue

        rows = _get_table_rows(table)
        current_col, prior_col = _find_header_columns(rows)
        backlog, backlog_prior = _find_metric_row_values(
            rows,
            _ORDER_BACKLOG_MARKERS,
            (),
            current_col,
            prior_col,
        )
        intake, intake_prior = _find_metric_row_values(
            rows,
            _ORDER_INTAKE_MARKERS,
            _ORDER_BACKLOG_MARKERS,
            current_col,
            prior_col,
        )
        if backlog is None and intake is None:
            intake, backlog = _find_total_row_values_by_metric_columns(rows)
        if backlog is not None or backlog_prior is not None or intake is not None or intake_prior is not None:
            return {
                "order_intake": _to_yen(intake),
                "order_backlog": _to_yen(backlog),
                "order_intake_prior": _to_yen(intake_prior),
                "order_backlog_prior": _to_yen(backlog_prior),
                "method": "mda_textblock_table",
            }

    return _not_found("MD&A TextBlock 内の table から受注高・受注残高を取得できない")


def _parse_html_tables_with_bs4(fragment: str) -> ET.Element | None:
    if not _BS4_AVAILABLE:
        return None
    soup = BeautifulSoup(fragment, "html.parser")
    tables = soup.find_all("table")
    if not tables:
        return None

    root = ET.Element("root")
    for soup_table in tables:
        table = ET.SubElement(root, "table")
        for soup_row in soup_table.find_all("tr"):
            row = ET.SubElement(table, "tr")
            for soup_cell in soup_row.find_all(["td", "th"], recursive=False):
                cell = ET.SubElement(row, soup_cell.name)
                colspan = soup_cell.get("colspan")
                if isinstance(colspan, str):
                    cell.set("colspan", colspan)
                cell.text = soup_cell.get_text("", strip=True)
    return root


def _parse_escaped_html_fragment(text: str | None) -> ET.Element | None:
    if not text:
        return None
    unescaped = html.unescape(text)
    if "<table" not in unescaped:
        return None
    try:
        return ET.fromstring(f"<root>{unescaped}</root>")
    except ET.ParseError:
        return _parse_html_tables_with_bs4(unescaped)


def _search_in_element(element: ET.Element) -> OrderBookResult:
    result = _search_in_tables(element)
    if result["order_intake"] is not None or result["order_backlog"] is not None:
        return result

    parsed_html = _parse_escaped_html_fragment(element.text)
    if parsed_html is not None:
        result = _search_in_tables(parsed_html)
        if result["order_intake"] is not None or result["order_backlog"] is not None:
            return result

    text = element.text or ""
    if "<table" in text or "&lt;table" in text:
        return result

    intake, backlog = _search_in_plain_text(text)
    if intake is not None or backlog is not None:
        return {
            "order_intake": _to_yen(intake),
            "order_backlog": _to_yen(backlog),
            "order_intake_prior": None,
            "order_backlog_prior": None,
            "method": "mda_textblock_text",
        }

    return result


def extract_order_book(
    xbrl_dir: Path,
    *,
    pre_parsed: XbrlTagElements | None = None,
) -> OrderBookResult:
    """XBRLディレクトリから受注高・受注残高を抽出する。"""
    # pre_parsed は現状、数値タグのみを共有するため TextBlock 解析には使えない。
    # 抽出器共通シグネチャを保ちつつ、MD&A の XHTML table だけ XML から直接読む。
    _ = pre_parsed
    for xml_file in find_xbrl_files(xbrl_dir):
        try:
            root = ET.parse(xml_file).getroot()
        except ET.ParseError:
            continue
        for elem in root.iter():
            if _local_tag(elem.tag) not in _MDA_TEXTBLOCK_ELEMENT_NAMES:
                continue
            result = _search_in_element(elem)
            if result["order_intake"] is not None or result["order_backlog"] is not None:
                return result
    return _not_found("MD&A TextBlock が見つからない、または受注高・受注残高を取得できない")
