"""
決算カレンダー補助サービス
"""

import logging
from datetime import date
from typing import Any

from mebuki.utils.cache import CacheManager
from mebuki.utils.fiscal_year import parse_date_string

logger = logging.getLogger(__name__)

_EARNINGS_CALENDAR_FQ_FILTER = {"本決算", "第２四半期"}


def _parse_calendar_date(date_str: str) -> date:
    dt = parse_date_string(date_str)
    return dt.date() if dt is not None else date(2000, 1, 1)


class EarningsCalendarService:
    """決算カレンダーのキャッシュ更新と分析結果への付与を担当するサービス"""

    def __init__(self, api_client, cache_manager: CacheManager):
        self.api_client = api_client
        self.cache_manager = cache_manager

    async def refresh_if_needed(self) -> None:
        """1日1回、決算カレンダーのストアを更新する"""
        today = date.today()
        today_str = today.isoformat()
        if self.cache_manager.get("earnings_calendar_last_fetched") == today_str:
            return

        try:
            raw = await self.api_client.get_earnings_calendar()
            valid_new = [
                e for e in raw
                if _parse_calendar_date(e.get("Date", "")) >= today
                and e.get("FQ") in _EARNINGS_CALENDAR_FQ_FILTER
            ]

            existing = self.cache_manager.get("earnings_calendar_store") or []
            existing_valid = [
                e for e in existing
                if _parse_calendar_date(e.get("Date", "")) >= today
            ]
            existing_keys = {(e["Date"], e["Code"]) for e in existing_valid}
            for entry in valid_new:
                key = (entry.get("Date"), entry.get("Code"))
                if key not in existing_keys:
                    existing_valid.append(entry)
                    existing_keys.add(key)

            self.cache_manager.set("earnings_calendar_store", existing_valid)
            self.cache_manager.set("earnings_calendar_last_fetched", today_str)
        except Exception as e:
            logger.warning(f"決算カレンダーの更新に失敗（処理を続行）: {e}")

    def attach_upcoming_earnings(self, result: dict[str, Any], code: str) -> None:
        """決算スケジュールを result に付与する（該当なければ何もしない）"""
        store = self.cache_manager.get("earnings_calendar_store") or []
        today = date.today()
        for entry in store:
            if (
                entry.get("Code", "").startswith(code[:4])
                and _parse_calendar_date(entry.get("Date", "")) >= today
            ):
                result["upcoming_earnings"] = {
                    "date": entry.get("Date"),
                    "FQ": entry.get("FQ"),
                    "SectorNm": entry.get("SectorNm"),
                    "Section": entry.get("Section"),
                }
                break
