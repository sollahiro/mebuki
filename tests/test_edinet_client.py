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


class _FailingRequestClient(EdinetAPIClient):
    def __init__(self, api_key: str, cache_store: EdinetCacheStore) -> None:
        super().__init__(api_key=api_key, cache_store=cache_store)
        self.request_calls = 0

    async def _request(
        self,
        endpoint: str,
        params: dict[str, Any] | None = None,
        max_retries: int = 3,
    ) -> dict[str, Any]:
        self.request_calls += 1
        raise RuntimeError("edinet down")


class _EmptyIndexClient(EdinetAPIClient):
    def __init__(self, api_key: str, cache_store: EdinetCacheStore) -> None:
        super().__init__(api_key=api_key, cache_store=cache_store)
        self.build_calls = 0

    async def _build_document_index_for_year(self, year: int, required_through: date) -> list[dict[str, Any]]:
        self.build_calls += 1
        return []


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


@pytest.mark.asyncio
async def test_documents_for_date_prefers_stale_search_cache(tmp_path) -> None:
    store = EdinetCacheStore(tmp_path, search_hit_ttl_days=0)
    filename = store.search_cache_key("2024-06-24")
    documents = [{"docID": "S100STALE", "docTypeCode": "120"}]
    store.save_search_cache(filename, documents)
    client = _FailingRequestClient(api_key="dummy", cache_store=store)

    assert await client._get_documents_for_date("2024-06-24") == documents
    assert client.request_calls == 0


@pytest.mark.asyncio
async def test_document_index_prefers_stale_index(tmp_path) -> None:
    store = EdinetCacheStore(tmp_path)
    year = date.today().year
    documents = [{"docID": "S100STALE", "docTypeCode": "120"}]
    store.save_document_index(year, documents, built_through=f"{year}-01-01")
    client = _EmptyIndexClient(api_key="dummy", cache_store=store)

    assert await client.ensure_document_index_for_year(year) == documents
    assert client.build_calls == 0
