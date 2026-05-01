"""
業種関連ユーティリティ
"""

from mebuki.services.master_data import master_data_manager
from mebuki.utils.master_types import SectorSummary, StockSearchResult


def list_sectors() -> list[SectorSummary]:
    """33業種一覧を銘柄数付きで返す"""
    return master_data_manager.list_sectors()


def search_by_sector(sector_query: str) -> list[StockSearchResult]:
    """業種名（部分一致）で銘柄一覧を返す"""
    return master_data_manager.search_by_sector(sector_query)
