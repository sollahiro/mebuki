"""
EDINET 書類検索・本文抽出サービス
"""

from typing import Any

from mebuki.analysis.xbrl_parser import XBRLParser

from .edinet_fetcher import EdinetFetcher


class FilingService:
    """EDINET filing の検索と XBRL セクション抽出を担当するサービス"""

    def __init__(self, api_client, edinet_client):
        self.api_client = api_client
        self.edinet_client = edinet_client

    async def search_filings(
        self,
        code: str,
        max_years: int = 10,
        doc_types: list[str] | None = None,
        max_documents: int = 10,
    ) -> list[dict[str, Any]]:
        """EDINET書類を検索"""
        fin_data = await self.api_client.get_financial_summary(code=code)
        edinet_fetcher = EdinetFetcher(self.api_client, self.edinet_client)
        return await edinet_fetcher.search_recent_reports(
            code=code,
            jquants_data=fin_data,
            max_years=max_years,
            doc_types=doc_types,
            max_documents=max_documents,
        )

    async def extract_filing_content(
        self,
        code: str,
        doc_id: str | None = None,
        sections: list[str] | None = None,
    ) -> dict[str, Any]:
        """EDINET書類からセクションを抽出"""
        requested_sections = sections or ["all"]

        meta: dict[str, Any] = {}
        if not doc_id:
            docs = await self.search_filings(
                code=code,
                max_years=5,
                doc_types=["120", "140"],
                max_documents=5,
            )
            if not docs:
                raise ValueError(f"No Securities Report found for {code}")
            doc = docs[0]
            doc_id = doc["docID"]
            meta = {
                "fiscal_year": doc.get("fiscal_year"),
                "period_type": doc.get("period_type"),
                "jquants_fy_end": doc.get("jquants_fy_end"),
            }

        xbrl_dir = await self.edinet_client.download_document(doc_id, 1)
        if not xbrl_dir:
            raise ValueError("Document not found or download failed")

        parser = XBRLParser()
        all_sections = parser.extract_sections_by_type(xbrl_dir)

        base = {"doc_id": doc_id, **meta}
        if "all" in requested_sections:
            return {**base, "sections": all_sections}

        result = {}
        for section in requested_sections:
            if section in all_sections:
                result[section] = all_sections[section]
        return {**base, "sections": result}
