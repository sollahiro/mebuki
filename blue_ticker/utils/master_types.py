"""
銘柄マスタ関連の TypedDict 定義

CSV 読み込み後の内部表現と、検索/業種一覧の公開結果を型で表現する。
"""

from typing import TypedDict


class MasterStock(TypedDict):
    Code: str
    CoName: str
    CoNameUpper: str
    CoNameNormalized: str
    S33Nm: str
    MktNm: str
    S33: str
    S17Nm: str
    S17: str


class StockSearchResult(TypedDict):
    code: str
    name: str
    sector: str
    market: str


class SectorSummary(TypedDict):
    code: str
    name: str
    count: int
