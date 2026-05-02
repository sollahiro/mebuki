"""
EDINET ローカルキャッシュ境界。

日別書類一覧と XBRL パッケージの保存形式を API 通信から分離する。
"""

import json
import logging
import shutil
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Any

from mebuki.constants.api import EDINET_SEARCH_EMPTY_TTL_DAYS, EDINET_SEARCH_HIT_TTL_DAYS

logger = logging.getLogger(__name__)


class EdinetCacheStore:
    """EDINET の日別検索結果と XBRL 展開ディレクトリを管理する。"""

    def __init__(
        self,
        cache_dir: str | Path,
        *,
        search_empty_ttl_days: int = EDINET_SEARCH_EMPTY_TTL_DAYS,
        search_hit_ttl_days: int = EDINET_SEARCH_HIT_TTL_DAYS,
    ):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.search_empty_ttl_days = search_empty_ttl_days
        self.search_hit_ttl_days = search_hit_ttl_days

    def search_cache_key(self, date_str: str) -> str:
        """日別検索キャッシュのファイル名を返す。"""
        return f"search_{date_str}.json"

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

    def xbrl_dir(self, doc_id: str, save_dir: str | Path | None = None) -> Path:
        """XBRL 展開ディレクトリのパスを返す。"""
        root = Path(save_dir) if save_dir is not None else self.cache_dir
        return root / f"{doc_id}_xbrl"

    def has_xbrl_dir(self, doc_id: str, save_dir: str | Path | None = None) -> bool:
        """XBRL 展開済みディレクトリがあるかを返す。"""
        dest = self.xbrl_dir(doc_id, save_dir)
        return dest.exists() and dest.is_dir()

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
        ttl_days = self.search_hit_ttl_days if has_results else self.search_empty_ttl_days
        mtime = datetime.fromtimestamp(cache_path.stat().st_mtime)
        return (datetime.now() - mtime).days >= ttl_days
