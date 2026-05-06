"""
EDINET external cache backend boundary.

Local CLI operation uses the file-backed implementation. Remote MCP/server
operation can provide another implementation with the same contract.
"""

from abc import ABC, abstractmethod
from contextlib import AbstractContextManager
from pathlib import Path
from typing import Any


class EdinetCacheBackend(ABC):
    """EDINET API由来キャッシュの差し替え境界。"""

    cache_dir: Path
    xbrl_root_dir: Path

    @abstractmethod
    def search_cache_key(self, date_str: str) -> str:
        """日別検索キャッシュキーを返す。"""

    @abstractmethod
    def document_index_cache_key(self, year: int) -> str:
        """年次書類インデックスのキャッシュキーを返す。"""

    @abstractmethod
    def load_search_cache(
        self,
        filename: str,
        *,
        allow_expired: bool = False,
    ) -> list[dict[str, Any]] | None:
        """日別検索結果を読み込む。"""

    @abstractmethod
    def save_search_cache(self, filename: str, data: list[dict[str, Any]]) -> None:
        """日別検索結果を保存する。"""

    @abstractmethod
    def file_lock(self, name: str) -> AbstractContextManager[None]:
        """同一キャッシュ生成処理の重複を避けるロックを返す。"""

    @abstractmethod
    def load_document_index(
        self,
        year: int,
        *,
        required_through: str | None = None,
        allow_stale: bool = False,
    ) -> list[dict[str, Any]] | None:
        """年次書類インデックスの documents を読み込む。"""

    @abstractmethod
    def load_document_index_info(
        self,
        year: int,
        *,
        required_through: str | None = None,
        allow_stale: bool = False,
    ) -> dict[str, Any] | None:
        """年次書類インデックスのメタ情報込み payload を読み込む。"""

    @abstractmethod
    def save_document_index(
        self,
        year: int,
        documents: list[dict[str, Any]],
        *,
        built_through: str,
    ) -> None:
        """年次書類インデックスを保存する。"""

    @abstractmethod
    def clear_document_index(self, year: int) -> None:
        """年次書類インデックスを削除する。"""

    @abstractmethod
    def xbrl_dir(self, doc_id: str, save_dir: str | Path | None = None) -> Path:
        """XBRL 展開ディレクトリのパスを返す。"""

    @abstractmethod
    def has_xbrl_dir(self, doc_id: str, save_dir: str | Path | None = None) -> bool:
        """XBRL 展開済みディレクトリがあるかを返す。"""

    @abstractmethod
    def touch_xbrl_dir(self, doc_id: str, save_dir: str | Path | None = None) -> None:
        """XBRL 展開ディレクトリの mtime を更新する。"""

    @abstractmethod
    def store_xbrl_zip(
        self,
        doc_id: str,
        content: bytes,
        save_dir: str | Path | None = None,
    ) -> Path:
        """XBRL zip を保存/展開し、展開ディレクトリを返す。"""
