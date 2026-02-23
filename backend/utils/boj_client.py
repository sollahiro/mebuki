import time
import logging
import requests
from typing import Dict, Any, List, Optional
from mebuki.utils.cache import CacheManager
from backend.settings import settings_store

logger = logging.getLogger(__name__)

class BOJClient:
    """
    日銀API（v1/getDataCode）クライアント
    """
    BASE_URL = "https://www.stat-search.boj.or.jp/api/v1/getDataCode"
    
    def __init__(self, cache: Optional[CacheManager] = None):
        self.cache = cache
        self._last_request_time = 0
        self.interval = 1.1

    def _wait_for_interval(self):
        elapsed = time.time() - self._last_request_time
        if elapsed < self.interval:
            time.sleep(self.interval - elapsed)
        self._last_request_time = time.time()

    def _get_cache_key(self, db: str, code: str, params: Dict[str, Any]) -> str:
        param_str = "_".join(f"{k}_{v}" for k, v in sorted(params.items()))
        return f"boj_{db}_{code}_{param_str}"

    def get_time_series(self, db: str, series_code: str, start_date: Optional[str] = None, end_date: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        時系列データを取得
        
        Args:
            db: データベース名 (IR01, CO, FM08 etc.)
            series_code: 系列コード
            start_date: 開始日 (YYYYMMDD, YYYYMM)
            end_date: 終了日 (YYYYMMDD, YYYYMM)
        """
        if start_date and len(start_date) == 4 and start_date.isdigit():
            logger.info(f"Normalizing start_date from {start_date} to {start_date}01")
            start_date = f"{start_date}01"
            
        if end_date and len(end_date) == 4 and end_date.isdigit():
            logger.info(f"Normalizing end_date from {end_date} to {end_date}12")
            end_date = f"{end_date}12"

        params = {
            "db": db,
            "code": series_code,
            "format": "json"
        }
        if start_date:
            params["startDate"] = start_date
        if end_date:
            params["endDate"] = end_date

        cache_key = self._get_cache_key(db, series_code, params)
        if self.cache:
            cached_data = self.cache.get(cache_key)
            if cached_data:
                logger.info(f"Using cached BOJ data for: {series_code}")
                return cached_data

        all_series_data = []
        start_position = 1

        while True:
            params["startPosition"] = start_position
            
            response_json = self._request_with_retry(params)
            if not response_json:
                break

            # 新APIの構造: {"RESULTSET": [{"VALUES": {"SURVEY_DATES": [], "VALUES": []}}]}
            result_set = response_json.get("RESULTSET", [])
            if not result_set:
                break
                
            for series_obj in result_set:
                values_dict = series_obj.get("VALUES", {})
                dates = values_dict.get("SURVEY_DATES", [])
                values = values_dict.get("VALUES", [])
                
                # 日付と値をzipして汎用形式にする
                for d, v in zip(dates, values):
                    all_series_data.append({
                        "date": str(d),
                        "value": v
                    })

            # ページネーション (NEXTPOSITIONはトップレベルにある)
            next_position = response_json.get("NEXTPOSITION")
            if next_position and int(next_position) > start_position:
                start_position = int(next_position)
            else:
                break

        if all_series_data and self.cache:
            self.cache.set(cache_key, all_series_data)

        return all_series_data

    def _request_with_retry(self, params: Dict[str, Any], max_retries: int = 3) -> Optional[Dict[str, Any]]:
        for i in range(max_retries):
            self._wait_for_interval()
            
            try:
                headers = {
                    "Accept-Encoding": "gzip",
                    "User-Agent": "mebuki-mcp-server/1.1.0"
                }
                
                logger.info(f"Fetching BOJ data: {params.get('db')}/{params.get('code')} (Retry: {i})")
                response = requests.get(self.BASE_URL, params=params, headers=headers, timeout=30)
                
                if response.status_code != 200:
                    logger.error(f"BOJ API HTTP Error: {response.status_code}")
                    if response.status_code >= 500:
                        continue
                    return None

                data = response.json()
                
                # エラーコードの確認 (新APIでは STATUS, MESSAGEID として返ってくる場合がある)
                status = data.get("STATUS")
                if status and status != 200:
                    msg = data.get("MESSAGE", "Unknown Error")
                    msg_id = data.get("MESSAGEID")
                    
                    if msg_id in ["M181090S", "M181091S"]:
                        logger.warning(f"BOJ API Server Error ({msg_id}): {msg}. Retrying...")
                        continue
                    else:
                        logger.error(f"BOJ API Error ({msg_id}): {msg}")
                        return None
                
                return data

            except Exception as e:
                logger.error(f"BOJ API Request Exception: {e}")
                if i < max_retries - 1:
                    continue
                return None
        
        return None
