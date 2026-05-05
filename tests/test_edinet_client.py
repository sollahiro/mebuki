from datetime import date
from typing import Any

import pytest

from mebuki.api.edinet_cache_store import EdinetCacheStore
from mebuki.api.edinet_client import EdinetAPIClient


class _FakeEdinetClient(EdinetAPIClient):
    def __init__(self, cache_store: EdinetCacheStore, docs_by_date: dict[str, list[dict[str, Any]]]):
        super().__init__(api_key="dummy", cache_store=cache_store)
        self.docs_by_date = docs_by_date
        self.fetch_dates: list[str] = []

    async def _get_documents_for_date(self, date_str: str) -> list[dict[str, Any]]:
        self.fetch_dates.append(date_str)
        return self.docs_by_date.get(date_str, [])


@pytest.mark.asyncio
async def test_document_index_builds_year_cache_with_low_parallel_fetch(tmp_path) -> None:
    store = EdinetCacheStore(tmp_path)
    client = _FakeEdinetClient(
        store,
        {
            "2024-06-24": [{
                "docID": "S100TEST",
                "secCode": "72030",
                "docTypeCode": "120",
                "periodEnd": "2024-03-31",
                "submitDateTime": "2024-06-24 10:00",
            }]
        },
    )

    docs = await client.ensure_document_index_for_year(2024)
    cached = store.load_document_index(2024, required_through="2024-12-31")

    assert docs == cached
    assert {
        "docID": "S100TEST",
        "secCode": "72030",
        "docTypeCode": "120",
        "periodEnd": "2024-03-31",
        "submitDateTime": "2024-06-24 10:00",
        "_edinet_list_date": "2024-06-24",
    } in docs
    assert len(client.fetch_dates) == 366


@pytest.mark.asyncio
async def test_get_documents_for_date_range_uses_year_index_for_wide_ranges(tmp_path) -> None:
    store = EdinetCacheStore(tmp_path)
    store.save_document_index(
        2024,
        [
            {
                "docID": "IN",
                "submitDateTime": "2024-06-24 10:00",
                "_edinet_list_date": "2024-06-24",
            },
            {
                "docID": "OUT",
                "submitDateTime": "2024-08-01 10:00",
                "_edinet_list_date": "2024-08-01",
            },
        ],
        built_through="2024-12-31",
    )
    client = _FakeEdinetClient(store, {})

    docs_by_date = await client.get_documents_for_date_range(
        date(2024, 6, 1),
        date(2024, 6, 30),
    )

    assert docs_by_date["2024-06-24"][0]["docID"] == "IN"
    assert all(doc.get("docID") != "OUT" for docs in docs_by_date.values() for doc in docs)
    assert client.fetch_dates == []
