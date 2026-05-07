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
        requested_sections = sections or ["all"]

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
            meta = {
                "fiscal_year": doc.get("fiscal_year"),
                "period_type": doc.get("period_type"),
                "edinet_fy_end": doc.get("edinet_fy_end"),
            }

        xbrl_dir = await self.edinet_client.download_document(selected_doc_id, 1)
        if not xbrl_dir:
            raise ValueError("Document not found or download failed")

        parser = XBRLParser()
        all_sections = parser.extract_sections_by_type(xbrl_dir)

        base = {"doc_id": selected_doc_id, **meta}
        if "all" in requested_sections:
            return {**base, "sections": all_sections}

        result = {}
        for section in requested_sections:
            if section in all_sections:
                result[section] = all_sections[section]
        return {**base, "sections": result}
