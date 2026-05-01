"""
ポートフォリオ関連の TypedDict 定義

portfolio_store が永続化する JSON と、portfolio_service が返す
ビュー/操作結果の構造を型で表現する。
"""

from typing import Literal, NotRequired, TypedDict


PortfolioStatus = Literal["watch", "holding"]
PortfolioMutationStatus = Literal["added", "already_exists", "removed", "not_found", "sold"]
AccountType = Literal["特定", "一般", "NISA"]


class PortfolioLot(TypedDict):
    quantity: int
    cost_price: float
    bought_at: str


class PortfolioItem(TypedDict):
    ticker_code: str
    name: str
    status: PortfolioStatus
    broker: str
    account_type: str
    lots: list[PortfolioLot]
    added_at: str


class WatchMutationResult(TypedDict):
    status: PortfolioMutationStatus
    item: NotRequired[PortfolioItem]


class AddHoldingResult(TypedDict):
    status: PortfolioMutationStatus
    lot: PortfolioLot


class SellHoldingResult(TypedDict):
    status: PortfolioMutationStatus
    sold_quantity: int
    remaining_quantity: int


class StatusResult(TypedDict):
    status: PortfolioMutationStatus


class AccountSummary(TypedDict):
    broker: str
    account_type: str
    quantity: int
    avg_cost_price: float


class ConsolidatedHolding(TypedDict):
    ticker_code: str
    name: str
    total_quantity: int
    avg_cost_price: float
    accounts: list[AccountSummary]


class SectorAllocation(TypedDict):
    sector_name: str
    ticker_count: int
    tickers: list[str]
    total_cost: int
    ratio: float
