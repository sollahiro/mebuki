"""
データサービス
純粋なデータ取得・計算ロジック（LLM非依存）
"""

import asyncio
import logging
from datetime import datetime, timedelta, date
from pathlib import Path
from typing import Dict, Any, List, Optional

from mebuki.api.jquants_client import JQuantsAPIClient
from mebuki.api.edinet_client import EdinetAPIClient
from mebuki.analysis.xbrl_parser import XBRLParser
from mebuki.infrastructure.settings import settings_store
from mebuki.utils.cache import CacheManager
from mebuki.utils.fiscal_year import parse_date_string

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
            raw = await asyncio.to_thread(self.api_client.get_earnings_calendar)
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

    def reinitialize(self) -> None:
        """設定変更時に呼び出され、APIクライアントなどの設定を更新します。"""
        logger.info("再初期化中: APIクライアントの設定を更新します")
        self.api_client.update_api_key(settings_store.jquants_api_key)
        self.edinet_client.update_api_key(settings_store.edinet_api_key)

        self.cache_manager.cache_dir = Path(settings_store.cache_dir)
        self.cache_manager.enabled = settings_store.cache_enabled
        self.cache_manager.cache_dir.mkdir(parents=True, exist_ok=True)

    def get_analyzer(self, use_cache: bool = True) -> IndividualAnalyzer:
        """IndividualAnalyzerのインスタンスを取得"""
        return IndividualAnalyzer(
            api_client=self.api_client,
            edinet_client=self.edinet_client,
            cache=self.cache_manager,
            use_cache=use_cache,
        )

    async def search_companies(self, query: str) -> List[Dict[str, Any]]:
        """銘柄コードまたは名称で企業を検索します。"""
        return master_data_manager.search(query, limit=50)

    def fetch_stock_basic_info(self, code: str) -> Dict[str, Any]:
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
        scope: str = "overview",
        use_cache: bool = True,
        include_2q: bool = False,
    ) -> Any:
        """財務データ取得の統一公開API。"""
        analyzer = self.get_analyzer(use_cache=use_cache)

        if scope == "overview":
            result = await self.get_raw_analysis_data(code, use_cache=use_cache, include_2q=include_2q)
            try:
                await self._refresh_earnings_calendar_if_needed()
                self._attach_upcoming_earnings(result, code)
            except Exception:
                pass
            return result

        if scope == "metrics":
            metrics = await analyzer.get_metrics(code, include_2q=include_2q)
            result = metrics or {}
            try:
                await self._refresh_earnings_calendar_if_needed()
                self._attach_upcoming_earnings(result, code)
            except Exception:
                pass
            return result

        if scope == "raw":
            raw_data = await asyncio.to_thread(self.api_client.get_financial_summary, code=code)
            cleaned_data = [
                {k: v for k, v in record.items() if v is not None and v != ""}
                for record in raw_data
            ]
            return cleaned_data

        raise ValueError(f"Invalid scope: {scope}")

    async def get_price_data(self, code: str, days: int = 365) -> List[Dict[str, Any]]:
        """株価履歴データを取得"""
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        return await asyncio.to_thread(
            self.api_client.get_daily_bars,
            code=code,
            from_date=start_date.strftime("%Y-%m-%d"),
            to_date=end_date.strftime("%Y-%m-%d"),
        )

    async def search_filings(
        self,
        code: str,
        max_years: int = 10,
        doc_types: Optional[List[str]] = None,
        max_documents: int = 10,
    ) -> List[Dict[str, Any]]:
        """EDINET書類を検索"""
        fin_data = await asyncio.to_thread(self.api_client.get_financial_summary, code=code)
        return await asyncio.to_thread(
            self.edinet_client.search_recent_reports,
            code=code,
            jquants_data=fin_data,
            max_years=max_years,
            doc_types=doc_types,
            max_documents=max_documents,
        )

    async def extract_filing_content(
        self,
        code: str,
        doc_id: Optional[str] = None,
        sections: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """EDINET書類からセクションを抽出"""
        requested_sections = sections or ["all"]

        meta: Dict[str, Any] = {}
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

        xbrl_dir = await asyncio.to_thread(self.edinet_client.download_document, doc_id, 1)
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

    async def visualize_financial_data(self, code: str) -> Dict[str, Any]:
        """可視化向けの財務データを返す。"""
        analyzer = self.get_analyzer(use_cache=True)
        return await analyzer.analyze_stock(code) or {}

    async def get_raw_analysis_data(
        self,
        code: str,
        use_cache: bool = True,
        max_documents: int = 2,
        analysis_years: Optional[int] = None,
        include_2q: bool = False,
    ) -> Dict[str, Any]:
        """AI分析抜きの純粋な分析データを取得（財務指標 + 有報テキスト）"""
        analyzer = self.get_analyzer(use_cache=use_cache)

        if use_cache:
            cached = self.cache_manager.get(f"individual_analysis_{code}")
            if cached:
                if "llm_financial_analysis" in cached:
                    del cached["llm_financial_analysis"]
                return cached

        result = await analyzer.fetch_analysis_data(code, analysis_years, max_documents, include_2q=include_2q)
        if not result:
            return {}

        formatted = {
            "code": code,
            **self.fetch_stock_basic_info(code),
            "metrics": result["metrics"],
            "edinet_data": result["edinet_data"],
            "analyzed_at": datetime.now().isoformat(),
        }
        if use_cache:
            self.cache_manager.set(f"individual_analysis_{code}", formatted)
        return formatted


# シングルトンインスタンス
data_service = DataService()
