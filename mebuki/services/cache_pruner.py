"""
キャッシュ整理サービス

廃止済みキャッシュや肥大化しやすい EDINET キャッシュを削除する。
"""

import shutil
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path

from mebuki.utils.cache import CacheManager


@dataclass(frozen=True)
class PruneSummary:
    removed_files: int = 0
    removed_dirs: int = 0
    freed_bytes: int = 0
    scanned_files: int = 0
    scanned_dirs: int = 0
    dry_run: bool = True

    def to_dict(self) -> dict[str, int | bool]:
        return asdict(self)


@dataclass(frozen=True)
class CacheStats:
    cache_dir: str
    total_files: int = 0
    total_dirs: int = 0
    total_bytes: int = 0
    metadata_entries: int = 0
    root_json_files: int = 0
    edinet_search_files: int = 0
    edinet_xbrl_dirs: int = 0
    boj_files: int = 0
    boj_metadata_entries: int = 0
    unknown_root_json_files: int = 0

    def to_dict(self) -> dict[str, int | str]:
        return asdict(self)



class CachePruner:
    """キャッシュディレクトリのスリム化を担当する。"""

    def __init__(self, cache_dir: str | Path):
        self.cache_dir = Path(cache_dir)
        self.edinet_dir = self.cache_dir / "edinet"
        self.cache_manager = CacheManager(cache_dir=str(self.cache_dir))

    def prune(
        self,
        *,
        dry_run: bool = True,
        include_boj: bool = True,
        edinet_search_days: int | None = None,
        edinet_xbrl_days: int | None = None,
    ) -> PruneSummary:
        summary = PruneSummary(dry_run=dry_run)
        if include_boj:
            summary = self._merge(summary, self._prune_boj(dry_run=dry_run))
        if edinet_search_days is not None:
            summary = self._merge(
                summary,
                self._prune_edinet_search(days=edinet_search_days, dry_run=dry_run),
            )
        if edinet_xbrl_days is not None:
            summary = self._merge(
                summary,
                self._prune_edinet_xbrl(days=edinet_xbrl_days, dry_run=dry_run),
            )
        return summary

    def stats(self) -> CacheStats:
        """キャッシュ全体のサイズと主要カテゴリ別件数を返す。"""
        files = [path for path in self.cache_dir.rglob("*") if path.is_file()]
        dirs = [path for path in self.cache_dir.rglob("*") if path.is_dir()]
        metadata_keys = self.cache_manager.keys()
        root_json_files = [
            path
            for path in self.cache_dir.glob("*.json")
            if path.name != "metadata.json"
        ]
        boj_files = sorted(self.cache_dir.glob("boj_*.json"))
        known_root_prefixes = (
            "individual_analysis_",
            "half_year_periods_",
            "mof_",
            "boj_",
        )
        unknown_root_json_files = [
            path
            for path in root_json_files
            if not path.stem.startswith(known_root_prefixes)
        ]

        return CacheStats(
            cache_dir=str(self.cache_dir),
            total_files=len(files),
            total_dirs=len(dirs),
            total_bytes=sum(path.stat().st_size for path in files),
            metadata_entries=len(metadata_keys),
            root_json_files=len(root_json_files),
            edinet_search_files=len(list(self.edinet_dir.glob("search_*.json"))),
            edinet_xbrl_dirs=len([path for path in self.edinet_dir.glob("*_xbrl") if path.is_dir()]),
            boj_files=len(boj_files),
            boj_metadata_entries=len([key for key in metadata_keys if key.startswith("boj_")]),
            unknown_root_json_files=len(unknown_root_json_files),
        )

    def _prune_boj(self, *, dry_run: bool) -> PruneSummary:
        files = sorted(self.cache_dir.glob("boj_*.json"))
        freed = sum(path.stat().st_size for path in files if path.exists())
        if not dry_run:
            self.cache_manager.clear_prefix("boj_")
            for path in files:
                if path.exists():
                    path.unlink()
        return PruneSummary(
            removed_files=len(files),
            freed_bytes=freed,
            scanned_files=len(files),
            dry_run=dry_run,
        )

    def _prune_edinet_search(self, *, days: int, dry_run: bool) -> PruneSummary:
        files = [
            path
            for path in self.edinet_dir.glob("search_*.json")
            if self._age_days(path) >= days
        ]
        freed = sum(path.stat().st_size for path in files if path.exists())
        if not dry_run:
            for path in files:
                if path.exists():
                    path.unlink()
        return PruneSummary(
            removed_files=len(files),
            freed_bytes=freed,
            scanned_files=len(files),
            dry_run=dry_run,
        )

    def _prune_edinet_xbrl(self, *, days: int, dry_run: bool) -> PruneSummary:
        dirs = [
            path
            for path in self.edinet_dir.glob("*_xbrl")
            if path.is_dir() and self._age_days(path) >= days
        ]
        freed = sum(self._path_size(path) for path in dirs)
        if not dry_run:
            for path in dirs:
                if path.exists():
                    shutil.rmtree(path)
        return PruneSummary(
            removed_dirs=len(dirs),
            freed_bytes=freed,
            scanned_dirs=len(dirs),
            dry_run=dry_run,
        )

    @staticmethod
    def _age_days(path: Path) -> int:
        mtime = datetime.fromtimestamp(path.stat().st_mtime)
        return (datetime.now() - mtime).days

    @staticmethod
    def _path_size(path: Path) -> int:
        if path.is_file():
            return path.stat().st_size
        return sum(child.stat().st_size for child in path.rglob("*") if child.is_file())

    @staticmethod
    def _merge(left: PruneSummary, right: PruneSummary) -> PruneSummary:
        return PruneSummary(
            removed_files=left.removed_files + right.removed_files,
            removed_dirs=left.removed_dirs + right.removed_dirs,
            freed_bytes=left.freed_bytes + right.freed_bytes,
            scanned_files=left.scanned_files + right.scanned_files,
            scanned_dirs=left.scanned_dirs + right.scanned_dirs,
            dry_run=left.dry_run and right.dry_run,
        )
