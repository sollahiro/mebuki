"""
ポートフォリオストア（ウォッチリスト・保有銘柄の永続化）
"""
import contextlib
import json
import logging
import sys
from pathlib import Path
from typing import cast
from collections.abc import Iterator
from datetime import datetime

from mebuki.infrastructure.settings import settings_store
from mebuki.utils.portfolio_types import PortfolioItem

logger = logging.getLogger(__name__)


class PortfolioStore:
    """
    ポートフォリオストア（メモリ上でデータを保持）

    起動時に portfolio.json からロードし、明示的な save() 呼び出しで書き戻す。
    一意キー: (ticker_code, broker, account_type)
    """

    def __init__(self):
        self.portfolio_path: Path = settings_store.user_data_path / "portfolio.json"
        self._items: list[PortfolioItem] = []
        self._load_from_file()
        logger.info(f"Initialized PortfolioStore with path: {self.portfolio_path}")

    @contextlib.contextmanager
    def _file_lock(self) -> Iterator[None]:
        """portfolio.json への排他アクセスを確保するコンテキストマネージャ"""
        lock_path = self.portfolio_path.with_suffix(".json.lock")
        if sys.platform == "win32":
            import msvcrt
            lock_file = open(lock_path, "w")
            try:
                msvcrt.locking(lock_file.fileno(), msvcrt.LK_LOCK, 1)
                yield
            finally:
                msvcrt.locking(lock_file.fileno(), msvcrt.LK_UNLCK, 1)
                lock_file.close()
        else:
            import fcntl
            lock_file = open(lock_path, "w")
            try:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
                yield
            finally:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
                lock_file.close()

    def _load_from_file(self) -> None:
        """portfolio.json からデータをロードする"""
        if not self.portfolio_path.exists():
            logger.info(f"Portfolio file not found at {self.portfolio_path}. Starting empty.")
            return

        try:
            with self._file_lock():
                with open(self.portfolio_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
            self._items = cast(list[PortfolioItem], data.get("items", []))
            logger.info(f"Loaded {len(self._items)} portfolio items from {self.portfolio_path}")
        except Exception as e:
            try:
                backup_path = self.portfolio_path.with_suffix(".json.bak")
                self.portfolio_path.rename(backup_path)
                logger.warning(f"Portfolio file was corrupted. Backup created: {backup_path}")
                print(f"警告: ポートフォリオファイルが破損していました。バックアップを作成しました: {backup_path}", file=sys.stderr)
            except Exception:
                pass
            logger.error(f"Failed to load portfolio from {self.portfolio_path}: {e}")

    def find(self, ticker_code: str, broker: str, account_type: str) -> PortfolioItem | None:
        """一意キーでアイテムを検索する"""
        for item in self._items:
            if (item["ticker_code"] == ticker_code
                    and item["broker"] == broker
                    and item["account_type"] == account_type):
                return item
        return None

    def find_all_by_ticker(self, ticker_code: str) -> list[PortfolioItem]:
        """ticker_code に一致する全アイテムを返す"""
        return [item for item in self._items if item["ticker_code"] == ticker_code]

    def find_all_by_status(self, status: str) -> list[PortfolioItem]:
        """status に一致する全アイテムを返す"""
        return [item for item in self._items if item.get("status") == status]

    def upsert(self, item: PortfolioItem) -> None:
        """アイテムを追加または更新する（一意キーで照合）"""
        ticker_code = item["ticker_code"]
        broker = item["broker"]
        account_type = item["account_type"]

        for i, existing in enumerate(self._items):
            if (existing["ticker_code"] == ticker_code
                    and existing["broker"] == broker
                    and existing["account_type"] == account_type):
                self._items[i] = item
                return

        self._items.append(item)

    def remove(self, ticker_code: str, broker: str, account_type: str) -> bool:
        """一意キーに一致するアイテムを削除する。削除できた場合 True を返す。"""
        before = len(self._items)
        self._items = [
            item for item in self._items
            if not (item["ticker_code"] == ticker_code
                    and item["broker"] == broker
                    and item["account_type"] == account_type)
        ]
        return len(self._items) < before

    def save(self) -> bool:
        """現在のデータを portfolio.json に保存する"""
        try:
            with self._file_lock():
                with open(self.portfolio_path, "w", encoding="utf-8") as f:
                    json.dump({"items": self._items}, f, indent=2, ensure_ascii=False)
            return True
        except Exception as e:
            logger.error(f"Failed to save portfolio to {self.portfolio_path}: {e}")
            return False


# グローバルシングルトン
portfolio_store = PortfolioStore()
