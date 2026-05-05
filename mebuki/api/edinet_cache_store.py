"""
EDINET ローカルキャッシュ境界。

日別書類一覧と XBRL パッケージの保存形式を API 通信から分離する。
"""

import json
import logging
import os
import shutil
import zipfile
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from mebuki.constants.api import (
    EDINET_DOCUMENT_INDEX_VERSION,
    EDINET_SEARCH_EMPTY_TTL_DAYS,
    EDINET_SEARCH_HIT_TTL_DAYS,
    EDINET_SEARCH_PAST_TTL_DAYS,
    EDINET_XBRL_MAX_BYTES,
)
from mebuki.utils.fiscal_year import parse_date_string

logger = logging.getLogger(__name__)


class EdinetCacheStore:
    """EDINET の日別検索結果と XBRL 展開ディレクトリを管理する。"""

    def __init__(
        self,
        cache_dir: str | Path,
        *,
        search_empty_ttl_days: int = EDINET_SEARCH_EMPTY_TTL_DAYS,
        search_hit_ttl_days: int = EDINET_SEARCH_HIT_TTL_DAYS,
        search_past_ttl_days: int = EDINET_SEARCH_PAST_TTL_DAYS,
        max_xbrl_bytes: int | None = EDINET_XBRL_MAX_BYTES,
    ):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.search_empty_ttl_days = search_empty_ttl_days
        self.search_hit_ttl_days = search_hit_ttl_days
        self.search_past_ttl_days = search_past_ttl_days
        self.max_xbrl_bytes = max_xbrl_bytes

    def search_cache_key(self, date_str: str) -> str:
        """日別検索キャッシュのファイル名を返す。"""
        return f"search_{date_str}.json"

    def document_index_cache_key(self, year: int) -> str:
        """年次書類インデックスのファイル名を返す。"""
        return f"doc_index_{year}.json"

    def load_search_cache(self, filename: str) -> list[dict[str, Any]] | None:
        """日別検索結果をキャッシュから読み込む。"""
        cache_path = self.cache_dir / filename
        if not cache_path.exists():
            return None
        try:
            data = json.loads(cache_path.read_text(encoding="utf-8"))
        except Exception as e:
            logger.warning(f"Cache load failed: {e}")
            return None
        if not isinstance(data, list):
            logger.warning(f"Cache load failed: expected list in {cache_path}")
            return None
        if self._is_search_cache_expired(cache_path, has_results=bool(data)):
            return None
        return data

    def save_search_cache(self, filename: str, data: list[dict[str, Any]]) -> None:
        """日別検索結果をキャッシュに保存する。"""
        cache_path = self.cache_dir / filename
        try:
            cache_path.write_text(
                json.dumps(data, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception as e:
            logger.warning(f"Cache save failed: {e}")

    def load_document_index(
        self,
        year: int,
        *,
        required_through: str | None = None,
    ) -> list[dict[str, Any]] | None:
        """年次書類インデックスをキャッシュから読み込む。"""
        cache_path = self.cache_dir / self.document_index_cache_key(year)
        if not cache_path.exists():
            return None
        try:
            payload = json.loads(cache_path.read_text(encoding="utf-8"))
        except Exception as e:
            logger.warning(f"Document index load failed: {e}")
            return None
        if not isinstance(payload, dict):
            logger.warning(f"Document index load failed: expected dict in {cache_path}")
            return None
        if payload.get("_cache_version") != EDINET_DOCUMENT_INDEX_VERSION:
            return None
        if payload.get("year") != year:
            return None
        built_through = payload.get("built_through")
        if required_through is not None and (
            not isinstance(built_through, str) or built_through < required_through
        ):
            return None
        documents = payload.get("documents")
        if not isinstance(documents, list):
            logger.warning(f"Document index load failed: expected documents list in {cache_path}")
            return None
        return documents

    def save_document_index(
        self,
        year: int,
        documents: list[dict[str, Any]],
        *,
        built_through: str,
    ) -> None:
        """年次書類インデックスを保存する。"""
        cache_path = self.cache_dir / self.document_index_cache_key(year)
        payload = {
            "_cache_version": EDINET_DOCUMENT_INDEX_VERSION,
            "year": year,
            "built_through": built_through,
            "documents": documents,
        }
        try:
            cache_path.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception as e:
            logger.warning(f"Document index save failed: {e}")

    def xbrl_dir(self, doc_id: str, save_dir: str | Path | None = None) -> Path:
        """XBRL 展開ディレクトリのパスを返す。"""
        root = Path(save_dir) if save_dir is not None else self.cache_dir
        return root / f"{doc_id}_xbrl"

    def has_xbrl_dir(self, doc_id: str, save_dir: str | Path | None = None) -> bool:
        """XBRL 展開済みディレクトリがあるかを返す。"""
        dest = self.xbrl_dir(doc_id, save_dir)
        return dest.exists() and dest.is_dir()

    def touch_xbrl_dir(self, doc_id: str, save_dir: str | Path | None = None) -> None:
        """XBRL 展開ディレクトリの mtime を更新する。"""
        dest = self.xbrl_dir(doc_id, save_dir)
        if dest.exists() and dest.is_dir():
            os.utime(dest, None)

    def store_xbrl_zip(
        self,
        doc_id: str,
        content: bytes,
        save_dir: str | Path | None = None,
    ) -> Path:
        """XBRL zip を一時保存して安全に展開し、展開ディレクトリを返す。"""
        root = Path(save_dir) if save_dir is not None else self.cache_dir
        root.mkdir(parents=True, exist_ok=True)
        dest = self.xbrl_dir(doc_id, root)
        zip_path = root / f"{doc_id}.zip"

        zip_path.write_bytes(content)
        try:
            with zipfile.ZipFile(zip_path, "r") as z:
                self._validate_members(z, dest)
                dest.mkdir(parents=True, exist_ok=True)
                z.extractall(dest)
        except Exception:
            if dest.exists():
                shutil.rmtree(dest)
            raise
        finally:
            if zip_path.exists():
                zip_path.unlink()
        self._evict_xbrl_if_needed(root)
        return dest

    def _validate_members(self, archive: zipfile.ZipFile, dest: Path) -> None:
        dest_resolved = dest.resolve()
        for member in archive.namelist():
            member_path = (dest / member).resolve()
            try:
                member_path.relative_to(dest_resolved)
            except ValueError as e:
                raise ValueError(f"不正なZIPエントリ: {member}") from e

    def _is_search_cache_expired(self, cache_path: Path, *, has_results: bool) -> bool:
        ttl_days = self._search_cache_ttl_days(cache_path, has_results=has_results)
        mtime = datetime.fromtimestamp(cache_path.stat().st_mtime)
        return (datetime.now() - mtime).days >= ttl_days

    def _search_cache_ttl_days(self, cache_path: Path, *, has_results: bool) -> int:
        date_part = cache_path.stem.removeprefix("search_")
        cache_date = parse_date_string(date_part)
        if cache_date is not None and cache_date.date() < datetime.now().date() - timedelta(days=1):
            return self.search_past_ttl_days
        return self.search_hit_ttl_days if has_results else self.search_empty_ttl_days

    def _evict_xbrl_if_needed(self, root: Path) -> None:
        if self.max_xbrl_bytes is None:
            return

        dirs = sorted(
            (path for path in root.glob("*_xbrl") if path.is_dir()),
            key=lambda path: path.stat().st_mtime,
        )
        total_bytes = sum(self._path_size(path) for path in dirs)
        if total_bytes <= self.max_xbrl_bytes:
            return

        for path in dirs:
            if total_bytes <= self.max_xbrl_bytes:
                break
            size_bytes = self._path_size(path)
            logger.info(f"[EDINET] evict XBRL cache: {path} ({size_bytes} bytes)")
            shutil.rmtree(path)
            total_bytes -= size_bytes

    @staticmethod
    def _path_size(path: Path) -> int:
        return sum(child.stat().st_size for child in path.rglob("*") if child.is_file())
