"""
従業員数 XBRL抽出モジュール

XBRLインスタンス文書から従業員数（連結優先）を抽出する。

contextRef が Instant 型の連結コンテキストを優先し、
連結値が取れない場合のみ非連結にフォールバックする。
"""

from pathlib import Path

from blue_ticker.analysis.context_helpers import (
    _is_consolidated_instant,
    _is_consolidated_prior_instant,
)
from blue_ticker.analysis.field_parser import (
    field_set_from_pre_parsed,
    resolve_item,
)
from blue_ticker.analysis.xbrl_utils import collect_numeric_elements, find_xbrl_files
from blue_ticker.utils.xbrl_result_types import EmployeesResult, XbrlTagElements

EMPLOYEE_TAGS = [
    "NumberOfEmployees",       # 主要タグ（J-GAAP・IFRS共通）
    "NumberOfGroupEmployees",  # グループ従業員数（代替）
]

_RELEVANT_TAGS: frozenset[str] = frozenset(EMPLOYEE_TAGS)


def extract_employees(
    xbrl_dir: Path,
    *,
    pre_parsed: XbrlTagElements | None = None,
) -> EmployeesResult:
    """
    XBRLディレクトリから従業員数を抽出する。

    Returns:
        {
            "current": float | None,  # 当期末（人）
            "prior":   float | None,  # 前期末（人）
            "method":  str,           # "direct" | "not_found"
            "scope":   str,           # "consolidated" | "nonconsolidated" | "unknown"
        }
    """
    if pre_parsed is not None:
        tag_elements = pre_parsed
    else:
        tag_elements: XbrlTagElements = {}
        for f in find_xbrl_files(xbrl_dir):
            for tag, ctx_map in collect_numeric_elements(f, allowed_tags=_RELEVANT_TAGS).items():
                if tag not in tag_elements:
                    tag_elements[tag] = {}
                tag_elements[tag].update(ctx_map)

    field_set = field_set_from_pre_parsed(tag_elements)

    item = resolve_item(field_set, EMPLOYEE_TAGS)
    if item["tag"] is not None:
        ctx_map = tag_elements.get(item["tag"], {})
        scope = (
            "consolidated"
            if any(_is_consolidated_instant(c) or _is_consolidated_prior_instant(c) for c in ctx_map)
            else "nonconsolidated"
        )
        return {"current": item["current"], "prior": item["prior"], "method": "direct", "scope": scope}

    return {"current": None, "prior": None, "method": "not_found", "scope": "unknown"}
