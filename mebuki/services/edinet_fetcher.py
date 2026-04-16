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
    ) -> Dict[str, Any]:
        """EDINETデータを非同期で取得"""
        if not self.edinet_client:
            return {}
        try:
            results = {}
            async for data in self.fetch_edinet_reports_stream(
                code, financial_data, max_documents
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
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """EDINET書類を取得し、準備ができた段階で順次yieldする"""
        if not self.edinet_client or not self.edinet_client.api_key:
            logger.warning(f"EDINETクライアントが利用不可またはAPIキー未設定: code={code}")
            return

        try:
            annual_data_idx, years_list = prepare_edinet_search_data(
                financial_data, max_records=max_documents * 3
            )

            all_docs = await self.edinet_client.search_documents(
                code,
                years=years_list,
                jquants_data=annual_data_idx,
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
                xbrl_dir = await asyncio.wait_for(
                    self.edinet_client.download_document(doc["docID"], 1),
                    timeout=30.0,
                )
                if not xbrl_dir:
                    logger.warning(f"[IBD] {code} {fy_end_8}: XBRLダウンロード失敗")
                    return fy_end_8, None
                ibd = extract_interest_bearing_debt(Path(xbrl_dir))
                ibd["docID"] = doc["docID"]
                logger.info(
                    f"[IBD] {code} {fy_end_8}: current={ibd.get('current')}, method={ibd.get('method')}, docID={doc['docID']}"
                )
                return fy_end_8, ibd
            except asyncio.TimeoutError:
                logger.warning(f"[IBD] {code} {fy_end_8}: XBRLダウンロードタイムアウト(30s)")
                return fy_end_8, None
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

    async def extract_half_year_edinet_data(
        self,
        code: str,
        financial_data: List[Dict[str, Any]],
        max_years: int,
    ) -> Dict[str, dict]:
        """2Q期間のEDINETデータ（GrossProfit + CF）を年度別に抽出。

        Returns: { "YYYYMMDD": {"gp": gp_result_dict, "cf": cf_result_dict} }
        """
        from mebuki.analysis.gross_profit import extract_gross_profit
        from mebuki.analysis.cash_flow import extract_cash_flow

        if not self.edinet_client or not self.edinet_client.api_key:
            return {}

        # 2Qレコードのみ抽出（未来の開示日を除外して最新max_years件）
        today = time.time()
        from datetime import datetime as _dt
        now = _dt.now()

        q2_records_raw = []
        for r in financial_data:
            if r.get("CurPerType") != "2Q":
                continue
            disc_date = r.get("DiscDate", "")
            if disc_date:
                from mebuki.utils.fiscal_year import parse_date_string as _parse
                dt = _parse(disc_date)
                if dt and dt > now:
                    continue
            q2_records_raw.append(r)

        # CurFYEn ごとに1件に集約（複数ある場合は最も遅い DiscDate を採用）
        # 重複レコードが max_years の枠を消費しないようにする
        seen_fy_ends: dict = {}
        for r in q2_records_raw:
            fy_en = r.get("CurFYEn", "")
            if fy_en not in seen_fy_ends or r.get("DiscDate", "") > seen_fy_ends[fy_en].get("DiscDate", ""):
                seen_fy_ends[fy_en] = r

        q2_records = sorted(seen_fy_ends.values(), key=lambda x: x.get("CurFYEn", ""), reverse=True)[:max_years]
        if not q2_records:
            return {}

        docs = await self.edinet_client.search_documents(
            code=code,
            jquants_data=q2_records,
            max_documents=max_years,
        )
        logger.info(f"[HALF-EDINET] {code}: {len(docs)}件の2Q文書を検索")

        async def _process_doc(doc: dict) -> tuple[str, dict | None]:
            fy_end_8 = doc.get("jquants_fy_end", "").replace("-", "")
            if not fy_end_8:
                return "", None
            try:
                xbrl_dir = await asyncio.wait_for(
                    self.edinet_client.download_document(doc["docID"], 1),
                    timeout=30.0,
                )
                if not xbrl_dir:
                    logger.warning(f"[HALF-EDINET] {code} {fy_end_8}: XBRLダウンロード失敗")
                    return fy_end_8, None
                gp = extract_gross_profit(Path(xbrl_dir))
                cf = extract_cash_flow(Path(xbrl_dir))
                gp["docID"] = doc["docID"]
                logger.info(
                    f"[HALF-EDINET] {code} {fy_end_8}: "
                    f"gp={gp.get('current')}, cfo={cf['cfo'].get('current')}, cfi={cf['cfi'].get('current')}, docID={doc['docID']}"
                )
                return fy_end_8, {"gp": gp, "cf": cf}
            except asyncio.TimeoutError:
                logger.warning(f"[HALF-EDINET] {code} {fy_end_8}: XBRLダウンロードタイムアウト(30s)")
                return fy_end_8, None
            except Exception as e:
                logger.warning(f"[HALF-EDINET] {code} {fy_end_8}: 抽出エラー - {e}")
                return fy_end_8, None

        _t0 = time.perf_counter()
        results = await asyncio.gather(
            *[_process_doc(doc) for doc in docs], return_exceptions=True
        )
        half_data: dict = {}
        for res in results:
            if isinstance(res, Exception):
                logger.warning(f"[HALF-EDINET] {code} gather エラー: {res}")
                continue
            k, v = res
            if k and v is not None:
                half_data[k] = v

        _elapsed = time.perf_counter() - _t0
        logger.info(f"[HALF-EDINET] {code}: 半期EDINETデータ抽出完了 {len(half_data)}件 {_elapsed:.2f}s")
        return half_data

    async def extract_gross_profit_by_year(
        self,
        code: str,
        financial_data: List[Dict[str, Any]],
        max_years: int,
    ) -> Dict[str, dict]:
        """年度別に売上総利益を抽出。Returns: { "YYYYMMDD": gp_result_dict }"""
        from mebuki.analysis.gross_profit import extract_gross_profit

        if not self.edinet_client or not self.edinet_client.api_key:
            return {}

        docs = await self.edinet_client.search_recent_reports(
            code, financial_data, max_years, ["120"], max_years,
        )
        logger.info(f"[GP] {code}: {len(docs)}件のEDINET文書を検索")

        async def _process_doc(doc: dict) -> tuple[str, dict | None]:
            fy_end_8 = doc.get("jquants_fy_end", "").replace("-", "")
            if not fy_end_8:
                return "", None
            try:
                xbrl_dir = await asyncio.wait_for(
                    self.edinet_client.download_document(doc["docID"], 1),
                    timeout=30.0,
                )
                if not xbrl_dir:
                    logger.warning(f"[GP] {code} {fy_end_8}: XBRLダウンロード失敗")
                    return fy_end_8, None
                gp = extract_gross_profit(Path(xbrl_dir))
                gp["docID"] = doc["docID"]
                logger.info(
                    f"[GP] {code} {fy_end_8}: current={gp.get('current')}, method={gp.get('method')}, docID={doc['docID']}"
                )
                return fy_end_8, gp
            except asyncio.TimeoutError:
                logger.warning(f"[GP] {code} {fy_end_8}: XBRLダウンロードタイムアウト(30s)")
                return fy_end_8, None
            except Exception as e:
                logger.warning(f"[GP] {code} {fy_end_8}: 抽出エラー - {e}")
                return fy_end_8, None

        _t0 = time.perf_counter()
        results = await asyncio.gather(
            *[_process_doc(doc) for doc in docs], return_exceptions=True
        )
        gp_by_year: dict = {}
        for res in results:
            if isinstance(res, Exception):
                logger.warning(f"[GP] {code} gather エラー: {res}")
                continue
            k, v = res
            if k and v is not None:
                gp_by_year[k] = v

        _elapsed = time.perf_counter() - _t0
        logger.info(f"[GP] {code}: GP抽出完了 {len(gp_by_year)}件 {_elapsed:.2f}s")
        return gp_by_year
