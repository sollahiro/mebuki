"""
EDINET 書類検索・本文抽出サービス
"""

from collections.abc import Callable
from pathlib import Path
from typing import Any

from blue_ticker.api.edinet_client import EdinetAPIClient
from blue_ticker.analysis.segment_extractor import extract_segment_info, extract_geography_info
from blue_ticker.analysis.xbrl_parser import XBRLParser
from blue_ticker.constants.xbrl import XBRL_SECTIONS

from .edinet_fetcher import EdinetFetcher

_SECTION_EXTRACTORS: dict[str, Callable[[Path], Any]] = {
    "segments": extract_segment_info,
    "geography": extract_geography_info,
}
_SPECIAL_SECTIONS: frozenset[str] = frozenset(_SECTION_EXTRACTORS.keys())
_VALID_SECTIONS: frozenset[str] = frozenset(XBRL_SECTIONS.keys()) | _SPECIAL_SECTIONS


class FilingService:
    """EDINET filing の検索と XBRL セクション抽出を担当するサービス"""

    def __init__(self, edinet_client: EdinetAPIClient) -> None:
        self.edinet_client = edinet_client

    async def search_filings(
        self,
        code: str,
        max_years: int = 10,
        doc_types: list[str] | None = None,
        max_documents: int = 10,
    ) -> list[dict[str, Any]]:
        """EDINET書類を検索"""
        edinet_fetcher = EdinetFetcher(self.edinet_client)
        requested = set(doc_types or [])
        docs: list[dict[str, Any]] = []

        if not requested or requested.intersection({"120", "130"}):
            docs.extend(await edinet_fetcher._search_edinet_annual_docs(code, max_years))
        if not requested or requested.intersection({"140", "160"}):
            docs.extend(await edinet_fetcher._search_edinet_half_docs(code, max_years))

        if requested:
            docs = [doc for doc in docs if doc.get("docTypeCode") in requested]

        seen: set[str] = set()
        unique_docs: list[dict[str, Any]] = []
        for doc in sorted(docs, key=lambda d: str(d.get("submitDateTime") or ""), reverse=True):
            doc_id = doc.get("docID")
            if not isinstance(doc_id, str) or doc_id in seen:
                continue
            seen.add(doc_id)
            unique_docs.append(doc)
            if len(unique_docs) >= max_documents:
                break
        return unique_docs

    async def extract_filing_content(
        self,
        code: str,
        doc_id: str | None = None,
        sections: list[str] | None = None,
    ) -> dict[str, Any]:
        """EDINET書類からセクションを抽出"""
        if sections is not None:
            unknown = [s for s in sections if s not in _VALID_SECTIONS]
            if unknown:
                raise ValueError(f"Unknown section(s): {unknown}. Valid: {sorted(_VALID_SECTIONS)}")

        meta: dict[str, Any] = {}
        selected_doc_id = doc_id
        if not selected_doc_id:
            docs = await self.search_filings(
                code=code,
                max_years=5,
                doc_types=["120", "140"],
                max_documents=5,
            )
            if not docs:
                raise ValueError(f"No Securities Report found for {code}")
            doc = docs[0]
            selected_doc_id = doc["docID"]
            raw_fy_end: str = doc.get("edinet_fy_end") or ""
            meta = {
                "fy_end": raw_fy_end[:7] if raw_fy_end else None,
            }

        xbrl_dir = await self.edinet_client.download_document(selected_doc_id, 1)
        if not xbrl_dir:
            raise ValueError("Document not found or download failed")

        base = {"doc_id": selected_doc_id, **meta}
        extract_all = sections is None

        result: dict[str, Any] = {}

        for section_id, extractor in _SECTION_EXTRACTORS.items():
            if extract_all or section_id in sections:  # type: ignore[operator]
                result[section_id] = extractor(xbrl_dir)

        xbrl_sections = [s for s in (sections or []) if s not in _SPECIAL_SECTIONS]
        if extract_all or xbrl_sections:
            parser = XBRLParser()
            all_sections = parser.extract_sections_by_type(xbrl_dir)
            if extract_all:
                result.update({k: v for k, v in all_sections.items() if v})
            else:
                for s in xbrl_sections:
                    if all_sections.get(s):
                        result[s] = all_sections[s]

        return {**base, "sections": result}
