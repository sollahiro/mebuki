import asyncio
from unittest.mock import patch

import pytest

from mebuki.services.analyzer import IndividualAnalyzer


class _StubFinancialFetcher:
    def __init__(
        self,
        financial_data: list[dict],
        annual_data: list[dict] | None = None,
        stock_info: dict | None = None,
    ):
        self.financial_data = financial_data
        self.annual_data = annual_data
        self.stock_info = stock_info if stock_info is not None else {"Code": "7203", "CompanyName": "テスト株式会社"}
        self.calculate_annual_data: list[dict] | None = None

    async def fetch_financial_data(self, code: str, include_2q: bool) -> tuple[dict, list[dict], list[dict]]:
        return (
            self.stock_info,
            self.financial_data,
            self.annual_data if self.annual_data is not None else [
                {"CurPerType": "FY", "CurFYEn": "2024-03-31"},
                {"CurPerType": "FY", "CurFYEn": "2023-03-31"},
            ],
        )

    async def calculate_metrics(self, code: str, annual_data: list[dict], actual_years: int) -> dict:
        self.calculate_annual_data = annual_data
        return {
            "code": code,
            "analysis_years": actual_years,
            "years": [
                {
                    "fy_end": "2024-03-31",
                    "FinancialPeriod": "FY",
                    "RawData": {},
                    "CalculatedData": {"Sales": 1000.0},
                }
            ],
        }


class _ConcurrentEdinetFetcher:
    def __init__(self) -> None:
        self.predownload_started = asyncio.Event()
        self.fetch_started = asyncio.Event()
        self.extract_pre_parsed_map: dict | None = None
        self.fetch_max_documents: int | None = None

    async def predownload_and_parse(self, code: str, financial_data: list[dict], actual_years: int) -> dict:
        self.predownload_started.set()
        await asyncio.wait_for(self.fetch_started.wait(), timeout=1.0)
        return {"20240331": {"elements": []}}

    async def fetch_edinet_data_async(
        self,
        code: str,
        financial_data: list[dict],
        max_documents: int = 10,
    ) -> dict:
        self.fetch_max_documents = max_documents
        await asyncio.wait_for(self.predownload_started.wait(), timeout=1.0)
        self.fetch_started.set()
        return {"documents": [{"docID": "S100TEST"}]}

    async def extract_all_by_year(
        self,
        code: str,
        financial_data: list[dict],
        actual_years: int,
        pre_parsed_map: dict | None = None,
    ) -> dict:
        self.extract_pre_parsed_map = pre_parsed_map
        return {
            "gp": {"20240331": {"current": 400_000_000, "method": "direct"}},
            "doc_ids": {"20240331": "S100TEST"},
        }


class _FailingEdinetFetcher:
    async def build_xbrl_annual_records(self, *args, **kwargs) -> list:
        raise AssertionError("EDINET annual record fallback should not be called with annual_data")

    async def predownload_and_parse(self, *args, **kwargs) -> dict:
        raise AssertionError("EDINET predownload should not be called without financial_data")

    async def fetch_edinet_data_async(self, *args, **kwargs) -> dict:
        raise AssertionError("EDINET metadata fetch should not be called without financial_data")

    async def extract_all_by_year(self, *args, **kwargs) -> dict:
        raise AssertionError("EDINET metric extraction should not be called without financial_data")


class _EdinetOnlyFetcher:
    def __init__(self) -> None:
        self.build_args: tuple | None = None
        self.predownload_financial_data: list[dict] | None = None
        self.fetch_financial_data: list[dict] | None = None

    async def build_xbrl_annual_records(self, *args, **kwargs) -> list[dict]:
        self.build_args = (args, kwargs)
        return [
            {
                "Code": "7203",
                "CurPerType": "FY",
                "CurFYSt": "2023-04-01",
                "CurFYEn": "2024-03-31",
                "DiscDate": "2024-06-24",
                "Sales": 1_000_000_000,
                "OP": 100_000_000,
                "NP": 80_000_000,
                "Eq": 500_000_000,
                "_xbrl_source": True,
            }
        ]

    async def predownload_and_parse(self, code: str, financial_data: list[dict], actual_years: int) -> dict:
        self.predownload_financial_data = financial_data
        return {}

    async def fetch_edinet_data_async(
        self,
        code: str,
        financial_data: list[dict],
        max_documents: int = 10,
    ) -> dict:
        self.fetch_financial_data = financial_data
        return {}

    async def extract_all_by_year(
        self,
        code: str,
        financial_data: list[dict],
        actual_years: int,
        pre_parsed_map: dict | None = None,
    ) -> dict:
        return {"doc_ids": {}}


def _make_analyzer(financial_data: list[dict], edinet_fetcher: object) -> IndividualAnalyzer:
    analyzer = IndividualAnalyzer(api_client=object(), edinet_client=object())
    analyzer._financial_fetcher = _StubFinancialFetcher(financial_data)
    analyzer._edinet_fetcher = edinet_fetcher
    return analyzer


@pytest.mark.asyncio
async def test_fetch_analysis_data_fetches_edinet_metadata_in_parallel_with_predownload() -> None:
    edinet_fetcher = _ConcurrentEdinetFetcher()
    analyzer = _make_analyzer([{"DisclosedDate": "2024-06-01"}], edinet_fetcher)

    with patch("mebuki.services.analyzer._apply_wacc"):
        result = await analyzer.fetch_analysis_data("7203", analysis_years=1, max_documents=3)

    assert result["edinet_data"] == {"documents": [{"docID": "S100TEST"}]}
    assert edinet_fetcher.fetch_max_documents == 3
    assert edinet_fetcher.extract_pre_parsed_map == {"20240331": {"elements": []}}
    assert result["metrics"]["years"][0]["CalculatedData"]["GrossProfit"] == pytest.approx(400.0)
    assert result["metrics"]["years"][0]["CalculatedData"]["DocID"] == "S100TEST"


@pytest.mark.asyncio
async def test_fetch_analysis_data_uses_edinet_annual_records_without_jquants_data() -> None:
    edinet_fetcher = _EdinetOnlyFetcher()
    analyzer = IndividualAnalyzer(api_client=object(), edinet_client=object())
    financial_fetcher = _StubFinancialFetcher([], annual_data=[])
    analyzer._financial_fetcher = financial_fetcher
    analyzer._edinet_fetcher = edinet_fetcher

    with patch("mebuki.services.analyzer._apply_wacc"):
        result = await analyzer.fetch_analysis_data("7203", analysis_years=1)

    assert result["edinet_data"] == {}
    assert result["metrics"]["analysis_years"] == 1
    assert financial_fetcher.calculate_annual_data is not None
    assert financial_fetcher.calculate_annual_data[0]["_xbrl_source"] is True
    assert edinet_fetcher.predownload_financial_data == financial_fetcher.calculate_annual_data
    assert edinet_fetcher.fetch_financial_data == financial_fetcher.calculate_annual_data
