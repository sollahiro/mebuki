"""
DataService のユニットテスト

JQuantsAPIClient / EdinetAPIClient / IndividualAnalyzer をモック化し、
キャッシュロジック・データ変換・カレンダー付与などのビジネスロジックを検証する。
"""
import pytest
from datetime import date, datetime
from unittest.mock import AsyncMock, MagicMock, patch
from typing import Any


# ──────────────────────────────────────────────────────────────
# フィクスチャ
# ──────────────────────────────────────────────────────────────

@pytest.fixture
def svc(tmp_path):
    """
    DataService を外部依存ゼロで構築する。
    - settings_store は tmp_path を向くスタブ
    - JQuantsAPIClient / EdinetAPIClient は AsyncMock
    - CacheManager は tmp_path に実ファイルを作成（TTL ロジックも動作確認できる）
    """
    with (
        patch("mebuki.services.data_service.settings_store") as mock_settings,
        patch("mebuki.services.data_service.JQuantsAPIClient"),
        patch("mebuki.services.data_service.EdinetAPIClient"),
    ):
        mock_settings.jquants_api_key = ""
        mock_settings.edinet_api_key = ""
        mock_settings.cache_dir = str(tmp_path)
        mock_settings.cache_enabled = True

        from mebuki.services.data_service import DataService
        ds = DataService()
        ds.api_client = AsyncMock()
        ds.edinet_client = AsyncMock()
        yield ds


# ──────────────────────────────────────────────────────────────
# search_companies
# ──────────────────────────────────────────────────────────────

class TestSearchCompanies:
    @pytest.mark.asyncio
    async def test_delegates_to_master_data(self, svc):
        expected = [{"code": "72030", "name": "トヨタ自動車"}]
        with patch("mebuki.services.company_info_service.master_data_manager") as mm:
            mm.search.return_value = expected
            result = await svc.search_companies("トヨタ")
        mm.search.assert_called_once_with("トヨタ", limit=50)
        assert result == expected

    @pytest.mark.asyncio
    async def test_empty_query_returns_results(self, svc):
        with patch("mebuki.services.company_info_service.master_data_manager") as mm:
            mm.search.return_value = []
            result = await svc.search_companies("")
        assert result == []


# ──────────────────────────────────────────────────────────────
# fetch_stock_basic_info
# ──────────────────────────────────────────────────────────────

class TestFetchStockBasicInfo:
    def test_found_returns_mapped_fields(self, svc):
        stock = {
            "CoName": "トヨタ自動車",
            "CoNameEn": "Toyota Motor",
            "S33Nm": "輸送用機器",
            "S33": "33",
            "S17": "17",
            "S17Nm": "自動車・輸送機",
            "MktNm": "プライム",
        }
        with patch("mebuki.services.company_info_service.master_data_manager") as mm:
            mm.get_by_code.return_value = stock
            info = svc.fetch_stock_basic_info("72030")
        assert info["name"] == "トヨタ自動車"
        assert info["industry"] == "輸送用機器"
        assert info["code"] == "72030"

    def test_not_found_returns_empty_defaults(self, svc):
        with patch("mebuki.services.company_info_service.master_data_manager") as mm:
            mm.get_by_code.return_value = None
            info = svc.fetch_stock_basic_info("99990")
        assert info["name"] == ""
        assert info["industry"] == ""
        assert info["code"] == "99990"


# ──────────────────────────────────────────────────────────────
# _attach_upcoming_earnings
# ──────────────────────────────────────────────────────────────

