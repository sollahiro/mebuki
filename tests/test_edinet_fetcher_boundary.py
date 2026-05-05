from unittest.mock import AsyncMock, Mock
from pathlib import Path

import pytest

from mebuki.services.edinet_fetcher import EdinetFetcher
from mebuki.utils.cache import CacheManager


def _financial_record(
    fiscal_year_start: str,
    fiscal_year_end: str,
    disclosed_date: str,
    period_type: str = "FY",
) -> dict:
    return {
        "CurFYSt": fiscal_year_start,
        "CurFYEn": fiscal_year_end,
        "DiscDate": disclosed_date,
        "CurPerType": period_type,
    }


@pytest.mark.asyncio
async def test_search_recent_reports_prepares_jquants_data_in_service_layer() -> None:
    edinet_client = Mock()
    edinet_client.api_key = "dummy"
    edinet_client.search_documents = AsyncMock(return_value=[{"docID": "S100TEST"}])
    fetcher = EdinetFetcher(api_client=Mock(), edinet_client=edinet_client)

    docs = await fetcher.search_recent_reports(
        code="72030",
        jquants_data=[
            _financial_record("2023-04-01", "2024-03-31", "2024-06-01"),
            _financial_record("2022-04-01", "2023-03-31", "2023-06-01"),
        ],
        max_years=1,
        doc_types=["120"],
        max_documents=5,
    )

    assert docs == [{"docID": "S100TEST"}]
    edinet_client.search_documents.assert_awaited_once()
    _, kwargs = edinet_client.search_documents.await_args
    assert kwargs["code"] == "72030"
    assert kwargs["years"] == [2023]
    assert kwargs["doc_type_code"] == "120"
    assert kwargs["max_documents"] == 5
    assert kwargs["jquants_data"] == [
        {
            "CurFYEn": "2024-03-31",
            "CurPerEn": "",
            "CurFYSt": "2023-04-01",
            "DiscDate": "2024-06-01",
            "CurPerType": "FY",
            "fiscal_year": 2023,
        }
    ]


@pytest.mark.asyncio
async def test_fetch_latest_annual_report_selects_latest_120_doc() -> None:
    edinet_client = Mock()
    edinet_client.api_key = "dummy"
    edinet_client.search_documents = AsyncMock(return_value=[
        {"docID": "OLD", "docTypeCode": "120", "submitDateTime": "2023-06-01T10:00:00"},
        {"docID": "Q2", "docTypeCode": "140", "submitDateTime": "2024-02-01T10:00:00"},
        {"docID": "NEW", "docTypeCode": "120", "submitDateTime": "2024-06-01T10:00:00"},
    ])
    fetcher = EdinetFetcher(api_client=Mock(), edinet_client=edinet_client)

    doc = await fetcher.fetch_latest_annual_report(
        "72030",
        [_financial_record("2023-04-01", "2024-03-31", "2024-06-01")],
    )

    assert doc is not None
    assert doc["docID"] == "NEW"


@pytest.mark.asyncio
async def test_get_half_year_docs_calls_search_documents_once_on_repeated_calls() -> None:
    edinet_client = Mock()
    edinet_client.api_key = "dummy"
    edinet_client.search_documents = AsyncMock(return_value=[{"docID": "S100HALF"}])
    fetcher = EdinetFetcher(api_client=Mock(), edinet_client=edinet_client)
    financial_data = [
        _financial_record("2023-04-01", "2024-03-31", "2023-11-10", period_type="2Q"),
    ]

    first = await fetcher._get_half_year_docs("72030", financial_data, 1)
    second = await fetcher._get_half_year_docs("72030", financial_data, 1)

    assert first == [{"docID": "S100HALF"}]
    assert second == [{"docID": "S100HALF"}]
    edinet_client.search_documents.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_annual_docs_reads_from_persistent_cache(tmp_path) -> None:
    code = "72030"
    max_years = 1
    cache_manager = CacheManager(cache_dir=str(tmp_path))
    cache_manager.set(
        f"edinet_docs_{code}_{max_years}",
        {
            "_cache_version": "edinet-docs-v2",
            "docs": [{"docID": "S100CACHED"}],
        },
    )
    edinet_client = Mock()
    edinet_client.api_key = "dummy"
    edinet_client.search_documents = AsyncMock(return_value=[{"docID": "UNUSED"}])
    fetcher = EdinetFetcher(api_client=Mock(), edinet_client=edinet_client, cache_manager=cache_manager)

    docs = await fetcher._get_annual_docs(
        code,
        [_financial_record("2023-04-01", "2024-03-31", "2024-06-01")],
        max_years,
    )

    assert docs == [{"docID": "S100CACHED"}]
    edinet_client.search_documents.assert_not_awaited()


