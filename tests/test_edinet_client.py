from contextlib import AbstractContextManager, nullcontext
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import pytest

from mebuki.api.edinet_cache_backend import EdinetCacheBackend
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


class _MemoryEdinetCacheBackend(EdinetCacheBackend):
    def __init__(self, cache_dir: Path) -> None:
        self.cache_dir = cache_dir
        self.xbrl_root_dir = cache_dir / "xbrl"
        self.search_payloads: dict[str, list[dict[str, Any]]] = {}
        self.document_indexes: dict[int, dict[str, Any]] = {}

    def search_cache_key(self, date_str: str) -> str:
        return f"memory_search_{date_str}"

    def document_index_cache_key(self, year: int) -> str:
        return f"memory_doc_index_{year}"

    def load_search_cache(
        self,
        filename: str,
        *,
        allow_expired: bool = False,
    ) -> list[dict[str, Any]] | None:
        return self.search_payloads.get(filename)

    def save_search_cache(self, filename: str, data: list[dict[str, Any]]) -> None:
        self.search_payloads[filename] = data

    def file_lock(self, name: str) -> AbstractContextManager[None]:
        return nullcontext()

    def load_document_index(
        self,
        year: int,
        *,
        required_through: str | None = None,
        allow_stale: bool = False,
    ) -> list[dict[str, Any]] | None:
        info = self.load_document_index_info(
            year,
            required_through=required_through,
            allow_stale=allow_stale,
        )
        if info is None:
            return None
        documents = info.get("documents")
        return documents if isinstance(documents, list) else None

    def load_document_index_info(
        self,
        year: int,
        *,
        required_through: str | None = None,
        allow_stale: bool = False,
    ) -> dict[str, Any] | None:
        return self.document_indexes.get(year)

    def save_document_index(
        self,
        year: int,
        documents: list[dict[str, Any]],
        *,
        built_through: str,
    ) -> None:
        self.document_indexes[year] = {
            "year": year,
            "built_through": built_through,
            "documents": documents,
        }

    def clear_document_index(self, year: int) -> None:
        self.document_indexes.pop(year, None)

    def xbrl_dir(self, doc_id: str, save_dir: str | Path | None = None) -> Path:
        root = Path(save_dir) if save_dir is not None else self.xbrl_root_dir
        return root / f"{doc_id}_xbrl"

    def has_xbrl_dir(self, doc_id: str, save_dir: str | Path | None = None) -> bool:
        return self.xbrl_dir(doc_id, save_dir).is_dir()

    def touch_xbrl_dir(self, doc_id: str, save_dir: str | Path | None = None) -> None:
        return None

    def store_xbrl_zip(
        self,
        doc_id: str,
        content: bytes,
        save_dir: str | Path | None = None,
    ) -> Path:
        dest = self.xbrl_dir(doc_id, save_dir)
        dest.mkdir(parents=True, exist_ok=True)
        return dest


def test_client_accepts_cache_backend_boundary(tmp_path) -> None:
    backend = _MemoryEdinetCacheBackend(tmp_path)
    client = EdinetAPIClient(api_key="dummy", cache_store=backend)
    filename = client._get_search_cache_key("2024-06-24")

    client._save_search_cache(filename, [{"docID": "MEMORY"}])

    assert client.cache_store is backend
    assert client.cache_dir == tmp_path
    assert client._load_search_cache(filename) == [{"docID": "MEMORY"}]


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


@pytest.mark.asyncio
async def test_document_index_catchup_fetches_only_missing_dates(tmp_path) -> None:
    today = date.today()
    yesterday = today - timedelta(days=1)
    store = EdinetCacheStore(tmp_path)
    store.save_document_index(
        today.year,
        [{"docID": "OLD", "_edinet_list_date": yesterday.strftime("%Y-%m-%d")}],
        built_through=yesterday.strftime("%Y-%m-%d"),
    )
    client = _FakeEdinetClient(
        store,
        {
            today.strftime("%Y-%m-%d"): [{
                "docID": "NEW",
                "submitDateTime": f"{today.strftime('%Y-%m-%d')} 10:00",
            }]
        },
    )

    docs = await client.catchup_document_index_for_year(today.year)
    cached_info = store.load_document_index_info(today.year, allow_stale=True)

    assert [doc["docID"] for doc in docs] == ["OLD", "NEW"]
    assert client.fetch_dates == [today.strftime("%Y-%m-%d")]
    assert cached_info is not None
    assert cached_info["built_through"] == today.strftime("%Y-%m-%d")
