import json
import os
from datetime import datetime, timedelta
from pathlib import Path

from mebuki.api.edinet_cache_store import EdinetCacheStore


def _age(path: Path, days: int) -> None:
    ts = (datetime.now() - timedelta(days=days)).timestamp()
    os.utime(path, (ts, ts))


def test_load_search_cache_returns_fresh_empty_result(tmp_path):
    store = EdinetCacheStore(
        tmp_path,
        search_empty_ttl_days=1,
        search_hit_ttl_days=30,
    )
    filename = store.search_cache_key("2024-06-01")
    store.save_search_cache(filename, [])

    assert store.load_search_cache(filename) == []


def test_load_search_cache_expires_empty_result_quickly(tmp_path):
    store = EdinetCacheStore(
        tmp_path,
        search_empty_ttl_days=1,
        search_hit_ttl_days=30,
    )
    filename = store.search_cache_key("2024-06-01")
    store.save_search_cache(filename, [])
    _age(tmp_path / filename, days=1)

    assert store.load_search_cache(filename) is None


def test_load_search_cache_keeps_hit_result_longer_than_empty_result(tmp_path):
    store = EdinetCacheStore(
        tmp_path,
        search_empty_ttl_days=1,
        search_hit_ttl_days=30,
    )
    filename = store.search_cache_key("2024-06-01")
    documents = [{"docID": "S100TEST", "docTypeCode": "120"}]
    store.save_search_cache(filename, documents)
    _age(tmp_path / filename, days=1)

    assert store.load_search_cache(filename) == documents


def test_load_search_cache_expires_old_hit_result(tmp_path):
    store = EdinetCacheStore(
        tmp_path,
        search_empty_ttl_days=1,
        search_hit_ttl_days=30,
    )
    filename = store.search_cache_key("2024-06-01")
    store.save_search_cache(filename, [{"docID": "S100TEST"}])
    _age(tmp_path / filename, days=30)

    assert store.load_search_cache(filename) is None


def test_load_search_cache_rejects_non_list_payload(tmp_path):
    store = EdinetCacheStore(
        tmp_path,
        search_empty_ttl_days=1,
        search_hit_ttl_days=30,
    )
    filename = store.search_cache_key("2024-06-01")
    (tmp_path / filename).write_text(json.dumps({"results": []}), encoding="utf-8")

    assert store.load_search_cache(filename) is None
