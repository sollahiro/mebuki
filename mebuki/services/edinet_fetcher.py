"""
EDINETフェッチャー

EDINET APIからの有価証券報告書取得と有利子負債抽出を担当。
"""

import asyncio
import logging
import time
from dataclasses import dataclass
from importlib import import_module
from pathlib import Path
from typing import Any
from collections.abc import Callable, AsyncGenerator

from mebuki.api.jquants_client import JQuantsAPIClient
from mebuki.api.edinet_client import EdinetAPIClient
from mebuki.utils.jquants_utils import prepare_edinet_search_data

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ExtractorSpec:
    key: str
    label: str
    module: str
    fn_name: str
    result_check: Callable[[dict], bool] | None = None

    def load_fn(self) -> Callable:
        return getattr(import_module(self.module), self.fn_name)


_EXTRACTOR_SPECS: list[ExtractorSpec] = [
    ExtractorSpec("ibd", "IBD", "mebuki.analysis.interest_bearing_debt", "extract_interest_bearing_debt"),
    ExtractorSpec("gp", "GP", "mebuki.analysis.gross_profit", "extract_gross_profit"),
    ExtractorSpec("ie", "IE", "mebuki.analysis.interest_expense", "extract_interest_expense"),
    ExtractorSpec("tax", "TAX", "mebuki.analysis.tax_expense", "extract_tax_expense"),
    ExtractorSpec("emp", "EMP", "mebuki.analysis.employees", "extract_employees"),
    ExtractorSpec("nr", "NR", "mebuki.analysis.net_revenue", "extract_net_revenue", result_check=lambda r: r.get("found")),
    ExtractorSpec("op", "OP", "mebuki.analysis.operating_profit", "extract_operating_profit"),
]

_SPEC_BY_KEY: dict[str, ExtractorSpec] = {spec.key: spec for spec in _EXTRACTOR_SPECS}