@pytest.mark.asyncio
async def test_get_annual_docs_saves_to_persistent_cache_after_api_call(tmp_path) -> None:
    code = "72030"
    cache_manager = CacheManager(cache_dir=str(tmp_path))
    edinet_client = Mock()
    edinet_client.api_key = "dummy"
    edinet_client.search_documents = AsyncMock(return_value=[{"docID": "S100TEST"}])
    fetcher = EdinetFetcher(api_client=Mock(), edinet_client=edinet_client, cache_manager=cache_manager)

    docs = await fetcher._get_annual_docs(
        code,
        [_financial_record("2023-04-01", "2024-03-31", "2024-06-01")],
        1,
    )
    cached = cache_manager.get("edinet_docs_72030_1")

    assert docs == [{"docID": "S100TEST"}]
    assert isinstance(cached, dict)
    assert cached["docs"] == [{"docID": "S100TEST"}]


@pytest.mark.asyncio
async def test_get_annual_docs_ignores_q2_records_for_year_selection() -> None:
    edinet_client = Mock()
    edinet_client.api_key = "dummy"
    edinet_client.search_documents = AsyncMock(return_value=[{"docID": "S100ANNUAL"}])
    fetcher = EdinetFetcher(api_client=Mock(), edinet_client=edinet_client)

    docs = await fetcher._get_annual_docs(
        "59320",
        [
            _financial_record("2025-06-01", "2026-05-31", "2026-01-08", period_type="2Q"),
            _financial_record("2024-06-01", "2025-05-31", "2025-07-10"),
            _financial_record("2023-06-01", "2024-05-31", "2024-07-11"),
            _financial_record("2022-06-01", "2023-05-31", "2023-07-12"),
            _financial_record("2021-06-01", "2022-05-31", "2022-07-12"),
            _financial_record("2020-06-01", "2021-05-31", "2021-07-13"),
        ],
        5,
    )

    assert docs == [{"docID": "S100ANNUAL"}]
    _, kwargs = edinet_client.search_documents.await_args
    assert kwargs["years"] == [2024, 2023, 2022, 2021, 2020]
    assert [record["CurPerType"] for record in kwargs["jquants_data"]] == ["FY"] * 5


@pytest.mark.asyncio
async def test_get_half_year_docs_reads_from_persistent_cache(tmp_path) -> None:
    code = "72030"
    max_years = 1
    cache_manager = CacheManager(cache_dir=str(tmp_path))
    cache_manager.set(
        f"edinet_docs_{code}_{max_years}_2Q",
        {
            "_cache_version": "edinet-docs-v2",
            "docs": [{"docID": "S100HALFCACHED"}],
        },
    )
    edinet_client = Mock()
    edinet_client.api_key = "dummy"
    edinet_client.search_documents = AsyncMock(return_value=[{"docID": "UNUSED"}])
    fetcher = EdinetFetcher(api_client=Mock(), edinet_client=edinet_client, cache_manager=cache_manager)
    financial_data = [
        _financial_record("2023-04-01", "2024-03-31", "2023-11-10", period_type="2Q"),
    ]

    docs = await fetcher._get_half_year_docs(code, financial_data, max_years)

    assert docs == [{"docID": "S100HALFCACHED"}]
    edinet_client.search_documents.assert_not_awaited()


@pytest.mark.asyncio
async def test_get_half_year_docs_returns_empty_when_no_q2_records() -> None:
    edinet_client = Mock()
    edinet_client.api_key = "dummy"
    edinet_client.search_documents = AsyncMock(return_value=[{"docID": "UNUSED"}])
    fetcher = EdinetFetcher(api_client=Mock(), edinet_client=edinet_client)

    docs = await fetcher._get_half_year_docs(
        "72030",
        [
            _financial_record("2023-04-01", "2024-03-31", "2024-06-01", period_type="FY"),
            _financial_record("2022-04-01", "2023-03-31", "2023-06-01", period_type="3Q"),
        ],
        2,
    )

    assert docs == []
    edinet_client.search_documents.assert_not_awaited()


@pytest.mark.asyncio
async def test_build_xbrl_annual_records_falls_back_to_ordinary_revenue_for_sales(monkeypatch) -> None:
    edinet_client = Mock()
    edinet_client.api_key = "dummy"
    fetcher = EdinetFetcher(api_client=Mock(), edinet_client=edinet_client)
    fetcher._download_and_parse_docs = AsyncMock(return_value={"20250331": (Path("."), {})})  # type: ignore[method-assign]

    monkeypatch.setattr(
        "mebuki.services.edinet_fetcher.extract_income_statement",
        lambda *args, **kwargs: {
            "sales": None,
            "operating_profit": 367_694_000_000,
            "net_profit": 257_635_000_000,
            "accounting_standard": "J-GAAP",
        },
    )
    monkeypatch.setattr(
        "mebuki.services.edinet_fetcher.extract_gross_profit",
        lambda *args, **kwargs: {"current_sales": 2_922_428_000_000},
    )
    monkeypatch.setattr(
        "mebuki.services.edinet_fetcher.extract_balance_sheet",
        lambda *args, **kwargs: {"net_assets": 3_127_317_000_000},
    )
    monkeypatch.setattr(
        "mebuki.services.edinet_fetcher.extract_cash_flow",
        lambda *args, **kwargs: {
            "cfo": {"current": 3_976_669_000_000},
            "cfi": {"current": -1_763_839_000_000},
        },
    )

    records = await fetcher.build_xbrl_annual_records(
        "83090",
        1,
        docs=[
            {
                "docID": "S100VXKF",
                "jquants_fy_end": "2025-03-31",
                "submitDateTime": "2025-06-25T10:00:00",
            }
        ],
    )

    assert records[0]["Sales"] == 2_922_428_000_000
    assert records[0]["SalesLabel"] == "経常収益"
    assert records[0]["OP"] == 367_694_000_000


