"""
従業員数 XBRL抽出モジュール

XBRLインスタンス文書から従業員数（連結優先）を抽出する。

contextRef が Instant 型の連結コンテキストを優先し、
連結値が取れない場合のみ非連結にフォールバックする。
"""

from blue_ticker.analysis.context_helpers import (
    _is_consolidated_instant,
    _is_consolidated_prior_instant,
)
from blue_ticker.analysis.sections import EmployeeSection
from blue_ticker.utils.xbrl_result_types import EmployeesResult

EMPLOYEE_TAGS = [
    "NumberOfEmployees",       # 主要タグ（J-GAAP・IFRS共通）
    "NumberOfGroupEmployees",  # グループ従業員数（代替）
]


def extract_employees(section: EmployeeSection) -> EmployeesResult:
    """
    従業員セクションから従業員数を抽出する。

    Returns:
        {
            "current": float | None,  # 当期末（人）
            "prior":   float | None,  # 前期末（人）
            "method":  str,           # "direct" | "not_found"
            "scope":   str,           # "consolidated" | "nonconsolidated" | "unknown"
        }
    """
    item = section.resolve(EMPLOYEE_TAGS)
    if item["tag"] is not None:
        ctx_map = section.tag_elements.get(item["tag"], {})
        scope = (
            "consolidated"
            if any(_is_consolidated_instant(c) or _is_consolidated_prior_instant(c) for c in ctx_map)
            else "nonconsolidated"
        )
        return {"current": item["current"], "prior": item["prior"], "method": "direct", "scope": scope}

    return {"current": None, "prior": None, "method": "not_found", "scope": "unknown"}
