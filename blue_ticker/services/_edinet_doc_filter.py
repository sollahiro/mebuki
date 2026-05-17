"""書類分類・フィルタ系の純粋関数。"""

from typing import Any

from blue_ticker.constants.api import (
    EDINET_DOC_TYPE_AMENDMENT,
    EDINET_DOC_TYPE_ANNUAL_REPORT,
    EDINET_DOC_TYPE_HALF_YEAR_REPORT,
    EDINET_DOC_TYPE_QUARTERLY_REPORT,
)


def _fy_end_key(value: object) -> str:
    return value.replace("-", "") if isinstance(value, str) else ""


def _doc_type_code(doc: dict[str, Any]) -> str:
    value = doc.get("docTypeCode")
    return value if isinstance(value, str) else ""


def _is_half_year_doc(doc: dict[str, Any]) -> bool:
    return (
        doc.get("period_type") == "2Q"
        or _doc_type_code(doc) in {
            EDINET_DOC_TYPE_QUARTERLY_REPORT,
            EDINET_DOC_TYPE_HALF_YEAR_REPORT,
        }
    )


def _is_annual_amendment_doc(doc: dict[str, Any]) -> bool:
    return not _is_half_year_doc(doc) and (
        bool(doc.get("_is_amendment"))
        or _doc_type_code(doc) == EDINET_DOC_TYPE_AMENDMENT
    )


def _is_primary_annual_doc(doc: dict[str, Any]) -> bool:
    if _is_half_year_doc(doc) or _is_annual_amendment_doc(doc):
        return False
    doc_type = _doc_type_code(doc)
    return doc_type in ("", EDINET_DOC_TYPE_ANNUAL_REPORT)


def _primary_annual_docs(docs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    primary = [doc for doc in docs if _is_primary_annual_doc(doc)]
    if primary:
        return primary
    return [doc for doc in docs if not _is_half_year_doc(doc)]


def _doc_ids_by_year(docs: list[dict[str, Any]]) -> dict[str, str]:
    result: dict[str, str] = {}
    for doc in _primary_annual_docs(docs):
        fy_end = _fy_end_key(doc.get("edinet_fy_end"))
        doc_id = doc.get("docID")
        if fy_end and isinstance(doc_id, str) and doc_id:
            result.setdefault(fy_end, doc_id)
    return result


def _amendment_doc_ids_by_year(docs: list[dict[str, Any]]) -> dict[str, str]:
    result: dict[str, str] = {}
    for doc in docs:
        if not _is_annual_amendment_doc(doc):
            continue
        fy_end = _fy_end_key(doc.get("edinet_fy_end"))
        doc_id = doc.get("docID")
        if fy_end and isinstance(doc_id, str) and doc_id:
            result[fy_end] = doc_id
    return result


def _slice_docs_preserving_amendments(
    docs: list[dict[str, Any]],
    max_years: int,
) -> list[dict[str, Any]]:
    """通常書類を max_years 件に絞り、該当年度の訂正書類は保持する。

    build_document_index_for_code() は末尾に訂正書類を追加する場合がある。
    単純な docs[:max_years] だと訂正書類が落ちて XBRL 上書き処理が効かなくなる。
    """
    regular = [d for d in docs if _is_primary_annual_doc(d)]
    sliced = regular[:max_years]
    selected_fy_ends = {_fy_end_key(d.get("edinet_fy_end")) for d in sliced}
    amendments = [
        d for d in docs
        if _is_annual_amendment_doc(d)
        and _fy_end_key(d.get("edinet_fy_end")) in selected_fy_ends
    ]
    return sliced + amendments


def _slice_half_year_docs(docs: list[dict[str, Any]], max_years: int) -> list[dict[str, Any]]:
    return [d for d in docs if not d.get("_is_amendment")][:max_years]
