import json
import os
from datetime import datetime, timedelta

from mebuki.services.cache_pruner import CachePruner


def _touch_old(path, days: int) -> None:
    ts = (datetime.now() - timedelta(days=days)).timestamp()
    os.utime(path, (ts, ts))


def test_prune_boj_removes_files_and_metadata(tmp_path) -> None:
    from mebuki.utils.cache import CacheManager

    cache = CacheManager(cache_dir=str(tmp_path))
    cache.set("boj_legacy", [{"value": 1}])
    cache.set("mof_rf_rates", {"rates": {}})

    summary = CachePruner(tmp_path).prune(dry_run=False, include_boj=True)

    assert summary.removed_files == 1
    assert not (tmp_path / "boj_legacy.json").exists()
    assert (tmp_path / "mof_rf_rates.json").exists()
    metadata = json.loads((tmp_path / "metadata.json").read_text(encoding="utf-8"))
    assert "boj_legacy" not in metadata
    assert "mof_rf_rates" in metadata


def test_prune_dry_run_does_not_delete(tmp_path) -> None:
    from mebuki.utils.cache import CacheManager

    cache = CacheManager(cache_dir=str(tmp_path))
    cache.set("boj_legacy", [{"value": 1}])

    summary = CachePruner(tmp_path).prune(dry_run=True, include_boj=True)

    assert summary.removed_files == 1
    assert (tmp_path / "boj_legacy.json").exists()
    assert "boj_legacy" in json.loads((tmp_path / "metadata.json").read_text(encoding="utf-8"))


def test_prune_edinet_by_age(tmp_path) -> None:
    edinet_dir = tmp_path / "edinet"
    edinet_dir.mkdir()

    old_search = edinet_dir / "search_2024-01-01.json"
    new_search = edinet_dir / "search_2024-02-01.json"
    old_search.write_text("[]", encoding="utf-8")
    new_search.write_text("[]", encoding="utf-8")
    _touch_old(old_search, 40)
    _touch_old(new_search, 5)

    old_xbrl = edinet_dir / "S100OLD_xbrl"
    new_xbrl = edinet_dir / "S100NEW_xbrl"
    old_xbrl.mkdir()
    new_xbrl.mkdir()
    (old_xbrl / "doc.xbrl").write_text("old", encoding="utf-8")
    (new_xbrl / "doc.xbrl").write_text("new", encoding="utf-8")
    _touch_old(old_xbrl, 40)
    _touch_old(new_xbrl, 5)

    summary = CachePruner(tmp_path).prune(
        dry_run=False,
        include_boj=False,
        edinet_search_days=30,
        edinet_xbrl_days=30,
    )

    assert summary.removed_files == 1
    assert summary.removed_dirs == 1
    assert not old_search.exists()
    assert new_search.exists()
    assert not old_xbrl.exists()
    assert new_xbrl.exists()


def test_stats_and_audit_detect_deprecated_and_unknown_cache(tmp_path) -> None:
    from mebuki.utils.cache import CacheManager

    cache = CacheManager(cache_dir=str(tmp_path))
    cache.set("boj_legacy", [{"value": 1}])
    cache.set("mof_rf_rates", {"rates": {}})
    (tmp_path / "manual_dump.json").write_text("{}", encoding="utf-8")

    edinet_dir = tmp_path / "edinet"
    edinet_dir.mkdir()
    (edinet_dir / "search_2024-01-01.json").write_text("[]", encoding="utf-8")
    xbrl_dir = edinet_dir / "S100TEST_xbrl"
    xbrl_dir.mkdir()
    (xbrl_dir / "doc.xbrl").write_text("xbrl", encoding="utf-8")

    pruner = CachePruner(tmp_path)
    stats = pruner.stats()
    findings = pruner.audit()

    assert stats.total_files == 6
    assert stats.edinet_search_files == 1
    assert stats.edinet_xbrl_dirs == 1
    assert stats.boj_files == 1
    assert stats.boj_metadata_entries == 1
    assert stats.unknown_root_json_files == 1
    assert {finding.kind for finding in findings} == {
        "deprecated_boj_file",
        "deprecated_boj_metadata",
        "unknown_root_json_cache",
    }
