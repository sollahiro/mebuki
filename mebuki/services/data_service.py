"""
データサービス
純粋なデータ取得・計算ロジック（LLM非依存）
"""

import asyncio
import logging
from datetime import datetime, date
from pathlib import Path
from typing import Any

from mebuki import __version__
from mebuki.api.jquants_client import JQuantsAPIClient
from mebuki.api.edinet_client import EdinetAPIClient
from mebuki.analysis.xbrl_parser import XBRLParser
from mebuki.infrastructure.settings import settings_store
from mebuki.utils.cache import CacheManager
from mebuki.utils.fiscal_year import parse_date_string

_CACHE_VERSION = ".".join(__version__.split(".")[:2])

from .analyzer import IndividualAnalyzer
from .master_data import master_data_manager

logger = logging.getLogger(__name__)

_EARNINGS_CALENDAR_FQ_FILTER = {"本決算", "第２四半期"}


def _parse_calendar_date(date_str: str) -> date:
    dt = parse_date_string(date_str)
    return dt.date() if dt is not None else date(2000, 1, 1)


class DataService:
    """財務データおよび有報データの取得を行うクラス"""

    def __init__(self):
        self.api_client = JQuantsAPIClient(api_key=settings_store.jquants_api_key)
        edinet_cache = Path(settings_store.cache_dir) / "edinet"
        self.edinet_client = EdinetAPIClient(
            api_key=settings_store.edinet_api_key,
            cache_dir=str(edinet_cache),
        )
        self.cache_manager = CacheManager(
            cache_dir=settings_store.cache_dir,
            enabled=settings_store.cache_enabled,
        )

    async def _refresh_earnings_calendar_if_needed(self) -> None:
        """1日1回、決算カレンダーのストアを更新する"""
        today = date.today()
        today_str = today.isoformat()
        if self.cache_manager.get("earnings_calendar_last_fetched") == today_str:
            return

        try:
            raw = await self.api_client.get_earnings_calendar()
            valid_new = [
                e for e in raw
                if _parse_calendar_date(e.get("Date", "")) >= today
                and e.get("FQ") in _EARNINGS_CALENDAR_FQ_FILTER
            ]

            existing = self.cache_manager.get("earnings_calendar_store") or []
            existing_valid = [
                e for e in existing
                if _parse_calendar_date(e.get("Date", "")) >= today
            ]
            existing_keys = {(e["Date"], e["Code"]) for e in existing_valid}
            for entry in valid_new:
                key = (entry.get("Date"), entry.get("Code"))
                if key not in existing_keys:
                    existing_valid.append(entry)
                    existing_keys.add(key)

            self.cache_manager.set("earnings_calendar_store", existing_valid)
            self.cache_manager.set("earnings_calendar_last_fetched", today_str)
        except Exception as e:
            logger.warning(f"決算カレンダーの更新に失敗（処理を続行）: {e}")

    async def close(self) -> None:
        """全APIクライアントのセッションをクローズする"""
        await self.api_client.close()
        await self.edinet_client.close()

    def reinitialize(self) -> None:
        """設定変更時に呼び出され、APIクライアントなどの設定を更新します。"""
        logger.info("再初期化中: APIクライアントの設定を更新します")
        self.api_client.update_api_key(settings_store.jquants_api_key)
        self.edinet_client.update_api_key(settings_store.edinet_api_key)

        self.cache_manager.cache_dir = Path(settings_store.cache_dir)
        self.cache_manager.enabled = settings_store.cache_enabled
        self.cache_manager.cache_dir.mkdir(parents=True, exist_ok=True)

    def get_analyzer(self) -> IndividualAnalyzer:
        """IndividualAnalyzerのインスタンスを取得"""
        return IndividualAnalyzer(
            api_client=self.api_client,
            edinet_client=self.edinet_client,
        )

    async def search_companies(self, query: str) -> list[dict[str, Any]]:
        """銘柄コードまたは名称で企業を検索します。"""
        return master_data_manager.search(query, limit=50)

    def fetch_stock_basic_info(self, code: str) -> dict[str, Any]:
        """銘柄の基本情報を取得"""
        stock_info = master_data_manager.get_by_code(code)
        if not stock_info:
            logger.warning(f"銘柄情報が見つかりません: {code}")
            return {
                "name": "",
                "industry": "",
                "market": "",
                "code": code,
            }

        return {
            "name": stock_info.get("CoName"),
            "name_en": stock_info.get("CoNameEn", ""),
            "industry": stock_info.get("S33Nm"),
            "sector_33": stock_info.get("S33"),
            "sector_33_name": stock_info.get("S33Nm"),
            "sector_17": stock_info.get("S17"),
            "sector_17_name": stock_info.get("S17Nm"),
            "market": stock_info.get("MktNm", ""),
            "market_name": stock_info.get("MktNm", ""),
            "code": code,
        }

    def _attach_upcoming_earnings(self, result: dict, code: str) -> None:
        """決算スケジュールを result に付与する（該当なければ何もしない）"""
        store = self.cache_manager.get("earnings_calendar_store") or []
        today = date.today()
        for entry in store:
            if (
                entry.get("Code", "").startswith(code[:4])
                and _parse_calendar_date(entry.get("Date", "")) >= today
            ):
                result["upcoming_earnings"] = {
                    "date": entry.get("Date"),
                    "FQ": entry.get("FQ"),
                    "SectorNm": entry.get("SectorNm"),
                    "Section": entry.get("Section"),
                }
                break

    async def get_financial_data(
        self,
        code: str,
        scope: str | None = None,
        use_cache: bool = True,
        include_2q: bool = False,
        analysis_years: int | None = None,
    ) -> dict[str, Any] | list[dict[str, Any]]:
        """財務データ取得の統一公開API。scope=None で財務サマリー、scope="raw" で生データ。"""
        if scope == "raw":
            raw_data = await self.api_client.get_financial_summary(code=code)
            return [
                {k: v for k, v in record.items() if v is not None and v != ""}
                for record in raw_data
            ]

        result = await self.get_raw_analysis_data(code, use_cache=use_cache, include_2q=include_2q, analysis_years=analysis_years)
        try:
            await self._refresh_earnings_calendar_if_needed()
            self._attach_upcoming_earnings(result, code)
        except Exception:
            pass
        return result

    async def get_half_year_periods(
        self,
        code: str,
        years: int = 3,
        use_cache: bool = True,
    ) -> list[dict[str, Any]]:
        """H1/H2 の半期財務データを返す。"""
        from mebuki.utils.financial_data import build_half_year_periods
        from mebuki.services.edinet_fetcher import EdinetFetcher
        from mebuki.utils.converters import to_float
        from mebuki.constants.financial import MILLION_YEN

        cache_key = f"half_year_periods_{code}_{years}"
        if use_cache:
            cached = self.cache_manager.get(cache_key)
            if cached and cached.get("_cache_version") == _CACHE_VERSION:
                return cached["periods"]

        financial_data = await self.api_client.get_financial_summary(
            code=code,
            period_types=["FY", "2Q"],
            include_fields=None,
        )
        if not financial_data:
            return []

        base_periods = build_half_year_periods(financial_data, years=years)
        if not base_periods:
            return base_periods

        # EDINET からの補完（GrossProfit + CFO/CFI for H1）
        # 表示中の FY 数だけ 2Q EDINET を取得（26H1 等の extra 分も含む）
        unique_fy_ends = len(set(p["fy_end"] for p in base_periods))
        edinet_fetcher = EdinetFetcher(self.api_client, self.edinet_client)
        try:
            half_edinet, fy_gp, ibd_by_year = await asyncio.gather(
                edinet_fetcher.extract_half_year_edinet_data(code, financial_data, max_years=unique_fy_ends),
                edinet_fetcher.extract_gross_profit_by_year(code, financial_data, max_years=years),
                edinet_fetcher.extract_ibd_by_year(code, financial_data, max_years=years),
            )
        except Exception as e:
            logger.warning(f"[HALF] {code}: EDINET補完スキップ - {e}")
            return base_periods

        # FY J-Quants レコードを fy_end → record で引けるようにしておく
        fy_by_end: dict[str, dict] = {}
        for r in financial_data:
            if r.get("CurPerType") == "FY":
                fy_end_8 = r.get("CurFYEn", "").replace("-", "")
                if fy_end_8:
                    fy_by_end[fy_end_8] = r

        # 2Q J-Quants レコードを fy_end → record で引けるようにしておく
        q2_by_end: dict[str, dict] = {}
        for r in financial_data:
            if r.get("CurPerType") == "2Q":
                fy_end_8 = r.get("CurFYEn", "").replace("-", "")
                if fy_end_8:
                    q2_by_end[fy_end_8] = r

        # H1 期間で確定した EDINET CF 値を H2 計算に引き継ぐ
        h1_edinet_by_fy: dict[str, dict] = {}

        for period in base_periods:
            fy_end_8 = period["fy_end"].replace("-", "")
            half = period["half"]
            data = period["data"]

            if half == "H1":
                edinet_q2 = half_edinet.get(fy_end_8, {})
                gp_result = edinet_q2.get("gp")
                cf_result = edinet_q2.get("cf")

                # GrossProfit（H1 = 2Q XBRL の current 値）
                h1_gp_m = None
                if gp_result and gp_result.get("current") is not None:
                    h1_gp_m = gp_result["current"] / MILLION_YEN
                    sales = data.get("Sales")
                    data["GrossProfit"] = h1_gp_m
                    data["GrossProfitMargin"] = h1_gp_m / sales * 100 if sales else None
                    data["DocID"] = gp_result.get("docID")

                # CFO/CFI（H1 = 2Q XBRL の current 値）
                h1_cfo_m = h1_cfi_m = None
                if cf_result:
                    cfo_raw = cf_result["cfo"].get("current")
                    cfi_raw = cf_result["cfi"].get("current")
                    if cfo_raw is not None:
                        h1_cfo_m = cfo_raw / MILLION_YEN
                        data["CFO"] = h1_cfo_m
                    if cfi_raw is not None:
                        h1_cfi_m = cfi_raw / MILLION_YEN
                        data["CFI"] = h1_cfi_m
                    if h1_cfo_m is not None and h1_cfi_m is not None:
                        data["FreeCF"] = h1_cfo_m + h1_cfi_m

                # ROIC (H1): NP_H1 / (Eq_2Q + IBD_2Q)
                ibd_result = edinet_q2.get("ibd")
                h1_ibd_m = ibd_result["current"] / MILLION_YEN if ibd_result and ibd_result.get("current") is not None else None
                q2_rec = q2_by_end.get(fy_end_8, {})
                h1_eq_raw = to_float(q2_rec.get("Eq"))
                h1_eq_m = h1_eq_raw / MILLION_YEN if h1_eq_raw is not None else None
                np_h1 = data.get("NP")
                if np_h1 is not None and h1_eq_m is not None and h1_ibd_m is not None and (h1_eq_m + h1_ibd_m) != 0:
                    data["ROIC"] = np_h1 / (h1_eq_m + h1_ibd_m) * 100

                h1_edinet_by_fy[fy_end_8] = {
                    "gp_m": h1_gp_m,
                    "cfo_m": h1_cfo_m,
                    "cfi_m": h1_cfi_m,
                }

            elif half == "H2":
                h1 = h1_edinet_by_fy.get(fy_end_8, {})
                fy_rec = fy_by_end.get(fy_end_8, {})

                # H2 CFO/CFI = FY（J-Quants）- H1（EDINET 2Q）
                fy_cfo = to_float(fy_rec.get("CFO"))
                fy_cfi = to_float(fy_rec.get("CFI"))
                fy_cfo_m = fy_cfo / MILLION_YEN if fy_cfo is not None else None
                fy_cfi_m = fy_cfi / MILLION_YEN if fy_cfi is not None else None

                h1_cfo_m = h1.get("cfo_m")
                h1_cfi_m = h1.get("cfi_m")

                if fy_cfo_m is not None and h1_cfo_m is not None:
                    data["CFO"] = fy_cfo_m - h1_cfo_m
                if fy_cfi_m is not None and h1_cfi_m is not None:
                    data["CFI"] = fy_cfi_m - h1_cfi_m
                cfo = data.get("CFO")
                cfi = data.get("CFI")
                if cfo is not None and cfi is not None:
                    data["FreeCF"] = cfo + cfi

                # H2 GP = FY EDINET GP - H1 EDINET 2Q GP
                fy_gp_result = fy_gp.get(fy_end_8)
                h1_gp_m = h1.get("gp_m")
                if fy_gp_result and fy_gp_result.get("current") is not None:
                    fy_gp_m = fy_gp_result["current"] / MILLION_YEN
                    if h1_gp_m is not None:
                        h2_gp_m = fy_gp_m - h1_gp_m
                        sales = data.get("Sales")
                        data["GrossProfit"] = h2_gp_m
                        data["GrossProfitMargin"] = h2_gp_m / sales * 100 if sales else None
                        data["DocID"] = fy_gp_result.get("docID")

                # ROIC (H2): NP_H2 / (Eq_FY + IBD_FY)
                h2_ibd = ibd_by_year.get(fy_end_8)
                h2_ibd_m = h2_ibd["current"] / MILLION_YEN if h2_ibd and h2_ibd.get("current") is not None else None
                h2_eq_raw = to_float(fy_rec.get("Eq"))
                h2_eq_m = h2_eq_raw / MILLION_YEN if h2_eq_raw is not None else None
                np_h2 = data.get("NP")
                if np_h2 is not None and h2_eq_m is not None and h2_ibd_m is not None and (h2_eq_m + h2_ibd_m) != 0:
                    data["ROIC"] = np_h2 / (h2_eq_m + h2_ibd_m) * 100

            else:
                # FY のみ（2Q データなし）: EDINET FY GP を付与
                fy_gp_result = fy_gp.get(fy_end_8)
                if fy_gp_result and fy_gp_result.get("current") is not None:
                    gp_m = fy_gp_result["current"] / MILLION_YEN
                    sales = data.get("Sales")
                    data["GrossProfit"] = gp_m
                    data["GrossProfitMargin"] = gp_m / sales * 100 if sales else None

                # ROIC (FY): NP_FY / (Eq_FY + IBD_FY)
                fy_rec_data = fy_by_end.get(fy_end_8, {})
                fy_ibd = ibd_by_year.get(fy_end_8)
                fy_ibd_m = fy_ibd["current"] / MILLION_YEN if fy_ibd and fy_ibd.get("current") is not None else None
                fy_eq_raw = to_float(fy_rec_data.get("Eq"))
                fy_eq_m = fy_eq_raw / MILLION_YEN if fy_eq_raw is not None else None
                np_fy = data.get("NP")
                if np_fy is not None and fy_eq_m is not None and fy_ibd_m is not None and (fy_eq_m + fy_ibd_m) != 0:
                    data["ROIC"] = np_fy / (fy_eq_m + fy_ibd_m) * 100

        self.cache_manager.set(cache_key, {
            "_cache_version": _CACHE_VERSION,
            "periods": base_periods,
        })
        return base_periods

    async def search_filings(
        self,
        code: str,
        max_years: int = 10,
        doc_types: list[str] | None = None,
        max_documents: int = 10,
    ) -> list[dict[str, Any]]:
        """EDINET書類を検索"""
        fin_data = await self.api_client.get_financial_summary(code=code)
        return await self.edinet_client.search_recent_reports(
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

    async def get_raw_analysis_data(
        self,
        code: str,
        use_cache: bool = True,
        max_documents: int = 2,
        analysis_years: int | None = None,
        include_2q: bool = False,
    ) -> dict[str, Any]:
        """AI分析抜きの純粋な分析データを取得（財務指標 + 有報テキスト）"""
        cache_key = f"individual_analysis_{code}"
        analyzer = self.get_analyzer()

        if use_cache:
            cached = self.cache_manager.get(cache_key)
            if cached and cached.get("_cache_version") == _CACHE_VERSION:
                return {k: v for k, v in cached.items() if k != "_cache_version" and k != "llm_financial_analysis"}

        result = await analyzer.fetch_analysis_data(code, analysis_years, max_documents, include_2q=include_2q)
        if not result:
            return {}

        formatted = {
            "_cache_version": _CACHE_VERSION,
            "code": code,
            **self.fetch_stock_basic_info(code),
            "metrics": result["metrics"],
            "edinet_data": result["edinet_data"],
            "analyzed_at": datetime.now().isoformat(),
        }
        self.cache_manager.set(cache_key, formatted)
        return {k: v for k, v in formatted.items() if k != "_cache_version"}


# シングルトンインスタンス
data_service = DataService()
