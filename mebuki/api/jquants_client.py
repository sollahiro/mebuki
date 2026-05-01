"""
J-QUANTS API クライアント

APIキー認証とデータ取得機能を提供します。
データ取得期間を設定可能にしています。
"""

import asyncio
import logging
import ssl
from typing import Any

import aiohttp
import certifi
from ..constants.api import JQUANTS_API_BASE_URL

logger = logging.getLogger(__name__)


class JQuantsAPIClient:
    """J-QUANTS API クライアントクラス"""

    BASE_URL = "https://api.jquants.com/v2"  # V2に移行
    MAX_RETRIES = 5  # レート制限対応のため増加
    RETRY_DELAY = 2.0  # 秒（レート制限対応のため増加）
    RATE_LIMIT_WAIT = 60  # レート制限時の待機時間（秒）

    def __init__(self, api_key: str | None = None, base_url: str | None = None):
        """
        初期化

        Args:
            api_key: APIキー
            base_url: APIベースURL（Noneの場合はデフォルト値を使用）
        """
        self.api_key = api_key.strip() if api_key else api_key
        self.base_url = base_url or JQUANTS_API_BASE_URL
        self._session: aiohttp.ClientSession | None = None
        self._session_loop: asyncio.AbstractEventLoop | None = None

    def update_api_key(self, api_key: str | None) -> None:
        """APIキーを更新し、セッションを次回リクエスト時に再作成します。"""
        self.api_key = api_key.strip() if api_key else ""
        # セッションを破棄して次回アクセス時に新しいキーで再作成させる
        self._session = None
        self._session_loop = None

    async def _get_session(self) -> aiohttp.ClientSession:
        """セッションを遅延作成して返す"""
        current_loop = asyncio.get_running_loop()
        if self._session is not None and not self._session.closed and self._session_loop is not current_loop:
            await self._session.close()
            self._session = None
        if self._session is None or self._session.closed:
            headers = {}
            if self.api_key:
                headers["x-api-key"] = self.api_key
            ssl_context = ssl.create_default_context(cafile=certifi.where())
            connector = aiohttp.TCPConnector(ssl=ssl_context)
            self._session = aiohttp.ClientSession(headers=headers, connector=connector)
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
    ) -> dict[str, Any]:
        """
        APIリクエストを実行（リトライ機能付き）

        Args:
            endpoint: エンドポイントパス（例: "/fins/summary"）
            params: クエリパラメータ

        Returns:
            APIレスポンスのJSONデータ

        Raises:
            aiohttp.ClientError: リクエストエラー
            ValueError: APIキーが無効な場合
        """
        if not self.api_key:
            raise ValueError(
                "J-QUANTS APIキーが設定されていません。"
                "設定画面からAPIキーを入力してください。"
            )

        url = f"{self.base_url}{endpoint}"
        session = await self._get_session()
        timeout = aiohttp.ClientTimeout(total=30)

        for retry_count in range(self.MAX_RETRIES + 1):
            try:
                async with session.get(url, params=params, timeout=timeout) as response:
                    if response.status == 401:
                        raise ValueError("APIキーが無効です。正しいAPIキーを設定してください。")
                    elif response.status == 403:
                        text = await response.text()
                        error_msg = "認証エラー (403): APIキーが正しく設定されていない可能性があります。"
                        if "Missing Authentication Token" in text:
                            error_msg += "\nAPIキーが正しく送信されていない可能性があります。"
                        raise ValueError(error_msg)
                    elif response.status == 429:
                        if retry_count < self.MAX_RETRIES:
                            wait_time = self.RETRY_DELAY * (2 ** retry_count) + self.RATE_LIMIT_WAIT
                            print(f"⚠️  レート制限に達しました。{wait_time:.0f}秒待機してからリトライします...")
                            await asyncio.sleep(wait_time)
                            continue
                        else:
                            raise aiohttp.ClientError(
                                f"レート制限に達しました。リトライ回数上限に達しました。"
                                f"\nしばらく時間をおいてから再試行してください。"
                                f"\n（無料プランには1日あたりのリクエスト数制限があります）"
                            )
                    elif response.status == 400:
                        try:
                            error_data = await response.json()
                            msg = error_data.get("message", "")
                        except Exception:
                            msg = await response.text()
                        if "Your subscription covers" in msg:
                            raise ValueError(f"SUBSCRIPTION_OUT_OF_RANGE: {msg}")
                        raise aiohttp.ClientError(
                            f"APIリクエストエラー: {response.status} - {msg}"
                        )

                    response.raise_for_status()
                    return await response.json()

            except (aiohttp.ServerTimeoutError, aiohttp.ClientConnectorError) as e:
                if retry_count < self.MAX_RETRIES:
                    wait_time = self.RETRY_DELAY * (2 ** retry_count)
                    await asyncio.sleep(wait_time)
                    continue
                raise aiohttp.ClientError(f"ネットワークエラー: {str(e)}")

        raise aiohttp.ClientError("リトライ回数上限に達しました。")

    async def _get_all_pages(
        self,
        endpoint: str,
        params: dict[str, Any] | None = None
    ) -> list[dict[str, Any]]:
        """
        ページネーション対応のデータ取得

        Args:
            endpoint: エンドポイントパス
            params: クエリパラメータ

        Returns:
            全ページのデータを結合したリスト
        """
        all_data = []
        current_params = params.copy() if params else {}
        pagination_key = None

        while True:
            if pagination_key:
                current_params["pagination_key"] = pagination_key

            response = await self._request(endpoint, current_params)

            # レスポンス構造: {"data": [...], "pagination_key": "..."}
            if "data" in response:
                all_data.extend(response["data"])

            # ページネーションキーが存在する場合は次のページを取得
            pagination_key = response.get("pagination_key")
            if not pagination_key:
                break

        return all_data

    async def get_financial_summary(
        self,
        code: str | None = None,
        date: str | None = None,
        max_years: int | None = None,
        period_types: list[str] | None = None,
        include_fields: list[str] | None = None
    ) -> list[dict[str, Any]]:
        """
        財務情報を取得

        Args:
            code: 銘柄コード（5桁、例: "27800"）。4桁指定も可能
            date: 日付（YYYY-MM-DD または YYYYMMDD）
                  codeまたはdateのいずれかは必須
            max_years: 取得する最大年数（Noneの場合は設定から取得、API側では制限不可）
            period_types: 取得する期間タイプのリスト（例: ["FY", "2Q"]）
                         Noneの場合は全期間タイプを取得
            include_fields: 取得するフィールドのリスト（オプション、API仕様に従う）
                           Noneの場合は全フィールドを取得

        Returns:
            財務情報のリスト
        """
        if not code and not date:
            raise ValueError("codeまたはdateのいずれかを指定してください。")

        params = {}
        if code:
            params["code"] = code
        if date:
            params["date"] = date

        all_data = await self._get_all_pages("/fins/summary", params)

        if period_types:
            all_data = [record for record in all_data
                       if record.get("CurPerType") in period_types]

        return all_data

    async def get_equity_master(
        self,
        code: str | None = None,
        date: str | None = None
    ) -> list[dict[str, Any]]:
        """
        上場銘柄一覧を取得

        Args:
            code: 銘柄コード（5桁、例: "27800"）。4桁指定も可能
            date: 基準日（YYYYMMDD または YYYY-MM-DD）

        Returns:
            銘柄情報のリスト
        """
        params = {}
        if code:
            params["code"] = code
        if date:
            params["date"] = date

        return await self._get_all_pages("/equities/master", params)

    async def get_earnings_calendar(self) -> list[dict[str, Any]]:
        """
        決算発表予定日を取得

        翌営業日に決算発表が行われる銘柄の情報を返します。
        3月期・9月期決算の会社が対象です。

        Returns:
            決算発表予定日のリスト。各要素は以下のフィールドを含む:
                - Date: 決算発表予定日 (YYYY-MM-DD)
                - Code: 銘柄コード
                - CoName: 会社名
                - FY: 決算期末
                - SectorNm: 業種名
                - FQ: 決算種別
                - Section: 市場区分
        """
        return await self._get_all_pages("/equities/earnings-calendar")
