"""
従業員数 XBRL抽出モジュール

XBRLインスタンス文書から従業員数（連結優先）を抽出する。

contextRef が Instant 型の連結コンテキストを優先し、
連結値が取れない場合のみ非連結にフォールバックする。
"""

from pathlib import Path

from mebuki.analysis.context_helpers import (
    _is_consolidated_instant,
    _is_consolidated_prior_instant,
    _is_nonconsolidated_instant,
    _is_nonconsolidated_prior_instant,
)
from mebuki.analysis.xbrl_utils import collect_numeric_elements, find_xbrl_files
from mebuki.utils.xbrl_result_types import EmployeesResult

EMPLOYEE_TAGS = [
    "NumberOfEmployees",       # 主要タグ（J-GAAP・IFRS共通）
    "NumberOfGroupEmployees",  # グループ従業員数（代替）
]

_RELEVANT_TAGS: frozenset[str] = frozenset(EMPLOYEE_TAGS)


def _find_value(
    ctx_map: dict,
    is_current_fn,
    is_prior_fn,
) -> tuple[float | None, float | None]:
    current = prior = None
    for ctx, val in ctx_map.items():
        if current is None and is_current_fn(ctx):
            current = val
        elif prior is None and is_prior_fn(ctx):
            prior = val
    return current, prior


def extract_employees(xbrl_dir: Path, *, pre_parsed: dict | None = None) -> EmployeesResult:
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
        tag_elements: dict = {tag: ctx for tag, ctx in pre_parsed.items() if tag in _RELEVANT_TAGS}
    else:
        tag_elements = {}
        for f in find_xbrl_files(xbrl_dir):
            for tag, ctx_map in collect_numeric_elements(f, allowed_tags=_RELEVANT_TAGS).items():
                if tag not in tag_elements:
                    tag_elements[tag] = {}
                tag_elements[tag].update(ctx_map)

    for tag in EMPLOYEE_TAGS:
        if tag not in tag_elements:
            continue
        ctx_map = tag_elements[tag]

        current, prior = _find_value(ctx_map, _is_consolidated_instant, _is_consolidated_prior_instant)
        if current is not None or prior is not None:
            return {"current": current, "prior": prior, "method": "direct", "scope": "consolidated"}

        current, prior = _find_value(ctx_map, _is_nonconsolidated_instant, _is_nonconsolidated_prior_instant)
        if current is not None or prior is not None:
            return {"current": current, "prior": prior, "method": "direct", "scope": "nonconsolidated"}

    return {"current": None, "prior": None, "method": "not_found", "scope": "unknown"}