class TestAttachUpcomingEarnings:
    def _make_entry(self, code: str, date_str: str, fq: str = "本決算") -> dict:
        return {"Code": code, "Date": date_str, "FQ": fq, "SectorNm": "製造業", "Section": "プライム"}

    def test_attaches_matching_future_entry(self, svc):
        future = (date.today().replace(year=date.today().year + 1)).isoformat()
        entry = self._make_entry("72030", future)
        svc.cache_manager.set("earnings_calendar_store", [entry])

        result: dict[str, Any] = {}
        svc._attach_upcoming_earnings(result, "72030")
        assert "upcoming_earnings" in result
        assert result["upcoming_earnings"]["FQ"] == "本決算"

    def test_ignores_past_entry(self, svc):
        past = "2020-01-01"
        entry = self._make_entry("72030", past)
        svc.cache_manager.set("earnings_calendar_store", [entry])

        result: dict[str, Any] = {}
        svc._attach_upcoming_earnings(result, "72030")
        assert "upcoming_earnings" not in result

    def test_no_match_for_different_ticker(self, svc):
        future = (date.today().replace(year=date.today().year + 1)).isoformat()
        entry = self._make_entry("60980", future)
        svc.cache_manager.set("earnings_calendar_store", [entry])

        result: dict[str, Any] = {}
        svc._attach_upcoming_earnings(result, "72030")
        assert "upcoming_earnings" not in result

    def test_empty_store_is_noop(self, svc):
        svc.cache_manager.set("earnings_calendar_store", [])
        result: dict[str, Any] = {}
        svc._attach_upcoming_earnings(result, "72030")
        assert "upcoming_earnings" not in result


# ──────────────────────────────────────────────────────────────
# _refresh_earnings_calendar_if_needed
# ──────────────────────────────────────────────────────────────

class TestRefreshEarningsCalendar:
    @pytest.mark.asyncio
    async def test_skips_if_already_fetched_today(self, svc):
        today = date.today().isoformat()
        svc.cache_manager.set("earnings_calendar_last_fetched", today)
        await svc._refresh_earnings_calendar_if_needed()
        svc.api_client.get_earnings_calendar.assert_not_called()

    @pytest.mark.asyncio
    async def test_fetches_and_stores_on_first_call(self, svc):
        future = (date.today().replace(year=date.today().year + 1)).isoformat()
        svc.api_client.get_earnings_calendar.return_value = [
            {"Date": future, "Code": "72030", "FQ": "本決算", "SectorNm": "製造業", "Section": "プライム"},
        ]
        await svc._refresh_earnings_calendar_if_needed()
        svc.api_client.get_earnings_calendar.assert_called_once()
        stored = svc.cache_manager.get("earnings_calendar_store")
        assert any(e["Code"] == "72030" for e in stored)

    @pytest.mark.asyncio
    async def test_filters_past_dates(self, svc):
        svc.api_client.get_earnings_calendar.return_value = [
            {"Date": "2020-01-01", "Code": "72030", "FQ": "本決算"},
        ]
        await svc._refresh_earnings_calendar_if_needed()
        stored = svc.cache_manager.get("earnings_calendar_store") or []
        assert stored == []

    @pytest.mark.asyncio
    async def test_filters_non_target_fq(self, svc):
        future = (date.today().replace(year=date.today().year + 1)).isoformat()
        svc.api_client.get_earnings_calendar.return_value = [
            {"Date": future, "Code": "72030", "FQ": "第１四半期"},
        ]
        await svc._refresh_earnings_calendar_if_needed()
        stored = svc.cache_manager.get("earnings_calendar_store") or []
        assert stored == []

    @pytest.mark.asyncio
    async def test_no_duplicates_on_second_refresh(self, svc):
        future = (date.today().replace(year=date.today().year + 1)).isoformat()
        entry = {"Date": future, "Code": "72030", "FQ": "本決算"}
        svc.api_client.get_earnings_calendar.return_value = [entry]
        await svc._refresh_earnings_calendar_if_needed()
        # last_fetched をリセットして2回目を実行
        svc.cache_manager.set("earnings_calendar_last_fetched", "2000-01-01")
        await svc._refresh_earnings_calendar_if_needed()
        stored = svc.cache_manager.get("earnings_calendar_store") or []
        codes = [e["Code"] for e in stored]
        assert codes.count("72030") == 1

    @pytest.mark.asyncio
    async def test_api_error_does_not_raise(self, svc):
        svc.api_client.get_earnings_calendar.side_effect = RuntimeError("network error")
        await svc._refresh_earnings_calendar_if_needed()  # 例外を外に出さない


