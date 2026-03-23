"""
J-QUANTS API クライアント

APIキー認証とデータ取得機能を提供します。
データ取得期間を設定可能にしています。
"""

import asyncio
import logging
from typing import Optional, Dict, List, Any
from datetime import datetime, timedelta

import aiohttp
from ..constants.api import JQUANTS_API_BASE_URL
from mebuki.constants.formats import DATE_LEN_COMPACT
from mebuki.utils.fiscal_year import normalize_date_format, parse_date_string

logger = logging.getLogger(__name__)


class JQuantsAPIClient:
    """J-QUANTS API クライアントクラス"""

    BASE_URL = "https://api.jquants.com/v2"  # V2に移行
    MAX_RETRIES = 5  # レート制限対応のため増加
    RETRY_DELAY = 2.0  # 秒（レート制限対応のため増加）
    RATE_LIMIT_WAIT = 60  # レート制限時の待機時間（秒）

    def __init__(self, api_key: Optional[str] = None, base_url: Optional[str] = None):
        """
        初期化

        Args:
            api_key: APIキー
            base_url: APIベースURL（Noneの場合はデフォルト値を使用）
        """
        self.api_key = api_key.strip() if api_key else api_key
        self.base_url = base_url or JQUANTS_API_BASE_URL
        self._session: Optional[aiohttp.ClientSession] = None

    def update_api_key(self, api_key: str) -> None:
        """APIキーを更新し、セッションを次回リクエスト時に再作成します。"""
        self.api_key = api_key.strip() if api_key else ""
        # セッションを破棄して次回アクセス時に新しいキーで再作成させる
        self._session = None

    async def _get_session(self) -> aiohttp.ClientSession:
        """セッションを遅延作成して返す"""
        if self._session is None or self._session.closed:
            headers = {}
            if self.api_key:
                headers["x-api-key"] = self.api_key
            self._session = aiohttp.ClientSession(headers=headers)
        return self._session

    async def _request(
        self,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
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
        params: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
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
        code: Optional[str] = None,
        date: Optional[str] = None,
        max_years: Optional[int] = None,
        period_types: Optional[List[str]] = None,
        include_fields: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
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

    async def get_daily_bars(
        self,
        code: Optional[str] = None,
        date: Optional[str] = None,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        株価四本値データを取得

        Args:
            code: 銘柄コード（5桁、例: "27800"）。4桁指定も可能
            date: 日付（YYYYMMDD または YYYY-MM-DD）
            from_date: 期間指定の開始日
            to_date: 期間指定の終了日
            codeまたはdateのいずれかは必須

        Returns:
            株価データのリスト
        """
        if not code and not date:
            raise ValueError("codeまたはdateのいずれかを指定してください。")

        params = {}
        if code:
            params["code"] = code
        if date:
            params["date"] = date
        if from_date:
            params["from"] = from_date
        if to_date:
            params["to"] = to_date

        return await self._get_all_pages("/equities/bars/daily", params)

    async def get_equity_master(
        self,
        code: Optional[str] = None,
        date: Optional[str] = None
    ) -> List[Dict[str, Any]]:
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

    async def get_earnings_calendar(self) -> List[Dict[str, Any]]:
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

    async def get_prices_at_dates(
        self,
        code: str,
        dates: List[str],
        use_nearest_trading_day: bool = True
    ) -> Dict[str, Optional[float]]:
        """
        複数の日付の終値を一括取得（バッチ処理）

        指定日が休日の場合は、直前の営業日の終値を取得します。

        Args:
            code: 銘柄コード（5桁、例: "27800"）
            dates: 日付のリスト（YYYYMMDD または YYYY-MM-DD）
            use_nearest_trading_day: 指定日が休日の場合は直前の営業日を使用（デフォルト: True）

        Returns:
            日付をキーとした終値の辞書（AdjC）。データが存在しない場合はNone
        """
        if not dates:
            return {}

        results = {}

        # 日付を正規化して範囲を計算
        date_objects = []

        for date_str in dates:
            date_obj = parse_date_string(date_str)
            if date_obj is None:
                continue
            date_objects.append((date_str, date_obj))

        if not date_objects:
            return {}

        # 最小日付と最大日付を計算（バッチ取得用）
        min_date = min(dt for _, dt in date_objects)
        max_date = max(dt for _, dt in date_objects)

        # バッファを追加（休日対応のため前後10日）
        start_date = (min_date - timedelta(days=10)).strftime("%Y-%m-%d")
        end_date = (max_date + timedelta(days=10)).strftime("%Y-%m-%d")

        # 一括で株価データを取得
        try:
            all_bars = await self.get_daily_bars(
                code=code,
                from_date=start_date,
                to_date=end_date
            )

            bars_by_date = self._build_bars_by_date(all_bars)

            for date_str, date_obj in date_objects:
                normalized_date = normalize_date_format(date_str) or date_str[:10]
                price = bars_by_date.get(normalized_date) or bars_by_date.get(date_str)

                if price is None and use_nearest_trading_day:
                    for i in range(1, 11):
                        check_date = date_obj - timedelta(days=i)
                        check_date_str = check_date.strftime("%Y-%m-%d")
                        price = bars_by_date.get(check_date_str)
                        if price is not None:
                            break

                results[date_str] = price
                results[normalized_date] = price

        except Exception as e:
            error_str = str(e)
            if "SUBSCRIPTION_OUT_OF_RANGE" in error_str:
                import re
                match = re.search(r"(\d{4}-\d{2}-\d{2})", error_str)
                if match:
                    allowed_start = match.group(1)
                    logger.info(f"サブスク下限を検知: {allowed_start}。範囲を調整して再試行します。")

                    new_start_dt = datetime.strptime(allowed_start, "%Y-%m-%d")
                    if max_date < new_start_dt:
                        logger.warning(f"全リクエスト対象がサブスク範囲外です: {code}")
                        return {d: None for d in dates}

                    try:
                        all_bars = await self.get_daily_bars(
                            code=code,
                            from_date=allowed_start,
                            to_date=end_date
                        )
                        bars_by_date = self._build_bars_by_date(all_bars)

                        for date_str, date_obj in date_objects:
                            normalized_date = normalize_date_format(date_str) or date_str[:10]
                            price = bars_by_date.get(normalized_date) or bars_by_date.get(date_str)
                            if price is None and use_nearest_trading_day:
                                for i in range(1, 11):
                                    check_date = date_obj - timedelta(days=i)
                                    if check_date < new_start_dt:
                                        break
                                    check_date_str = check_date.strftime("%Y-%m-%d")
                                    price = bars_by_date.get(check_date_str)
                                    if price is not None:
                                        break
                            results[date_str] = price
                            results[normalized_date] = price
                        return results
                    except Exception as retry_e:
                        logger.error(f"範囲調整後のリトライに失敗: {retry_e}")

            logger.warning(f"バッチ株価取得エラー: {e}")
            # エラー時は個別取得にフォールバック
            for date_str in dates:
                results[date_str] = await self.get_price_at_date(code, date_str, use_nearest_trading_day)

        return results

    def _build_bars_by_date(self, all_bars: List[Dict[str, Any]]) -> Dict[str, Any]:
        """株価データを日付→価格の辞書に変換"""
        bars_by_date = {}
        for bar in all_bars:
            bar_date = bar.get("Date", "")
            if bar_date:
                normalized_bar_date = normalize_date_format(bar_date) or (
                    bar_date[:10] if len(bar_date) >= 10 else bar_date
                )
                price = bar.get("AdjC") or bar.get("C")
                if price is not None:
                    bars_by_date[normalized_bar_date] = price
                    bars_by_date[bar_date] = price
        return bars_by_date

    async def get_price_at_date(
        self,
        code: str,
        date: str,
        use_nearest_trading_day: bool = True
    ) -> Optional[float]:
        """
        指定日付の終値を取得（年度末株価取得用）

        指定日が休日の場合は、直前の営業日の終値を取得します。

        Args:
            code: 銘柄コード（5桁、例: "27800"）
            date: 日付（YYYYMMDD または YYYY-MM-DD）
            use_nearest_trading_day: 指定日が休日の場合は直前の営業日を使用（デフォルト: True）

        Returns:
            終値（AdjC）。データが存在しない場合はNone
        """
        # バッチ処理を使用
        results = await self.get_prices_at_dates(code, [date], use_nearest_trading_day)
        return results.get(date)
