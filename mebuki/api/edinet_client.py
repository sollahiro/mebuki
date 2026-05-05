import asyncio
import logging
import ssl
from pathlib import Path
from typing import Any

import aiohttp
import certifi

from ..constants.api import EDINET_API_BASE_URL
from .edinet_cache_store import EdinetCacheStore

logger = logging.getLogger(__name__)

class EdinetAPIClient:
    """EDINET API v2 クライアント"""

    def __init__(
        self,
        api_key: str | None = None,
        cache_dir: str | None = None,
        cache_store: EdinetCacheStore | None = None,
    ):
        self.api_key = api_key
        self.base_url = EDINET_API_BASE_URL
        self.cache_store = cache_store or EdinetCacheStore(cache_dir or Path("tmp_cache") / "edinet")
        self.cache_dir = self.cache_store.cache_dir

        self._session: aiohttp.ClientSession | None = None
        self._session_loop: asyncio.AbstractEventLoop | None = None
        self._download_locks: dict[str, asyncio.Lock] = {}
        self._date_fetch_semaphore = asyncio.Semaphore(10)

    def update_api_key(self, api_key: str | None) -> None:
        """APIキーを更新します。"""
        self.api_key = api_key.strip() if api_key else ""
        self._session = None
        self._session_loop = None

    async def _get_session(self) -> aiohttp.ClientSession:
        """セッションを遅延作成して返す"""
        current_loop = asyncio.get_running_loop()
        if self._session is not None and not self._session.closed and self._session_loop is not current_loop:
            await self._session.close()
            self._session = None
        if self._session is None or self._session.closed:
            ssl_context = ssl.create_default_context(cafile=certifi.where())
            connector = aiohttp.TCPConnector(ssl=ssl_context)
            self._session = aiohttp.ClientSession(connector=connector)
            self._session_loop = current_loop
        return self._session

    async def close(self) -> None:
        """セッションを明示的にクローズする"""
        if self._session is not None and not self._session.closed:
            await self._session.close()
        self._session = None
        self._session_loop = None

    async def _request(
        self,
        endpoint: str,
        params: dict[str, Any] | None = None,
        max_retries: int = 3,
    ) -> dict[str, Any]:
        """リトライ機能付きAPIリクエスト実行（JSON応答）"""
        if not self.api_key:
            raise ValueError("EDINET_API_KEY is not set")

        url = f"{self.base_url}{endpoint}"
        params = dict(params or {})
        params["Subscription-Key"] = self.api_key

        last_exception: BaseException | None = None
        session = await self._get_session()
        timeout = aiohttp.ClientTimeout(total=30)

        for attempt in range(max_retries):
            try:
                if attempt > 0:
                    wait_time = 2 ** attempt
                    logger.warning(f"⚠️ [EDINET API] Retry attempt {attempt+1}/{max_retries} after {wait_time}s...")
                    await asyncio.sleep(wait_time)

                async with session.get(url, params=params, timeout=timeout) as response:
                    # JSONボディのビジネスエラーをステータスコードより先にチェック
                    try:
                        data = await response.json(content_type=None)
                        status_code_in_body = data.get("statusCode")
                        if status_code_in_body and status_code_in_body != 200:
                            message = data.get("message", "Unknown error")
                            logger.error(f"❌ [EDINET API] Business logic error: {status_code_in_body} - {message}")
                            if status_code_in_body == 401:
                                raise ValueError(f"EDINET APIキーが無効です: {message}")
                            raise aiohttp.ClientResponseError(
                                response.request_info,
                                response.history,
                                status=status_code_in_body,
                                message=f"EDINET API error: {status_code_in_body} - {message}",
                            )
                        response.raise_for_status()
                        return data
                    except ValueError as e:
                        if "EDINET APIキーが無効です" in str(e):
                            raise
                        # JSON以外のレスポンス
                        response.raise_for_status()
                        return {}

            except (aiohttp.ClientResponseError, aiohttp.ClientError, ValueError) as e:
                last_exception = e
                if isinstance(e, ValueError) and "EDINET APIキーが無効です" in str(e):
                    raise

                status_code = getattr(e, "status", None)
                if status_code in [429, 500, 502, 503, 504] or isinstance(e, aiohttp.ClientConnectorError):
                    continue
                else:
                    logger.error(f"❌ [EDINET API] Non-retryable error: {e}")
                    raise

        logger.error(f"❌ [EDINET API] All {max_retries} attempts failed. Last error: {last_exception}")
        if last_exception is not None:
            raise last_exception
        raise aiohttp.ClientError("EDINET APIリトライ回数上限に達しました。")

    async def _request_binary(
        self,
        endpoint: str,
        params: dict[str, Any] | None = None,
        max_retries: int = 3,
    ) -> bytes:
        """リトライ機能付きAPIリクエスト実行（バイナリ応答）"""
        if not self.api_key:
            raise ValueError("EDINET_API_KEY is not set")

        url = f"{self.base_url}{endpoint}"
        params = dict(params or {})
        params["Subscription-Key"] = self.api_key

        last_exception: BaseException | None = None
        session = await self._get_session()
        timeout = aiohttp.ClientTimeout(total=120)

        for attempt in range(max_retries):
            try:
                if attempt > 0:
                    wait_time = 2 ** attempt
                    logger.warning(f"⚠️ [EDINET API] Retry attempt {attempt+1}/{max_retries} after {wait_time}s...")
                    await asyncio.sleep(wait_time)

                async with session.get(url, params=params, timeout=timeout) as response:
                    response.raise_for_status()
                    return await response.read()

            except (aiohttp.ClientResponseError, aiohttp.ClientError) as e:
                last_exception = e
                status_code = getattr(e, "status", None)
                if status_code in [429, 500, 502, 503, 504] or isinstance(e, aiohttp.ClientConnectorError):
                    continue
                raise

        if last_exception is not None:
            raise last_exception
        raise aiohttp.ClientError("EDINET APIバイナリ取得のリトライ回数上限に達しました。")

    def _get_search_cache_key(self, date_str: str) -> str:
        """検索用キャッシュキー生成（日付ベース）"""
        return self.cache_store.search_cache_key(date_str)

    def _load_search_cache(self, filename: str) -> list[dict[str, Any]] | None:
        """キャッシュから検索結果をロード"""
        return self.cache_store.load_search_cache(filename)

    def _save_search_cache(self, filename: str, data: list[dict[str, Any]]) -> None:
        """検索結果をキャッシュに保存"""
        self.cache_store.save_search_cache(filename, data)

    async def _get_documents_for_date(self, date_str: str) -> list[dict[str, Any]]:
        """特定の日付のドキュメント一覧を取得（キャッシュ対応）"""
        cache_key = self._get_search_cache_key(date_str)
        documents = self._load_search_cache(cache_key)
        if documents is not None:
            return documents

        async with self._date_fetch_semaphore:
            documents = self._load_search_cache(cache_key)
            if documents is not None:
                return documents
            try:
                data = await self._request("/documents.json", {"date": date_str, "type": 2})
                documents = data.get("results", [])
                self._save_search_cache(cache_key, documents)
                return documents
            except Exception:
                return []

    async def download_document(self, doc_id: str, doc_type: int = 1, save_dir: Path | None = None) -> Path | None:
        """書類をダウンロード（1=XBRLのみ維持。旧2=PDFは廃止）"""
        if doc_type != 1:
            logger.warning(f"⚠️ [EDINET] ID={doc_id} の PDF ダウンロードは廃止されました。")
            return None

        if save_dir is None:
            save_dir = self.cache_dir
        save_dir = Path(save_dir)
        save_dir.mkdir(parents=True, exist_ok=True)

        dest = self.cache_store.xbrl_dir(doc_id, save_dir)

        if doc_id not in self._download_locks:
            self._download_locks[doc_id] = asyncio.Lock()
        async with self._download_locks[doc_id]:
            if self.cache_store.has_xbrl_dir(doc_id, save_dir):
                self.cache_store.touch_xbrl_dir(doc_id, save_dir)
                return dest

            if not self.api_key:
                return None

            try:
                content = await self._request_binary(f"/documents/{doc_id}", {"type": 1})
                return self.cache_store.store_xbrl_zip(doc_id, content, save_dir)
            except Exception as e:
                logger.error(f"❌ [EDINET] XBRL Download error {doc_id}: {e}")
                return None
