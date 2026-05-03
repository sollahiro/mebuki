import json
import os
import zipfile
from datetime import datetime, timedelta
from io import BytesIO
from pathlib import Path

from mebuki.api.edinet_cache_store import EdinetCacheStore


def _age(path: Path, days: int) -> None:
    ts = (datetime.now() - timedelta(days=days)).timestamp()
    os.utime(path, (ts, ts))


def _set_mtime(path: Path, ts: float) -> None:
    os.utime(path, (ts, ts))


def _make_xbrl_zip(files: dict[str, bytes]) -> bytes:
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for name, content in files.items():
            archive.writestr(name, content)
    return buffer.getvalue()


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


def test_store_xbrl_zip_evicts_oldest_dirs_when_over_limit(tmp_path):
    store = EdinetCacheStore(tmp_path, max_xbrl_bytes=100)
    base_ts = datetime.now().timestamp() - 100

    store.store_xbrl_zip("DOC1", _make_xbrl_zip({"a.txt": b"1234"}))
    store.store_xbrl_zip("DOC2", _make_xbrl_zip({"a.txt": b"1234"}))
    store.store_xbrl_zip("DOC3", _make_xbrl_zip({"a.txt": b"1234"}))
    _set_mtime(store.xbrl_dir("DOC1"), base_ts)
    _set_mtime(store.xbrl_dir("DOC2"), base_ts + 1)
    _set_mtime(store.xbrl_dir("DOC3"), base_ts + 2)
    store.max_xbrl_bytes = 10

    store.store_xbrl_zip("DOC4", _make_xbrl_zip({"a.txt": b"1234"}))

    assert not store.xbrl_dir("DOC1").exists()
    assert not store.xbrl_dir("DOC2").exists()
    assert store.xbrl_dir("DOC3").exists()
    assert store.xbrl_dir("DOC4").exists()


def test_store_xbrl_zip_keeps_dirs_when_within_limit(tmp_path):
    store = EdinetCacheStore(tmp_path, max_xbrl_bytes=20)

    store.store_xbrl_zip("DOC1", _make_xbrl_zip({"a.txt": b"1234"}))
    store.store_xbrl_zip("DOC2", _make_xbrl_zip({"a.txt": b"1234"}))
    store.store_xbrl_zip("DOC3", _make_xbrl_zip({"a.txt": b"1234"}))

    assert store.xbrl_dir("DOC1").exists()
    assert store.xbrl_dir("DOC2").exists()
    assert store.xbrl_dir("DOC3").exists()


def test_store_xbrl_zip_does_not_evict_when_max_xbrl_bytes_is_none(tmp_path):
    store = EdinetCacheStore(tmp_path, max_xbrl_bytes=None)

    store.store_xbrl_zip("DOC1", _make_xbrl_zip({"a.txt": b"1234"}))
    store.store_xbrl_zip("DOC2", _make_xbrl_zip({"a.txt": b"1234"}))
    store.store_xbrl_zip("DOC3", _make_xbrl_zip({"a.txt": b"1234"}))

    assert store.xbrl_dir("DOC1").exists()
    assert store.xbrl_dir("DOC2").exists()
    assert store.xbrl_dir("DOC3").exists()


def test_touch_xbrl_dir_updates_mtime(tmp_path):
    store = EdinetCacheStore(tmp_path)
    store.store_xbrl_zip("DOC1", _make_xbrl_zip({"a.txt": b"1234"}))
    xbrl_dir = store.xbrl_dir("DOC1")
    old_ts = datetime.now().timestamp() - 100
    _set_mtime(xbrl_dir, old_ts)

    before = xbrl_dir.stat().st_mtime
    store.touch_xbrl_dir("DOC1")
    after = xbrl_dir.stat().st_mtime

    assert after > before