# ──────────────────────────────────────────────────────────────
# get_financial_data (scope="raw")
# ──────────────────────────────────────────────────────────────

class TestGetFinancialDataRaw:
    @pytest.mark.asyncio
    async def test_raw_scope_returns_cleaned_records(self, svc):
        svc.api_client.get_financial_summary.return_value = [
            {"LocalCode": "72030", "NP": 1000000.0, "EmptyField": "", "NullField": None},
        ]
        result = await svc.get_financial_data("72030", scope="raw")
        assert isinstance(result, list)
        assert result[0]["LocalCode"] == "72030"
        assert "EmptyField" not in result[0]
        assert "NullField" not in result[0]

    @pytest.mark.asyncio
    async def test_raw_scope_bypasses_cache(self, svc):
        svc.api_client.get_financial_summary.return_value = []
        await svc.get_financial_data("72030", scope="raw")
        await svc.get_financial_data("72030", scope="raw")
        assert svc.api_client.get_financial_summary.call_count == 2


# ──────────────────────────────────────────────────────────────
# get_raw_analysis_data (キャッシュ ヒット / ミス)
# ──────────────────────────────────────────────────────────────

class TestGetRawAnalysisData:
    def _make_cached(self, code: str) -> dict:
        from mebuki import __version__
        cache_version = f"{'.'.join(__version__.split('.')[:2])}:metrics-v2"
        return {
            "_cache_version": cache_version,
            "code": code,
            "name": "トヨタ自動車",
            "metrics": {"years": []},
            "edinet_data": {},
            "analyzed_at": "2024-01-01T00:00:00",
        }

    @pytest.mark.asyncio
    async def test_cache_hit_skips_fetch(self, svc):
        cached = self._make_cached("72030")
        svc.cache_manager.set("individual_analysis_72030", cached)

        mock_analyzer = AsyncMock()
        with patch.object(svc, "get_analyzer", return_value=mock_analyzer):
            result = await svc.get_raw_analysis_data("72030", use_cache=True)

        mock_analyzer.fetch_analysis_data.assert_not_called()
        assert result["code"] == "72030"
        assert "_cache_version" not in result

    @pytest.mark.asyncio
    async def test_cache_miss_calls_analyzer(self, svc):
        mock_analyzer = AsyncMock()
        mock_analyzer.fetch_analysis_data.return_value = {
            "metrics": {"years": []},
            "edinet_data": {},
        }
        with (
            patch.object(svc, "get_analyzer", return_value=mock_analyzer),
            patch.object(svc, "fetch_stock_basic_info", return_value={"name": "トヨタ"}),
        ):
            result = await svc.get_raw_analysis_data("72030", use_cache=False)

        mock_analyzer.fetch_analysis_data.assert_called_once()
        assert result["code"] == "72030"

    @pytest.mark.asyncio
    async def test_cache_version_mismatch_calls_analyzer(self, svc):
        stale = self._make_cached("72030")
        stale["_cache_version"] = "0.0"
        svc.cache_manager.set("individual_analysis_72030", stale)

        mock_analyzer = AsyncMock()
        mock_analyzer.fetch_analysis_data.return_value = {
            "metrics": {"years": []},
            "edinet_data": {},
        }
        with (
            patch.object(svc, "get_analyzer", return_value=mock_analyzer),
            patch.object(svc, "fetch_stock_basic_info", return_value={"name": "トヨタ"}),
        ):
            await svc.get_raw_analysis_data("72030", use_cache=True)

        mock_analyzer.fetch_analysis_data.assert_called_once()

    @pytest.mark.asyncio
    async def test_analyzer_returns_empty_yields_empty(self, svc):
        mock_analyzer = AsyncMock()
        mock_analyzer.fetch_analysis_data.return_value = {}
        with patch.object(svc, "get_analyzer", return_value=mock_analyzer):
            result = await svc.get_raw_analysis_data("72030", use_cache=False)
        assert result == {}