@pytest.mark.asyncio
async def test_build_xbrl_annual_records_uses_operating_profit_fallback(monkeypatch) -> None:
    edinet_client = Mock()
    edinet_client.api_key = "dummy"
    fetcher = EdinetFetcher(api_client=Mock(), edinet_client=edinet_client)
    fetcher._download_and_parse_docs = AsyncMock(return_value={"20250331": (Path("."), {})})  # type: ignore[method-assign]

    monkeypatch.setattr(
        "mebuki.services.edinet_fetcher.extract_income_statement",
        lambda *args, **kwargs: {
            "sales": 3_195_828_000_000,
            "operating_profit": None,
            "net_profit": 260_951_000_000,
            "accounting_standard": "US-GAAP",
        },
    )
    monkeypatch.setattr(
        "mebuki.services.edinet_fetcher.extract_operating_profit",
        lambda *args, **kwargs: {"current": 340_594_000_000},
    )
    monkeypatch.setattr(
        "mebuki.services.edinet_fetcher.extract_balance_sheet",
        lambda *args, **kwargs: {"net_assets": 3_348_480_000_000},
    )
    monkeypatch.setattr(
        "mebuki.services.edinet_fetcher.extract_cash_flow",
        lambda *args, **kwargs: {
            "cfo": {"current": 428_162_000_000},
            "cfi": {"current": -541_953_000_000},
        },
    )

    records = await fetcher.build_xbrl_annual_records(
        "49010",
        1,
        docs=[
            {
                "docID": "S100W3XJ",
                "jquants_fy_end": "2025-03-31",
                "submitDateTime": "2025-06-27T10:00:00",
            }
        ],
    )

    assert records[0]["OP"] == 340_594_000_000


@pytest.mark.asyncio
async def test_build_xbrl_annual_records_defers_ordinary_income_to_edinet_applier(monkeypatch) -> None:
    edinet_client = Mock()
    edinet_client.api_key = "dummy"
    fetcher = EdinetFetcher(api_client=Mock(), edinet_client=edinet_client)
    fetcher._download_and_parse_docs = AsyncMock(return_value={"20250331": (Path("."), {})})  # type: ignore[method-assign]

    monkeypatch.setattr(
        "mebuki.services.edinet_fetcher.extract_income_statement",
        lambda *args, **kwargs: {
            "sales": 13_629_997_000_000,
            "operating_profit": None,
            "net_profit": 1_862_946_000_000,
            "accounting_standard": "J-GAAP",
        },
    )
    monkeypatch.setattr(
        "mebuki.services.edinet_fetcher.extract_operating_profit",
        lambda *args, **kwargs: {"current": 2_669_483_000_000, "label": "経常利益"},
    )
    monkeypatch.setattr(
        "mebuki.services.edinet_fetcher.extract_balance_sheet",
        lambda *args, **kwargs: {"net_assets": 21_728_132_000_000},
    )
    monkeypatch.setattr(
        "mebuki.services.edinet_fetcher.extract_cash_flow",
        lambda *args, **kwargs: {
            "cfo": {"current": 6_415_000_000},
            "cfi": {"current": -186_948_000_000},
        },
    )

    records = await fetcher.build_xbrl_annual_records(
        "83060",
        1,
        docs=[
            {
                "docID": "S100W4FB",
                "jquants_fy_end": "2025-03-31",
                "submitDateTime": "2025-06-25T10:00:00",
            }
        ],
    )

    assert records[0]["OP"] is None


def test_prepare_q2_records_deduplicates_by_fy_end_keeping_latest_disc_date() -> None:
    fetcher = EdinetFetcher(api_client=Mock(), edinet_client=Mock())

    records = fetcher._prepare_q2_records(
        [
            _financial_record("2023-04-01", "2024-03-31", "2023-11-05", period_type="2Q"),
            _financial_record("2023-04-01", "2024-03-31", "2023-11-10", period_type="2Q"),
            _financial_record("2022-04-01", "2023-03-31", "2022-11-10", period_type="2Q"),
        ],
        3,
    )

    assert len(records) == 2
    assert records[0]["CurFYEn"] == "2024-03-31"
    assert records[0]["DiscDate"] == "2023-11-10"
