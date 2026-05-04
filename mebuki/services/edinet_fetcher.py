"""
EDINETフェッチャー

EDINET APIからの有価証券報告書取得と有利子負債抽出を担当。
"""

import asyncio
import logging
import time
from collections.abc import AsyncGenerator, Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, TypeAlias

from mebuki import __version__
from mebuki.api.jquants_client import JQuantsAPIClient
from mebuki.api.edinet_client import EdinetAPIClient
from mebuki.analysis.balance_sheet import extract_balance_sheet
from mebuki.analysis.depreciation import extract_depreciation
from mebuki.analysis.employees import extract_employees
from mebuki.analysis.gross_profit import extract_gross_profit
from mebuki.analysis.interest_bearing_debt import extract_interest_bearing_debt
from mebuki.analysis.interest_expense import extract_interest_expense
from mebuki.analysis.net_revenue import extract_net_revenue
from mebuki.analysis.operating_profit import extract_operating_profit
from mebuki.analysis.order_book import extract_order_book
from mebuki.analysis.tax_expense import extract_tax_expense
from mebuki.utils.cache import CacheManager
from mebuki.utils.jquants_utils import prepare_edinet_search_data
from mebuki.utils.xbrl_result_types import GrossProfitResult, HalfYearEdinetEntry, XbrlTagElements

logger = logging.getLogger(__name__)

_EDINET_DOCS_CACHE_VERSION = "edinet-docs-v2"
_XBRL_PARSE_CACHE_VERSION = ".".join(__version__.split(".")[:2]) + ":xbrl-parse"

_PreParsedMap: TypeAlias = dict[str, tuple[Path, XbrlTagElements]]
_MetricByYear: TypeAlias = dict[str, dict[str, Any]]
_AllMetrics: TypeAlias = dict[str, dict[str, Any]]
_DocCacheKey: TypeAlias = tuple[str, int] | tuple[str, int, str]


def _fy_end_key(value: object) -> str:
    return value.replace("-", "") if isinstance(value, str) else ""


def _is_valid_xbrl_parse_cache(data: object) -> bool:
    """dict[str, dict[str, float]] 相当の shape を簡易検証する。"""
    if not isinstance(data, dict):
        return False
    for value in data.values():
        if not isinstance(value, dict):
            return False
        if not all(isinstance(number, (int, float)) and not isinstance(number, bool) for number in value.values()):
            return False
    return True


@dataclass(frozen=True)
class ExtractorSpec:
    key: str
    label: str
    extract_fn: Callable
    result_check: Callable[[dict[str, Any]], bool] | None = None


_EXTRACTOR_SPECS: list[ExtractorSpec] = [
    ExtractorSpec("ibd", "IBD", extract_interest_bearing_debt),
    ExtractorSpec(
        "bs",
        "BS",
        extract_balance_sheet,
        result_check=lambda r: any(
            r.get(key) is not None
            for key in (
                "current_assets",
                "non_current_assets",
                "current_liabilities",
                "non_current_liabilities",
                "net_assets",
            )
        ),
    ),
    ExtractorSpec("gp", "GP", extract_gross_profit),
    ExtractorSpec("ie", "IE", extract_interest_expense),
    ExtractorSpec("tax", "TAX", extract_tax_expense),
    ExtractorSpec("emp", "EMP", extract_employees),
    ExtractorSpec("nr", "NR", extract_net_revenue, result_check=lambda r: bool(r.get("found"))),
    ExtractorSpec("op", "OP", extract_operating_profit),
    ExtractorSpec("da", "DA", extract_depreciation),
    ExtractorSpec(
        "ob",
        "OB",
        extract_order_book,
        result_check=lambda r: r.get("order_intake") is not None or r.get("order_backlog") is not None,
    ),
]

_SPEC_BY_KEY: dict[str, ExtractorSpec] = {spec.key: spec for spec in _EXTRACTOR_SPECS}


