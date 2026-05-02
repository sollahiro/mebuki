from unittest.mock import AsyncMock, Mock

import pytest

from mebuki.services.edinet_fetcher import EdinetFetcher


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
