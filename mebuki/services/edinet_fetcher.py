"""
EDINETフェッチャー

EDINET APIからの有価証券報告書取得と有利子負債抽出を担当。
"""

import asyncio
import logging
import time
from pathlib import Path
from typing import List, Dict, Any, Optional, Callable, AsyncGenerator

from mebuki.api.jquants_client import JQuantsAPIClient
from mebuki.api.edinet_client import EdinetAPIClient
from mebuki.utils.jquants_utils import prepare_edinet_search_data

logger = logging.getLogger(__name__)


class EdinetFetcher:
    """EDINETからの有価証券報告書取得・有利子負債抽出"""

    def __init__(
        self,
        api_client: JQuantsAPIClient,
        edinet_client: Optional[EdinetAPIClient],
    ):
        self.api_client = api_client
        self.edinet_client = edinet_client

    async def fetch_edinet_data_async(
        self,
        code: str,
        financial_data: List[Dict[str, Any]],
        max_documents: int = 10,
        edinet_code: Optional[str] = None,
    ) -> Dict[str, Any]:
        """EDINETデータを非同期で取得"""
        if not self.edinet_client:
            return {}
        try:
            if edinet_code is None:
                master_data = await self.api_client.get_equity_master(code=code)
                edinet_code = master_data[0].get("EdinetCode") if master_data else None

            results = {}
            async for data in self.fetch_edinet_reports_stream(
                code, financial_data, max_documents, edinet_code=edinet_code
            ):
                fy_key = data["fy_key"]
                report = data["report"]
                fy_key_str = str(fy_key)
                if fy_key_str not in results:
                    results[fy_key_str] = []
                results[fy_key_str].append(report)

            return results
        except Exception as e:
            logger.error(f"EDINET非同期データ取得エラー: {code} - {e}", exc_info=True)
            return {}

    async def fetch_edinet_reports_stream(
        self,
        code: str,
        financial_data: List[Dict[str, Any]],
        max_documents: int = 20,
        edinet_code: Optional[str] = None,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """EDINET書類を取得し、準備ができた段階で順次yieldする"""
        if not self.edinet_client or not self.edinet_client.api_key:
            logger.warning(f"EDINETクライアントが利用不可またはAPIキー未設定: code={code}")
            return

        try:
            if not edinet_code:
                master_data = await self.api_client.get_equity_master(code=code)
                edinet_code = master_data[0].get("EdinetCode") if master_data else None

            annual_data_idx, years_list = prepare_edinet_search_data(
                financial_data, max_records=max_documents * 3
            )

            all_docs = await self.edinet_client.search_documents(
                code,
                years=years_list,
                jquants_data=annual_data_idx,
                edinet_code=edinet_code,
                max_documents=max_documents,
            )

            if not all_docs:
                logger.info(f"EDINET書類が見つかりませんでした: code={code}")
                return

            all_docs.sort(key=lambda x: x.get("submitDateTime", ""), reverse=True)

            for doc in all_docs:
                doc_id = doc["docID"]
                dt = doc.get("docTypeCode")
                label = "有価証券報告書" if dt == "120" else "半期報告書"
                year = doc.get("fiscal_year")
                fy_key = doc.get("jquants_fy_end") or str(year)

                report_info = {
                    "docID": doc_id,
                    "submitDate": doc.get("submitDateTime", "")[:10],
                    "edinetCode": doc.get("edinetCode"),
                    "docType": label,
                    "docTypeCode": dt,
                    "fiscal_year": year,
                    "jquants_fy_end": fy_key,
                }

                yield {"year": year, "fy_key": fy_key, "report": report_info}

        except Exception as e:
            logger.error(f"EDINETストリーミング取得エラー: {code} - {e}", exc_info=True)

    async def fetch_edinet_reports(
        self,
        code: str,
        years: List[int],
        jquants_annual_data: Optional[List[Dict[str, Any]]] = None,
        progress_callback: Optional[Callable] = None,
        edinet_code: Optional[str] = None,
        max_documents: int = 20,
    ) -> Dict[int, List[Dict[str, Any]]]:
        """指定年度の有価証券報告書を取得"""
        results = {}
        async for data in self.fetch_edinet_reports_stream(
            code, jquants_annual_data, max_documents
        ):
            fy_key = data["fy_key"]
            report = data["report"]
            fy_key_str = str(fy_key)
            if fy_key_str not in results:
                results[fy_key_str] = []

            found = False
            for i, existing in enumerate(results[fy_key_str]):
                if existing["docID"] == report["docID"]:
                    results[fy_key_str][i] = report
                    found = True
                    break
            if not found:
                results[fy_key_str].append(report)

        return results

    async def extract_ibd_by_year(
        self,
        code: str,
        financial_data: List[Dict[str, Any]],
        max_years: int,
    ) -> Dict[str, dict]:
        """年度別に有利子負債を抽出。Returns: { "YYYYMMDD": ibd_result_dict }"""
        from mebuki.analysis.interest_bearing_debt import extract_interest_bearing_debt

        if not self.edinet_client or not self.edinet_client.api_key:
            return {}

        docs = await self.edinet_client.search_recent_reports(
            code, financial_data, max_years, ["120"], max_years,
        )
        logger.info(f"[IBD] {code}: {len(docs)}件のEDINET文書を検索")

        async def _process_doc(doc: dict) -> tuple[str, dict | None]:
            fy_end_8 = doc.get("jquants_fy_end", "").replace("-", "")
            if not fy_end_8:
                return "", None
            try:
                xbrl_dir = await self.edinet_client.download_document(doc["docID"], 1)
                if not xbrl_dir:
                    logger.warning(f"[IBD] {code} {fy_end_8}: XBRLダウンロード失敗")
                    return fy_end_8, None
                ibd = extract_interest_bearing_debt(Path(xbrl_dir))
                logger.info(
                    f"[IBD] {code} {fy_end_8}: current={ibd.get('current')}, method={ibd.get('method')}"
                )
                return fy_end_8, ibd
            except Exception as e:
                logger.warning(f"[IBD] {code} {fy_end_8}: 抽出エラー - {e}")
                return fy_end_8, None

        _t0 = time.perf_counter()
        results = await asyncio.gather(
            *[_process_doc(doc) for doc in docs], return_exceptions=True
        )
        ibd_by_year: dict = {}
        for res in results:
            if isinstance(res, Exception):
                logger.warning(f"[IBD] {code} gather エラー: {res}")
                continue
            k, v = res
            if k and v is not None:
                ibd_by_year[k] = v

        _elapsed = time.perf_counter() - _t0
        logger.info(f"[IBD] {code}: IBD抽出完了 {len(ibd_by_year)}件 {_elapsed:.2f}s")
        return ibd_by_year
