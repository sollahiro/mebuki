import json
import os
import time
import zipfile
from datetime import datetime, timedelta
from io import BytesIO
from pathlib import Path

from blue_ticker.api.edinet_cache_store import EdinetCacheStore


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


def _today_str() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def _search_cache_path(store: EdinetCacheStore, filename: str) -> Path:
    return store.documents_by_date_dir / filename


def test_load_search_cache_returns_fresh_empty_result(tmp_path):
    store = EdinetCacheStore(
        tmp_path,
        search_empty_ttl_days=1,
        search_hit_ttl_days=30,
    )
    filename = store.search_cache_key(_today_str())
    store.save_search_cache(filename, [])

    assert store.load_search_cache(filename) == []


def test_load_search_cache_expires_empty_result_quickly(tmp_path):
    store = EdinetCacheStore(
        tmp_path,
        search_empty_ttl_days=1,
        search_hit_ttl_days=30,
    )
    filename = store.search_cache_key(_today_str())
    store.save_search_cache(filename, [])
    _age(_search_cache_path(store, filename), days=1)

    assert store.load_search_cache(filename) is None


def test_load_search_cache_keeps_hit_result_longer_than_empty_result(tmp_path):
    store = EdinetCacheStore(
        tmp_path,
        search_empty_ttl_days=1,
        search_hit_ttl_days=30,
    )
    filename = store.search_cache_key(_today_str())
    documents = [{"docID": "S100TEST", "docTypeCode": "120"}]
    store.save_search_cache(filename, documents)
    _age(_search_cache_path(store, filename), days=1)

    assert store.load_search_cache(filename) == documents


def test_load_search_cache_expires_old_hit_result(tmp_path):
    store = EdinetCacheStore(
        tmp_path,
        search_empty_ttl_days=1,
        search_hit_ttl_days=30,
    )
    filename = store.search_cache_key(_today_str())
    store.save_search_cache(filename, [{"docID": "S100TEST"}])
    _age(_search_cache_path(store, filename), days=30)

    assert store.load_search_cache(filename) is None


def test_load_search_cache_can_allow_expired_result(tmp_path):
    store = EdinetCacheStore(
        tmp_path,
        search_empty_ttl_days=1,
        search_hit_ttl_days=30,
    )
    filename = store.search_cache_key(_today_str())
    documents = [{"docID": "S100TEST"}]
    store.save_search_cache(filename, documents)
    _age(_search_cache_path(store, filename), days=30)

    assert store.load_search_cache(filename, allow_expired=True) == documents


def test_load_search_cache_rejects_non_list_payload(tmp_path):
    store = EdinetCacheStore(
        tmp_path,
        search_empty_ttl_days=1,
        search_hit_ttl_days=30,
    )
    filename = store.search_cache_key("2024-06-01")
    _search_cache_path(store, filename).parent.mkdir(parents=True, exist_ok=True)
    _search_cache_path(store, filename).write_text(json.dumps({"results": []}), encoding="utf-8")

    assert store.load_search_cache(filename) is None


def test_load_search_cache_keeps_past_date_result_longer(tmp_path):
    store = EdinetCacheStore(
        tmp_path,
        search_empty_ttl_days=1,
        search_hit_ttl_days=30,
        search_past_ttl_days=3650,
    )
    filename = store.search_cache_key("2024-06-01")
    documents = [{"docID": "S100TEST", "docTypeCode": "120"}]
    store.save_search_cache(filename, documents)
    _age(_search_cache_path(store, filename), days=365)

    assert store.load_search_cache(filename) == documents


def test_document_index_roundtrip_requires_version_and_built_through(tmp_path):
    store = EdinetCacheStore(tmp_path)
    documents = [{"docID": "S100TEST", "docTypeCode": "120"}]
    store.save_document_index(2024, documents, built_through="2024-12-31")

    assert store.load_document_index(2024, required_through="2024-06-30") == documents
    assert store.load_document_index(2024, required_through="2025-01-01") is None


def test_document_index_can_allow_stale_built_through(tmp_path):
    store = EdinetCacheStore(tmp_path)
    documents = [{"docID": "S100TEST", "docTypeCode": "120"}]
    store.save_document_index(2024, documents, built_through="2024-06-30")

    assert store.load_document_index(2024, required_through="2024-12-31", allow_stale=True) == documents


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


def test_file_lock_creates_and_removes_lock_file(tmp_path):
    store = EdinetCacheStore(tmp_path)

    with store.file_lock("documents_by_date_2024-06-24"):
        assert list(store.locks_dir.glob("documents_by_date_2024-06-24.lock"))

    assert not list(store.locks_dir.glob("documents_by_date_2024-06-24.lock"))


def test_file_lock_removes_stale_lock(tmp_path, monkeypatch):
    store = EdinetCacheStore(tmp_path)
    store.locks_dir.mkdir(parents=True, exist_ok=True)
    lock_path = store.locks_dir / "document_index_2024.lock"
    lock_path.write_text("stale", encoding="utf-8")
    stale_ts = time.time() - 3600
    os.utime(lock_path, (stale_ts, stale_ts))
    monkeypatch.setattr("blue_ticker.api.edinet_cache_store.EDINET_CACHE_LOCK_STALE_SECONDS", 1)

    with store.file_lock("document_index_2024"):
        assert lock_path.exists()

    assert not lock_path.exists()


def test_file_lock_prints_wait_notice(tmp_path, monkeypatch, capsys):
    store = EdinetCacheStore(tmp_path)
    store.locks_dir.mkdir(parents=True, exist_ok=True)
    lock_path = store.locks_dir / "document_index_2024.lock"
    lock_path.write_text("active", encoding="utf-8")
    calls = {"count": 0}

    def fake_sleep(seconds: float) -> None:
        calls["count"] += 1
        if calls["count"] == 2 and lock_path.exists():
            lock_path.unlink()

    times = iter([0.0, 1.1, 1.3, 1.5])
    monkeypatch.setattr("blue_ticker.api.edinet_cache_store.time.monotonic", lambda: next(times))
    monkeypatch.setattr("blue_ticker.api.edinet_cache_store.time.sleep", fake_sleep)
    monkeypatch.setattr("blue_ticker.api.edinet_cache_store.EDINET_CACHE_LOCK_NOTICE_SECONDS", 1.0)

    with store.file_lock("document_index_2024"):
        pass

    captured = capsys.readouterr()
    assert "別のblue_tickerプロセスの完了を待っています" in captured.err
    assert "処理を続行します" in captured.err
