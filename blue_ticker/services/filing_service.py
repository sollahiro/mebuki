"""
EDINET 書類検索・本文抽出サービス
"""

from typing import Any

from blue_ticker.api.edinet_client import EdinetAPIClient
from blue_ticker.analysis.xbrl_parser import XBRLParser

from .edinet_fetcher import EdinetFetcher


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
        want_segments = sections is None or "segments" in sections
        want_geography = sections is None or "geography" in sections

        result: dict[str, Any] = {}

        if want_segments or want_geography:
            from blue_ticker.analysis.segment_extractor import (
                extract_segment_info,
                extract_geography_info,
            )
            if want_segments:
                result["segments"] = extract_segment_info(xbrl_dir)
            if want_geography:
                result["geography"] = extract_geography_info(xbrl_dir)

        _SPECIAL_SECTIONS = {"segments", "geography"}
        xbrl_sections = [s for s in (sections or []) if s not in _SPECIAL_SECTIONS]
        if extract_all or xbrl_sections:
            parser = XBRLParser()
            all_sections = parser.extract_sections_by_type(xbrl_dir)
            if extract_all:
                result.update(all_sections)
            else:
                for s in xbrl_sections:
                    if s in all_sections:
                        result[s] = all_sections[s]

        return {**base, "sections": result}
