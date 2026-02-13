"""
J-QUANTS API クライアント

APIキー認証とデータ取得機能を提供します。
データ取得期間を設定可能にしています。
"""

import time
import logging
from typing import Optional, Dict, List, Any
from datetime import datetime

import requests
from ..constants.api import JQUANTS_API_BASE_URL

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
        self.api_key = api_key
        
        # ベースURLを定数または引数から取得
        self.base_url = base_url or JQUANTS_API_BASE_URL
        
        # APIキーの前後の空白を削除
        if self.api_key:
            self.api_key = self.api_key.strip()

        self.session = requests.Session()
        if self.api_key:
            self.session.headers.update({
                "x-api-key": self.api_key
            })

    def update_api_key(self, api_key: str):
        """APIキーを更新し、セッションヘッダーを更新します。"""
        self.api_key = api_key.strip() if api_key else ""
        self.session.headers.update({
            "x-api-key": self.api_key
        })

    def _request(
        self,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        retry_count: int = 0
    ) -> Dict[str, Any]:
        """
        APIリクエストを実行（リトライ機能付き）

        Args:
            endpoint: エンドポイントパス（例: "/fins/summary"）
            params: クエリパラメータ
            retry_count: 現在のリトライ回数

        Returns:
            APIレスポンスのJSONデータ

        Raises:
            requests.RequestException: リクエストエラー
            ValueError: APIキーが無効な場合
        """
        if not self.api_key:
            raise ValueError(
                "J-QUANTS APIキーが設定されていません。"
                "設定画面からAPIキーを入力してください。"
            )
        
        url = f"{self.base_url}{endpoint}"
        
        try:
            response = self.session.get(url, params=params, timeout=30)
            response.raise_for_status()
            return response.json()
        
        except requests.exceptions.HTTPError as e:
            if response.status_code == 401:
                raise ValueError("APIキーが無効です。正しいAPIキーを設定してください。")
            elif response.status_code == 403:
                error_msg = f"認証エラー (403): {response.text}"
                if "Missing Authentication Token" in response.text:
                    error_msg += "\nAPIキーが正しく送信されていない可能性があります。"
                    error_msg += f"\n使用中のベースURL: {self.base_url}"
                    error_msg += f"\nエンドポイント: {endpoint}"
                raise ValueError(error_msg)
            elif response.status_code == 429:
                # レート制限エラー
                if retry_count < self.MAX_RETRIES:
                    # レート制限時は長めに待機（指数バックオフ + 固定待機時間）
                    wait_time = self.RETRY_DELAY * (2 ** retry_count) + self.RATE_LIMIT_WAIT
                    print(f"⚠️  レート制限に達しました。{wait_time:.0f}秒待機してからリトライします...")
                    time.sleep(wait_time)
                    return self._request(endpoint, params, retry_count + 1)
                else:
                    raise requests.RequestException(
                        f"レート制限に達しました。リトライ回数上限に達しました。"
                        f"\nしばらく時間をおいてから再試行してください。"
                        f"\n（無料プランには1日あたりのリクエスト数制限があります）"
                    )
            else:
                raise requests.RequestException(
                    f"APIリクエストエラー: {response.status_code} - {response.text}"
                )
        
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
            # 一時的なネットワークエラー
            if retry_count < self.MAX_RETRIES:
                wait_time = self.RETRY_DELAY * (2 ** retry_count)
                time.sleep(wait_time)
                return self._request(endpoint, params, retry_count + 1)
            else:
                raise requests.RequestException(
                    f"ネットワークエラー: {str(e)}"
                )

    def _get_all_pages(
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
            
            response = self._request(endpoint, current_params)
            
            # レスポンス構造: {"data": [...], "pagination_key": "..."}
            if "data" in response:
                all_data.extend(response["data"])
            
            # ページネーションキーが存在する場合は次のページを取得
            pagination_key = response.get("pagination_key")
            if not pagination_key:
                break

        return all_data

    def get_financial_summary(
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

        # 全データを取得（フィルタリングは後で行う）
        all_data = self._get_all_pages("/fins/summary", params)
        
        # period_typesでフィルタリング（API側でフィルタリングできないため、取得後にフィルタリング）
        if period_types:
            all_data = [record for record in all_data 
                       if record.get("CurPerType") in period_types]
        
        # include_fieldsはAPI側で指定できないため、取得後にフィールドの存在を確認
        # 実際のフィールド名はAPIレスポンスに依存
        # CashEqのフィールド名は確認が必要（例: "CashAndCashEquivalents", "CashEq"など）
        
        # max_yearsが指定されている場合、年度データを制限
        # 注意: API側で年数制限はできないため、取得後にフィルタリング
        # 実際の年数制限は extract_annual_data と calculate_metrics で行う
        
        return all_data

    def get_daily_bars(
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

        return self._get_all_pages("/equities/bars/daily", params)

    def get_equity_master(
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

        return self._get_all_pages("/equities/master", params)

    def get_prices_at_dates(
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
        from datetime import datetime, timedelta
        normalized_dates = []
        date_objects = []
        
        for date_str in dates:
            try:
                if "-" in date_str:
                    date_obj = datetime.strptime(date_str[:10], "%Y-%m-%d")
                else:
                    date_obj = datetime.strptime(date_str[:8], "%Y%m%d")
                normalized_dates.append(date_str)
                date_objects.append((date_str, date_obj))
            except (ValueError, TypeError):
                continue
        
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
            all_bars = self.get_daily_bars(
                code=code,
                from_date=start_date,
                to_date=end_date
            )
            
            # 日付をキーとした辞書を作成
            bars_by_date = {}
            for bar in all_bars:
                bar_date = bar.get("Date", "")
                if bar_date:
                    # 日付形式を正規化
                    if len(bar_date) == 8:
                        normalized_bar_date = f"{bar_date[:4]}-{bar_date[4:6]}-{bar_date[6:8]}"
                    else:
                        normalized_bar_date = bar_date[:10] if len(bar_date) >= 10 else bar_date
                    
                    price = bar.get("AdjC") or bar.get("C")
                    if price is not None:
                        bars_by_date[normalized_bar_date] = price
                        bars_by_date[bar_date] = price  # 元の形式も保存
            
            # 各日付の株価を取得
            for date_str, date_obj in date_objects:
                # 日付を正規化
                if "-" in date_str:
                    normalized_date = date_str[:10]
                else:
                    normalized_date = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}"
                
                # まず指定日付で取得を試みる
                price = bars_by_date.get(normalized_date) or bars_by_date.get(date_str)
                
                # 指定日が休日の場合、直前の営業日を探す
                if price is None and use_nearest_trading_day:
                    # 指定日より前の日付を探す（最大10営業日前まで）
                    for i in range(1, 11):
                        check_date = date_obj - timedelta(days=i)
                        check_date_str = check_date.strftime("%Y-%m-%d")
                        price = bars_by_date.get(check_date_str)
                        if price is not None:
                            break
                
                results[date_str] = price
                results[normalized_date] = price  # 正規化形式も保存
            
        except Exception as e:
            logger.warning(f"バッチ株価取得エラー: {e}")
            # エラー時は個別取得にフォールバック
            for date_str in dates:
                results[date_str] = self.get_price_at_date(code, date_str, use_nearest_trading_day)
        
        return results
    
    def get_price_at_date(
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
        results = self.get_prices_at_dates(code, [date], use_nearest_trading_day)
        return results.get(date)

