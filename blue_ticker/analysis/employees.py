"""
従業員数 XBRL抽出モジュール

XBRLインスタンス文書から従業員数（連結優先）を抽出する。

contextRef が Instant 型の連結コンテキストを優先し、
連結値が取れない場合のみ非連結にフォールバックする。
"""

from pathlib import Path

from blue_ticker.analysis.field_parser import (
    field_set_from_pre_parsed,
    parse_instant_fields,
    resolve_item,
)
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
    field_set = (
        field_set_from_pre_parsed(pre_parsed)
        if pre_parsed is not None
        else parse_instant_fields(xbrl_dir, allowed_tags=_RELEVANT_TAGS)
    )

    item = resolve_item(field_set, EMPLOYEE_TAGS)
    if item["tag"] is not None:
        return {"current": item["current"], "prior": item["prior"], "method": "direct", "scope": "consolidated"}

    return {"current": None, "prior": None, "method": "not_found", "scope": "unknown"}
