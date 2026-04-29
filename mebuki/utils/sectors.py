"""
業種関連ユーティリティ
"""

from typing import Any
from mebuki.services.master_data import master_data_manager


def list_sectors() -> list[dict[str, Any]]:
    """33業種一覧を銘柄数付きで返す"""
    return master_data_manager.list_sectors()


def search_by_sector(sector_query: str) -> list[dict[str, Any]]:
    """業種名（部分一致）で銘柄一覧を返す"""
    return master_data_manager.search_by_sector(sector_query)