# ──────────────────────────────────────────────────────────────
# HalfYearDataService
# ──────────────────────────────────────────────────────────────

class TestHalfYearDataService:
    def _make_service(self, tmp_path):
        from mebuki.services.half_year_data_service import HalfYearDataService
        from mebuki.utils.cache import CacheManager

        api_client = AsyncMock()
        edinet_client = AsyncMock()
        cache_manager = CacheManager(cache_dir=str(tmp_path), enabled=True)
        return HalfYearDataService(api_client, edinet_client, cache_manager)

    def _fy_record(self) -> dict:
        return {
            "CurPerType": "FY",
            "CurFYEn": "2024-03-31",
            "DiscDate": "2024-05-14",
            "Sales": 100_000_000,
            "OP": 10_000_000,
            "NP": 8_000_000,
            "CFO": 12_000_000,
            "CFI": -3_000_000,
            "Eq": 40_000_000,
        }

    def _q2_record(self) -> dict:
        return {
            "CurPerType": "2Q",
            "CurFYEn": "2024-03-31",
            "DiscDate": "2023-11-14",
            "Sales": 45_000_000,
            "OP": 4_000_000,
            "NP": 3_000_000,
            "CFO": 5_000_000,
            "CFI": -1_000_000,
            "Eq": 35_000_000,
        }

    @pytest.mark.asyncio
    async def test_cache_hit_skips_fetch(self, tmp_path):
        from mebuki import __version__
        cache_version = f"{'.'.join(__version__.split('.')[:2])}:metrics-v2"
        service = self._make_service(tmp_path)
        cached_periods = [{"label": "24H1", "half": "H1", "fy_end": "2024-03-31", "data": {"Sales": 45.0}}]
        service.cache_manager.set("half_year_periods_72030_3", {
            "_cache_version": cache_version,
            "periods": cached_periods,
        })

        result = await service.get_half_year_periods("72030", years=3, use_cache=True)

        assert result == cached_periods
        service.api_client.get_financial_summary.assert_not_called()

    @pytest.mark.asyncio
    async def test_empty_financial_data_returns_empty(self, tmp_path):
        service = self._make_service(tmp_path)
        service.api_client.get_financial_summary.return_value = []

        result = await service.get_half_year_periods("72030", years=3, use_cache=False)

        assert result == []

    @pytest.mark.asyncio
    async def test_edinet_failure_returns_base_periods(self, tmp_path):
        service = self._make_service(tmp_path)
        service.api_client.get_financial_summary.return_value = [self._fy_record(), self._q2_record()]

        with patch("mebuki.services.half_year_data_service.EdinetFetcher") as fetcher_cls:
            fetcher = fetcher_cls.return_value
            fetcher.extract_half_year_edinet_data.side_effect = RuntimeError("edinet down")
            fetcher.extract_gross_profit_by_year.return_value = {}
            fetcher.extract_ibd_by_year.return_value = {}

            result = await service.get_half_year_periods("72030", years=1, use_cache=False)

        assert [p["label"] for p in result] == ["24H1", "24H2"]
        assert result[0]["data"]["Sales"] == 45.0
        assert result[0]["data"]["CFC"] == 4.0
        assert result[0]["data"]["FreeCF"] == result[0]["data"]["CFC"]
        assert result[0]["data"]["MetricSources"]["CFC"]["method"] == "CFO + CFI"
        assert result[1]["data"]["Sales"] == 55.0
        assert result[1]["data"]["CFC"] == 5.0
        assert result[1]["data"]["FreeCF"] == result[1]["data"]["CFC"]