class EdinetFetcher:
    """EDINETからの有価証券報告書取得・有利子負債抽出"""

    def __init__(
        self,
        api_client: JQuantsAPIClient,
        edinet_client: EdinetAPIClient | None,
    ):
        self.api_client = api_client
        self.edinet_client = edinet_client
        self._doc_cache: dict = {}
        self._doc_locks: dict = {}

    async def _get_annual_docs(
        self,
        code: str,
        financial_data: list[dict[str, Any]],
        max_years: int,
    ) -> list:
        """search_recent_reports の結果をインスタンス内でキャッシュ。

        同一 code+max_years を asyncio.gather で並列呼び出しした場合に
        ネットワーク呼び出しを1回に集約する。
        """
        key = (code, max_years)
        if key not in self._doc_locks:
            self._doc_locks[key] = asyncio.Lock()
        async with self._doc_locks[key]:
            if key not in self._doc_cache:
                self._doc_cache[key] = await self.search_recent_reports(
                    code=code,
                    jquants_data=financial_data,
                    max_years=max_years,
                    doc_types=["120"],
                    max_documents=max_years,
                )
            return self._doc_cache[key]

    async def search_recent_reports(
        self,
        code: str,
        jquants_data: list[dict[str, Any]],
        max_years: int = 5,
        doc_types: list[str] | None = None,
        max_documents: int = 10,
    ) -> list[dict[str, Any]]:
        """J-QUANTS年度データをもとに、直近N年分のEDINET書類を検索する。

        EDINET API client はレコード単位の検索だけを担当し、J-QUANTS側の
        年度抽出・対象期間選定はサービス層で行う。
        """
        if not self.edinet_client or not self.edinet_client.api_key or not jquants_data:
            return []

        annual_data_idx, years_list = prepare_edinet_search_data(
            jquants_data,
            max_records=max_years * 3,
        )
        target_years = years_list[:max_years]
        recent_data = [
            record for record in annual_data_idx
            if record.get("fiscal_year") in target_years
        ]

        return await self.edinet_client.search_documents(
            code=code,
            years=target_years,
            jquants_data=recent_data,
            doc_type_code=doc_types[0] if doc_types and len(doc_types) == 1 else None,
            max_documents=max_documents,
        )

    async def fetch_latest_annual_report(
        self,
        code: str,
        jquants_data: list[dict[str, Any]],
    ) -> dict[str, Any] | None:
        """最新の有価証券報告書(120)を1件取得する。"""
        docs = await self.search_recent_reports(
            code,
            jquants_data,
            max_years=10,
            doc_types=["120"],
        )
        annual_reports = [doc for doc in docs if doc.get("docTypeCode") == "120"]
        if annual_reports:
            return sorted(annual_reports, key=lambda x: x.get("submitDateTime", ""), reverse=True)[0]
        return None

    async def predownload_and_parse(
        self,
        code: str,
        financial_data: list[dict[str, Any]],
        max_years: int,
    ) -> dict[str, tuple[Path, dict]]:
        """全年度のXBRL文書を一括ダウンロード・パースする。

        Returns: { "YYYYMMDD": (xbrl_dir_path, pre_parsed_dict) }
        """
        from mebuki.analysis.xbrl_utils import collect_all_numeric_elements

        if not self.edinet_client or not self.edinet_client.api_key:
            return {}

        docs = await self._get_annual_docs(code, financial_data, max_years)

        async def _dl_parse(doc: dict) -> tuple[str, tuple[Path, dict] | None]:
            fy_end_8 = doc.get("jquants_fy_end", "").replace("-", "")
            if not fy_end_8:
                return "", None
            try:
                xbrl_dir = await asyncio.wait_for(
                    self.edinet_client.download_document(doc["docID"], 1),
                    timeout=30.0,
                )
                if not xbrl_dir:
                    return fy_end_8, None
                xbrl_path = Path(xbrl_dir)
                pre_parsed = collect_all_numeric_elements(xbrl_path)
                return fy_end_8, (xbrl_path, pre_parsed)
            except asyncio.TimeoutError:
                logger.warning(f"[PARSE] {code} {fy_end_8}: XBRLダウンロードタイムアウト(30s)")
                return fy_end_8, None
            except Exception as e:
                logger.warning(f"[PARSE] {code} {fy_end_8}: パースエラー - {e}")
                return fy_end_8, None

        _t0 = time.perf_counter()
        raw = await asyncio.gather(*[_dl_parse(doc) for doc in docs], return_exceptions=True)
        out: dict[str, tuple[Path, dict]] = {}
        for res in raw:
            if isinstance(res, Exception):
                continue
            k, v = res
            if k and v is not None:
                out[k] = v
        logger.info(f"[PARSE] {code}: XBRL一括パース完了 {len(out)}件 {time.perf_counter() - _t0:.2f}s")
        return out

    async def _run_extraction(
        self,
        doc: dict,
        code: str,
        prefix: str,
        extract_fn: Callable,
        *,
        result_check: Callable[[dict], bool] | None = None,
        pre_parsed_map: dict[str, tuple[Path, dict]] | None = None,
    ) -> tuple[str, dict | None]:
        fy_end_8 = doc.get("jquants_fy_end", "").replace("-", "")
        if not fy_end_8:
            return "", None
        try:
            if pre_parsed_map is not None and fy_end_8 in pre_parsed_map:
                xbrl_path, pre_parsed = pre_parsed_map[fy_end_8]
                result = extract_fn(xbrl_path, pre_parsed=pre_parsed)
            else:
                xbrl_dir = await asyncio.wait_for(
                    self.edinet_client.download_document(doc["docID"], 1),
                    timeout=30.0,
                )
                if not xbrl_dir:
                    logger.warning(f"[{prefix}] {code} {fy_end_8}: XBRLダウンロード失敗")
                    return fy_end_8, None
                result = extract_fn(Path(xbrl_dir))
            if result_check is not None and not result_check(result):
                return fy_end_8, None
            result["docID"] = doc["docID"]
            logger.info(f"[{prefix}] {code} {fy_end_8}: docID={doc['docID']}")
            return fy_end_8, result
        except asyncio.TimeoutError:
            logger.warning(f"[{prefix}] {code} {fy_end_8}: XBRLダウンロードタイムアウト(30s)")
            return fy_end_8, None
        except Exception as e:
            logger.warning(f"[{prefix}] {code} {fy_end_8}: 抽出エラー - {e}")
            return fy_end_8, None

    def _collect_results(self, results: list, code: str, prefix: str) -> dict:
        out: dict = {}
        for res in results:
            if isinstance(res, Exception):
                logger.warning(f"[{prefix}] {code} gather エラー: {res}")
                continue
            k, v = res
            if k and v is not None:
                out[k] = v
        return out

    async def fetch_edinet_data_async(
        self,
        code: str,
        financial_data: list[dict[str, Any]],
        max_documents: int = 10,
    ) -> dict[str, Any]:
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
        financial_data: list[dict[str, Any]],
        max_documents: int = 20,
    ) -> AsyncGenerator[dict[str, Any], None]:
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
        years: list[int],
        jquants_annual_data: list[dict[str, Any]] | None = None,
        progress_callback: Callable | None = None,
        max_documents: int = 20,
    ) -> dict[int, list[dict[str, Any]]]:
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

    async def get_doc_ids_by_year(
        self,
        code: str,
        financial_data: list[dict[str, Any]],
        max_years: int,
    ) -> dict[str, str]:
        """年度別にEDINET有価証券報告書のdocIDを返す。Returns: { "YYYYMMDD": docID }"""
        if not self.edinet_client or not self.edinet_client.api_key:
            return {}
        docs = await self._get_annual_docs(code, financial_data, max_years)
        result: dict[str, str] = {}
        for doc in docs:
            fy_end = doc.get("jquants_fy_end", "").replace("-", "")
            if fy_end:
                result[fy_end] = doc["docID"]
        return result

    async def _extract_metric_by_year(
        self,
        spec: ExtractorSpec,
        code: str,
        financial_data: list[dict[str, Any]],
        max_years: int,
        *,
        pre_parsed_map: dict[str, tuple[Path, dict]] | None = None,
    ) -> dict[str, dict]:
        if not self.edinet_client or not self.edinet_client.api_key:
            return {}
        extract_fn = spec.load_fn()
        docs = await self._get_annual_docs(code, financial_data, max_years)
        logger.info(f"[{spec.label}] {code}: {len(docs)}件のEDINET文書を検索")
        _t0 = time.perf_counter()
        results = await asyncio.gather(
            *[self._run_extraction(doc, code, spec.label, extract_fn, result_check=spec.result_check, pre_parsed_map=pre_parsed_map) for doc in docs],
            return_exceptions=True,
        )
        by_year = self._collect_results(results, code, spec.label)
        logger.info(f"[{spec.label}] {code}: 抽出完了 {len(by_year)}件 {time.perf_counter() - _t0:.2f}s")
        return by_year

    async def extract_all_by_year(
        self,
        code: str,
        financial_data: list[dict[str, Any]],
        max_years: int,
        *,
        pre_parsed_map: dict[str, tuple[Path, dict]] | None = None,
    ) -> dict[str, dict[str, dict]]:
        """全メトリクスを並列抽出。Returns: {"ibd": {...}, "gp": {...}, ..., "doc_ids": {...}}"""
        tasks: list = [
            self._extract_metric_by_year(spec, code, financial_data, max_years, pre_parsed_map=pre_parsed_map)
            for spec in _EXTRACTOR_SPECS
        ] + [self.get_doc_ids_by_year(code, financial_data, max_years)]
        results = await asyncio.gather(*tasks)
        out: dict[str, dict[str, dict]] = {
            spec.key: result
            for spec, result in zip(_EXTRACTOR_SPECS, results)
        }
        out["doc_ids"] = results[-1]
        return out

    async def extract_ibd_by_year(
        self,
        code: str,
        financial_data: list[dict[str, Any]],
        max_years: int,
        *,
        pre_parsed_map: dict[str, tuple[Path, dict]] | None = None,
    ) -> dict[str, dict]:
        """年度別に有利子負債を抽出。Returns: { "YYYYMMDD": ibd_result_dict }"""
        return await self._extract_metric_by_year(_SPEC_BY_KEY["ibd"], code, financial_data, max_years, pre_parsed_map=pre_parsed_map)

    async def extract_half_year_edinet_data(
        self,
        code: str,
        financial_data: list[dict[str, Any]],
        max_years: int,
    ) -> dict[str, dict]:
        """2Q期間のEDINETデータ（GrossProfit + CF + IBD）を年度別に抽出。

        Returns: { "YYYYMMDD": {"gp": gp_result_dict, "cf": cf_result_dict, "ibd": ibd_result_dict} }
        """
        from mebuki.analysis.gross_profit import extract_gross_profit
        from mebuki.analysis.cash_flow import extract_cash_flow

        if not self.edinet_client or not self.edinet_client.api_key:
            return {}

        # 2Qレコードのみ抽出（未来の開示日を除外して最新max_years件）
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
                from mebuki.analysis.interest_bearing_debt import extract_interest_bearing_debt
                from mebuki.analysis.xbrl_utils import collect_all_numeric_elements
                xbrl_path = Path(xbrl_dir)
                pre_parsed = collect_all_numeric_elements(xbrl_path)
                gp = extract_gross_profit(xbrl_path, pre_parsed=pre_parsed)
                cf = extract_cash_flow(xbrl_path, pre_parsed=pre_parsed)
                ibd = extract_interest_bearing_debt(xbrl_path, pre_parsed=pre_parsed)
                gp["docID"] = doc["docID"]
                logger.info(
                    f"[HALF-EDINET] {code} {fy_end_8}: "
                    f"gp={gp.get('current')}, cfo={cf['cfo'].get('current')}, cfi={cf['cfi'].get('current')}, ibd={ibd.get('current')}, docID={doc['docID']}"
                )
                return fy_end_8, {"gp": gp, "cf": cf, "ibd": ibd}
            except asyncio.TimeoutError:
                logger.warning(f"[HALF-EDINET] {code} {fy_end_8}: XBRLダウンロードタイムアウト(30s)")
                return fy_end_8, None
            except Exception as e:
                logger.warning(f"[HALF-EDINET] {code} {fy_end_8}: 抽出エラー - {e}")
                return fy_end_8, None

        _t0 = time.perf_counter()
        results = await asyncio.gather(*[_process_doc(doc) for doc in docs], return_exceptions=True)
        half_data = self._collect_results(results, code, "HALF-EDINET")
        logger.info(f"[HALF-EDINET] {code}: 半期EDINETデータ抽出完了 {len(half_data)}件 {time.perf_counter() - _t0:.2f}s")
        return half_data

    async def extract_employees_by_year(
        self,
        code: str,
        financial_data: list[dict[str, Any]],
        max_years: int,
        *,
        pre_parsed_map: dict[str, tuple[Path, dict]] | None = None,
    ) -> dict[str, dict]:
        """年度別に従業員数を抽出。Returns: { "YYYYMMDD": employees_result_dict }"""
        return await self._extract_metric_by_year(_SPEC_BY_KEY["emp"], code, financial_data, max_years, pre_parsed_map=pre_parsed_map)

    async def extract_net_revenue_by_year(
        self,
        code: str,
        financial_data: list[dict[str, Any]],
        max_years: int,
        *,
        pre_parsed_map: dict[str, tuple[Path, dict]] | None = None,
    ) -> dict[str, dict]:
        """年度別に IFRS 純収益・事業利益を抽出。Returns: { "YYYYMMDD": nr_result_dict }"""
        return await self._extract_metric_by_year(_SPEC_BY_KEY["nr"], code, financial_data, max_years, pre_parsed_map=pre_parsed_map)

    async def extract_gross_profit_by_year(
        self,
        code: str,
        financial_data: list[dict[str, Any]],
        max_years: int,
        *,
        pre_parsed_map: dict[str, tuple[Path, dict]] | None = None,
    ) -> dict[str, dict]:
        """年度別に売上総利益を抽出。Returns: { "YYYYMMDD": gp_result_dict }"""
        return await self._extract_metric_by_year(_SPEC_BY_KEY["gp"], code, financial_data, max_years, pre_parsed_map=pre_parsed_map)

    async def extract_tax_expense_by_year(
        self,
        code: str,
        financial_data: list[dict[str, Any]],
        max_years: int,
        *,
        pre_parsed_map: dict[str, tuple[Path, dict]] | None = None,
    ) -> dict[str, dict]:
        """年度別に税引前利益・法人税等を抽出。Returns: { "YYYYMMDD": tax_result_dict }"""
        return await self._extract_metric_by_year(_SPEC_BY_KEY["tax"], code, financial_data, max_years, pre_parsed_map=pre_parsed_map)

    async def extract_interest_expense_by_year(
        self,
        code: str,
        financial_data: list[dict[str, Any]],
        max_years: int,
        *,
        pre_parsed_map: dict[str, tuple[Path, dict]] | None = None,
    ) -> dict[str, dict]:
        """年度別に支払利息（金融費用）を抽出。Returns: { "YYYYMMDD": ie_result_dict }"""
        return await self._extract_metric_by_year(_SPEC_BY_KEY["ie"], code, financial_data, max_years, pre_parsed_map=pre_parsed_map)

    async def extract_operating_profit_by_year(
        self,
        code: str,
        financial_data: list[dict[str, Any]],
        max_years: int,
        *,
        pre_parsed_map: dict[str, tuple[Path, dict]] | None = None,
    ) -> dict[str, dict]:
        """年度別に営業利益（または経常利益）を抽出。Returns: { "YYYYMMDD": op_result_dict }"""
        return await self._extract_metric_by_year(_SPEC_BY_KEY["op"], code, financial_data, max_years, pre_parsed_map=pre_parsed_map)