class EdinetFetcher:
    """EDINETからの有価証券報告書取得・有利子負債抽出"""

    def __init__(
        self,
        api_client: JQuantsAPIClient,
        edinet_client: EdinetAPIClient | None,
        *,
        cache_manager: CacheManager | None = None,
    ):
        self.api_client = api_client
        self.edinet_client = edinet_client
        self.cache_manager = cache_manager
        self._doc_cache: dict[_DocCacheKey, list[dict[str, Any]]] = {}
        self._doc_locks: dict[_DocCacheKey, asyncio.Lock] = {}

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
        persistent_key = f"edinet_docs_{code}_{max_years}"
        if key not in self._doc_locks:
            self._doc_locks[key] = asyncio.Lock()
        async with self._doc_locks[key]:
            if key not in self._doc_cache:
                if self.cache_manager is not None:
                    cached = self.cache_manager.get(persistent_key)
                    if (
                        isinstance(cached, dict)
                        and cached.get("_cache_version") == _EDINET_DOCS_CACHE_VERSION
                        and isinstance(cached.get("docs"), list)
                    ):
                        self._doc_cache[key] = cached["docs"]
                        return self._doc_cache[key]

                annual_financial_data = [
                    record for record in financial_data
                    if record.get("CurPerType") == "FY"
                ]

                docs = await self.search_recent_reports(
                    code=code,
                    jquants_data=annual_financial_data,
                    max_years=max_years,
                    doc_types=["120"],
                    max_documents=max_years,
                )
                self._doc_cache[key] = docs
                if self.cache_manager is not None:
                    self.cache_manager.set(
                        persistent_key,
                        {"_cache_version": _EDINET_DOCS_CACHE_VERSION, "docs": docs},
                    )
            return self._doc_cache[key]

    def _prepare_q2_records(
        self,
        financial_data: list[dict[str, Any]],
        max_years: int,
    ) -> list[dict[str, Any]]:
        """2Qレコードを抽出し、年度末ごとに最新開示日へ集約する。"""
        from datetime import datetime as _dt
        from mebuki.utils.fiscal_year import parse_date_string as _parse

        now = _dt.now()
        q2_records_raw: list[dict[str, Any]] = []
        for record in financial_data:
            if record.get("CurPerType") != "2Q":
                continue
            disc_date = record.get("DiscDate", "")
            if disc_date:
                dt = _parse(disc_date)
                if dt and dt > now:
                    continue
            q2_records_raw.append(record)

        seen_fy_ends: dict[str, dict[str, Any]] = {}
        for record in q2_records_raw:
            fy_end = record.get("CurFYEn", "")
            if fy_end not in seen_fy_ends or record.get("DiscDate", "") > seen_fy_ends[fy_end].get("DiscDate", ""):
                seen_fy_ends[fy_end] = record

        return sorted(
            seen_fy_ends.values(),
            key=lambda item: item.get("CurFYEn", ""),
            reverse=True,
        )[:max_years]

    async def _get_half_year_docs(
        self,
        code: str,
        financial_data: list[dict[str, Any]],
        max_years: int,
    ) -> list[dict[str, Any]]:
        key = (code, max_years, "2Q")
        persistent_key = f"edinet_docs_{code}_{max_years}_2Q"
        if key not in self._doc_locks:
            self._doc_locks[key] = asyncio.Lock()
        async with self._doc_locks[key]:
            if key not in self._doc_cache:
                if self.cache_manager is not None:
                    cached = self.cache_manager.get(persistent_key)
                    if (
                        isinstance(cached, dict)
                        and cached.get("_cache_version") == _EDINET_DOCS_CACHE_VERSION
                        and isinstance(cached.get("docs"), list)
                    ):
                        self._doc_cache[key] = cached["docs"]
                        return self._doc_cache[key]

                records = self._prepare_q2_records(financial_data, max_years)
                if not records or not self.edinet_client:
                    docs: list[dict[str, Any]] = []
                else:
                    docs = await self.edinet_client.search_documents(
                        code=code,
                        jquants_data=records,
                        max_documents=max_years,
                    )
                self._doc_cache[key] = docs
                if self.cache_manager is not None:
                    self.cache_manager.set(
                        persistent_key,
                        {"_cache_version": _EDINET_DOCS_CACHE_VERSION, "docs": docs},
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
    ) -> _PreParsedMap:
        """全年度のXBRL文書を一括ダウンロード・パースする。

        Returns: { "YYYYMMDD": (xbrl_dir_path, pre_parsed_dict) }
        """
        if not self.edinet_client or not self.edinet_client.api_key:
            return {}
        docs = await self._get_annual_docs(code, financial_data, max_years)
        return await self._download_and_parse_docs(docs, code)

    async def _download_and_parse_docs(
        self,
        docs: list[dict[str, Any]],
        code: str,
    ) -> _PreParsedMap:
        """XBRL文書を一括ダウンロード・パースする。"""
        from mebuki.analysis.xbrl_utils import collect_all_numeric_elements

        if self.edinet_client is None:
            return {}
        client = self.edinet_client

        async def _dl_parse(doc: dict[str, Any]) -> tuple[str, tuple[Path, XbrlTagElements] | None]:
            fy_end_8 = _fy_end_key(doc.get("jquants_fy_end"))
            doc_id = doc["docID"]
            if not fy_end_8:
                return "", None
            parse_cache_key = f"xbrl_parsed_{doc_id}"
            try:
                xbrl_dir = await asyncio.wait_for(
                    client.download_document(doc_id, 1),
                    timeout=30.0,
                )
                if not xbrl_dir:
                    return fy_end_8, None
                xbrl_path = Path(xbrl_dir)
                if self.cache_manager is not None:
                    cached = self.cache_manager.get(parse_cache_key)
                    if (
                        isinstance(cached, dict)
                        and cached.get("_cache_version") == _XBRL_PARSE_CACHE_VERSION
                        and _is_valid_xbrl_parse_cache(cached.get("data"))
                    ):
                        return fy_end_8, (xbrl_path, cached["data"])
                pre_parsed = collect_all_numeric_elements(xbrl_path)
                if self.cache_manager is not None:
                    self.cache_manager.set(parse_cache_key, {
                        "_cache_version": _XBRL_PARSE_CACHE_VERSION,
                        "data": pre_parsed,
                    })
                return fy_end_8, (xbrl_path, pre_parsed)
            except asyncio.TimeoutError:
                logger.warning(f"[PARSE] {code} {fy_end_8}: XBRLダウンロードタイムアウト(30s)")
                return fy_end_8, None
            except Exception as e:
                logger.warning(f"[PARSE] {code} {fy_end_8}: パースエラー - {e}")
                return fy_end_8, None

        _t0 = time.perf_counter()
        raw = await asyncio.gather(*[_dl_parse(doc) for doc in docs], return_exceptions=True)
        out: _PreParsedMap = {}
        for res in raw:
            if isinstance(res, BaseException):
                continue
            k, v = res
            if k and v is not None:
                out[k] = v
        logger.info(f"[PARSE] {code}: XBRL一括パース完了 {len(out)}件 {time.perf_counter() - _t0:.2f}s")
        return out

    async def _run_extraction(
        self,
        doc: dict[str, Any],
        code: str,
        prefix: str,
        extract_fn: Callable,
        *,
        result_check: Callable[[dict[str, Any]], bool] | None = None,
        pre_parsed_map: _PreParsedMap | None = None,
    ) -> tuple[str, dict[str, Any] | None]:
        fy_end_8 = _fy_end_key(doc.get("jquants_fy_end"))
        if not fy_end_8:
            return "", None
        if self.edinet_client is None:
            return fy_end_8, None
        client = self.edinet_client
        try:
            if pre_parsed_map is not None and fy_end_8 in pre_parsed_map:
                xbrl_path, pre_parsed = pre_parsed_map[fy_end_8]
                result = extract_fn(xbrl_path, pre_parsed=pre_parsed)
            else:
                xbrl_dir = await asyncio.wait_for(
                    client.download_document(doc["docID"], 1),
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

    def _collect_results(
        self,
        results: list[tuple[str, dict[str, Any] | None] | BaseException],
        code: str,
        prefix: str,
    ) -> _MetricByYear:
        out: _MetricByYear = {}
        for res in results:
            if isinstance(res, BaseException):
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
            code, jquants_annual_data or [], max_documents
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
        client = self.edinet_client
        docs = await self._get_annual_docs(code, financial_data, max_years)
        result: dict[str, str] = {}
        for doc in docs:
            fy_end = _fy_end_key(doc.get("jquants_fy_end"))
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
        pre_parsed_map: _PreParsedMap | None = None,
    ) -> _MetricByYear:
        if not self.edinet_client or not self.edinet_client.api_key:
            return {}
        docs = await self._get_annual_docs(code, financial_data, max_years)
        logger.info(f"[{spec.label}] {code}: {len(docs)}件のEDINET文書を検索")
        _t0 = time.perf_counter()
        results = await asyncio.gather(
            *[
                self._run_extraction(
                    doc,
                    code,
                    spec.label,
                    spec.extract_fn,
                    result_check=spec.result_check,
                    pre_parsed_map=pre_parsed_map,
                )
                for doc in docs
            ],
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
        pre_parsed_map: _PreParsedMap | None = None,
    ) -> _AllMetrics:
        """全メトリクスを並列抽出。Returns: {"ibd": {...}, "gp": {...}, ..., "doc_ids": {...}}"""
        metric_results = await asyncio.gather(*[
            self._extract_metric_by_year(spec, code, financial_data, max_years, pre_parsed_map=pre_parsed_map)
            for spec in _EXTRACTOR_SPECS
        ])
        doc_ids = await self.get_doc_ids_by_year(code, financial_data, max_years)
        out: _AllMetrics = {
            spec.key: result
            for spec, result in zip(_EXTRACTOR_SPECS, metric_results)
        }
        out["doc_ids"] = doc_ids
        return out

    async def extract_ibd_by_year(
        self,
        code: str,
        financial_data: list[dict[str, Any]],
        max_years: int,
        *,
        pre_parsed_map: _PreParsedMap | None = None,
    ) -> _MetricByYear:
        """年度別に有利子負債を抽出。Returns: { "YYYYMMDD": ibd_result_dict }"""
        return await self._extract_metric_by_year(_SPEC_BY_KEY["ibd"], code, financial_data, max_years, pre_parsed_map=pre_parsed_map)

    async def extract_half_year_edinet_data(
        self,
        code: str,
        financial_data: list[dict[str, Any]],
        max_years: int,
    ) -> dict[str, HalfYearEdinetEntry]:
        """2Q期間のEDINETデータ（GrossProfit + CF + IBD）を年度別に抽出。

        Returns: { "YYYYMMDD": {"gp": gp_result_dict, "cf": cf_result_dict, "ibd": ibd_result_dict} }
        """
        from mebuki.analysis.gross_profit import extract_gross_profit
        from mebuki.analysis.cash_flow import extract_cash_flow
        from mebuki.analysis.interest_bearing_debt import extract_interest_bearing_debt

        if not self.edinet_client or not self.edinet_client.api_key:
            return {}
        docs = await self._get_half_year_docs(code, financial_data, max_years)
        if not docs:
            return {}
        logger.info(f"[HALF-EDINET] {code}: {len(docs)}件の2Q文書を検索")

        pre_parsed_map = await self._download_and_parse_docs(docs, code)

        out: dict[str, HalfYearEdinetEntry] = {}
        for doc in docs:
            fy_end_8 = _fy_end_key(doc.get("jquants_fy_end"))
            if not fy_end_8 or fy_end_8 not in pre_parsed_map:
                continue
            xbrl_path, pre_parsed = pre_parsed_map[fy_end_8]
            gp: GrossProfitResult = extract_gross_profit(xbrl_path, pre_parsed=pre_parsed)
            cf = extract_cash_flow(xbrl_path, pre_parsed=pre_parsed)
            ibd = extract_interest_bearing_debt(xbrl_path, pre_parsed=pre_parsed)
            gp["docID"] = doc["docID"]
            logger.info(
                f"[HALF-EDINET] {code} {fy_end_8}: "
                f"gp={gp.get('current')}, cfo={cf['cfo'].get('current')}, "
                f"cfi={cf['cfi'].get('current')}, ibd={ibd.get('current')}, docID={doc['docID']}"
            )
            out[fy_end_8] = {"gp": gp, "cf": cf, "ibd": ibd}

        logger.info(f"[HALF-EDINET] {code}: 半期EDINETデータ抽出完了 {len(out)}件")
        return out

    async def extract_employees_by_year(
        self,
        code: str,
        financial_data: list[dict[str, Any]],
        max_years: int,
        *,
        pre_parsed_map: _PreParsedMap | None = None,
    ) -> _MetricByYear:
        """年度別に従業員数を抽出。Returns: { "YYYYMMDD": employees_result_dict }"""
        return await self._extract_metric_by_year(_SPEC_BY_KEY["emp"], code, financial_data, max_years, pre_parsed_map=pre_parsed_map)

    async def extract_net_revenue_by_year(
        self,
        code: str,
        financial_data: list[dict[str, Any]],
        max_years: int,
        *,
        pre_parsed_map: _PreParsedMap | None = None,
    ) -> _MetricByYear:
        """年度別に IFRS 純収益・事業利益を抽出。Returns: { "YYYYMMDD": nr_result_dict }"""
        return await self._extract_metric_by_year(_SPEC_BY_KEY["nr"], code, financial_data, max_years, pre_parsed_map=pre_parsed_map)

    async def extract_gross_profit_by_year(
        self,
        code: str,
        financial_data: list[dict[str, Any]],
        max_years: int,
        *,
        pre_parsed_map: _PreParsedMap | None = None,
    ) -> _MetricByYear:
        """年度別に売上総利益を抽出。Returns: { "YYYYMMDD": gp_result_dict }"""
        return await self._extract_metric_by_year(_SPEC_BY_KEY["gp"], code, financial_data, max_years, pre_parsed_map=pre_parsed_map)

    async def extract_tax_expense_by_year(
        self,
        code: str,
        financial_data: list[dict[str, Any]],
        max_years: int,
        *,
        pre_parsed_map: _PreParsedMap | None = None,
    ) -> _MetricByYear:
        """年度別に税引前利益・法人税等を抽出。Returns: { "YYYYMMDD": tax_result_dict }"""
        return await self._extract_metric_by_year(_SPEC_BY_KEY["tax"], code, financial_data, max_years, pre_parsed_map=pre_parsed_map)

    async def extract_interest_expense_by_year(
        self,
        code: str,
        financial_data: list[dict[str, Any]],
        max_years: int,
        *,
        pre_parsed_map: _PreParsedMap | None = None,
    ) -> _MetricByYear:
        """年度別に支払利息（金融費用）を抽出。Returns: { "YYYYMMDD": ie_result_dict }"""
        return await self._extract_metric_by_year(_SPEC_BY_KEY["ie"], code, financial_data, max_years, pre_parsed_map=pre_parsed_map)

    async def extract_operating_profit_by_year(
        self,
        code: str,
        financial_data: list[dict[str, Any]],
        max_years: int,
        *,
        pre_parsed_map: _PreParsedMap | None = None,
    ) -> _MetricByYear:
        """年度別に営業利益（または経常利益）を抽出。Returns: { "YYYYMMDD": op_result_dict }"""
        return await self._extract_metric_by_year(_SPEC_BY_KEY["op"], code, financial_data, max_years, pre_parsed_map=pre_parsed_map)
