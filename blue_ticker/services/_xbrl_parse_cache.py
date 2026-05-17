"""XBRLパースキャッシュ変換・ステートメントスコープ絞り込みユーティリティ。"""

from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any, TypeAlias

from blue_ticker.utils.xbrl_result_types import XbrlFactIndex, XbrlTagElements

_PreParsedEntry: TypeAlias = tuple[Path, XbrlTagElements, XbrlFactIndex]
_PreParsedMap: TypeAlias = dict[str, _PreParsedEntry]

_INCOME_STATEMENT_SECTIONS: tuple[str, ...] = (
    "ConsolidatedStatementOfIncome",
    "ConsolidatedStatementOfComprehensiveIncome",
    "NotesConsolidatedStatementOfIncome",
    "NotesConsolidatedStatementOfComprehensiveIncome",
)
_INCOME_STATEMENT_FALLBACK_SECTIONS: tuple[str, ...] = (
    "StatementOfIncome",
    "NotesStatementOfIncome",
)
_BALANCE_SHEET_SECTIONS: tuple[str, ...] = (
    # タプル内の順序は探索順に影響しない（filter_fact_index_by_sections は集合として処理）。
    # BusinessResultsOfGroup を preferred に含めることで、IFRS要約情報セクションのタグ
    # （TotalAssetsIFRSSummaryOfBusinessResults 等）を連結BS相当として扱い、
    # preferred が非空になれば非連結BSフォールバックを遮断する意図。
    "BusinessResultsOfGroup",
    "ConsolidatedBalanceSheet",
    "NotesConsolidatedBalanceSheet",
    "ConsolidatedStatementOfFinancialPositionIFRS",  # IFRS 連結財政状態計算書
    "NotesConsolidatedStatementOfFinancialPositionIFRS",
)
_BALANCE_SHEET_FALLBACK_SECTIONS: tuple[str, ...] = (
    "BalanceSheet",
    "NotesBalanceSheet",
)
_CASH_FLOW_SECTIONS: tuple[str, ...] = (
    "ConsolidatedStatementOfCashFlows",
    "ConsolidatedStatementOfCashFlows-indirect",
    "NotesConsolidatedStatementOfCashFlows",
)
_CASH_FLOW_FALLBACK_SECTIONS: tuple[str, ...] = (
    "StatementOfCashFlows",
    "StatementOfCashFlows-indirect",
    "NotesStatementOfCashFlows",
)

_STATEMENT_SECTIONS_BY_KEY: dict[str, tuple[tuple[str, ...], tuple[str, ...]]] = {
    "ibd": (_BALANCE_SHEET_SECTIONS, _BALANCE_SHEET_FALLBACK_SECTIONS),
    "bs": (_BALANCE_SHEET_SECTIONS, _BALANCE_SHEET_FALLBACK_SECTIONS),
    # IS 系は全セクション対象: _INCOME_STATEMENT_SECTIONS に IFRS/US-GAAP セクション名が未登録のため
    # セクション絞り込みをすると J-GAAP サマリーの偽シグナルで IFRS/US-GAAP の値が誤抽出される
    "da": (_CASH_FLOW_SECTIONS, _CASH_FLOW_FALLBACK_SECTIONS),
}


def _is_valid_xbrl_parse_cache(data: object) -> bool:
    """dict[str, dict[str, XbrlFact]] 相当の shape を簡易検証する。"""
    if not isinstance(data, dict):
        return False
    for value in data.values():
        if not isinstance(value, dict):
            return False
        for fact in value.values():
            if not isinstance(fact, dict):
                return False
            if not isinstance(fact.get("tag"), str):
                return False
            if not isinstance(fact.get("contextRef"), str):
                return False
            fact_value = fact.get("value")
            if not isinstance(fact_value, (int, float)) or isinstance(fact_value, bool):
                return False
            if not isinstance(fact.get("consolidation"), str):
                return False
    return True


def _numeric_elements_from_xbrl_parse_cache(data: object) -> XbrlTagElements | None:
    """メタ付き fact キャッシュを既存抽出器向けの数値索引へ変換する。"""
    if not _is_valid_xbrl_parse_cache(data) or not isinstance(data, dict):
        return None
    numeric: XbrlTagElements = {}
    for tag, ctx_map in data.items():
        if not isinstance(tag, str) or not isinstance(ctx_map, dict):
            return None
        numeric[tag] = {}
        for context_ref, fact in ctx_map.items():
            if not isinstance(context_ref, str) or not isinstance(fact, dict):
                return None
            value = fact.get("value")
            if not isinstance(value, (int, float)) or isinstance(value, bool):
                return None
            numeric[tag][context_ref] = float(value)
    return numeric


def _preparsed_for_statement(
    entry: _PreParsedEntry,
    statement_key: str | None,
) -> XbrlTagElements:
    """メタ付き fact から statement 優先の数値索引を作る。"""
    from blue_ticker.analysis.xbrl_utils import (
        fact_index_to_numeric_elements,
        filter_fact_index_by_sections,
    )

    _xbrl_path, all_numeric, facts = entry
    if statement_key is None:
        return all_numeric
    section_pair = _STATEMENT_SECTIONS_BY_KEY.get(statement_key)
    if section_pair is None:
        return all_numeric
    preferred_sections, fallback_sections = section_pair
    filtered_facts = filter_fact_index_by_sections(
        facts,
        preferred_sections,
        fallback_sections,
    )
    if not filtered_facts:
        return all_numeric
    return fact_index_to_numeric_elements(filtered_facts)


def _result_has_signal(result: Mapping[str, Any]) -> bool:
    if result.get("method") == "not_found":
        return False
    for value in result.values():
        if isinstance(value, dict):
            if any(v is not None for v in value.values()):
                return True
        elif isinstance(value, (int, float)) and not isinstance(value, bool):
            return True
    return bool(result.get("found"))


def _extract_with_statement_scope(
    entry: _PreParsedEntry,
    statement_key: str | None,
    extract_fn: Callable,
) -> dict[str, Any]:
    xbrl_path = entry[0]
    scoped_pre_parsed = _preparsed_for_statement(entry, statement_key)
    result = extract_fn(xbrl_path, pre_parsed=scoped_pre_parsed)
    if scoped_pre_parsed is not entry[1] and not _result_has_signal(result):
        return extract_fn(xbrl_path, pre_parsed=entry[1])
    return result
