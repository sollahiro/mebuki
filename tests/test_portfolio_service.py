"""
PortfolioService のユニットテスト

portfolio_store グローバルをインメモリ実装で差し替えてテストする。
"""
import pytest
from unittest.mock import patch
from typing import Any


# ──────────────────────────────────────────────────────────────
# インメモリ PortfolioStore 代替（ディスク I/O なし）
# ──────────────────────────────────────────────────────────────

class _InMemoryStore:
    """PortfolioStore の公開インターフェースをインメモリで実装"""

    def __init__(self):
        self._items: list[dict[str, Any]] = []

    def find(self, ticker_code: str, broker: str, account_type: str) -> dict | None:
        for item in self._items:
            if (item["ticker_code"] == ticker_code
                    and item["broker"] == broker
                    and item["account_type"] == account_type):
                return item
        return None

    def find_all_by_ticker(self, ticker_code: str) -> list[dict]:
        return [i for i in self._items if i["ticker_code"] == ticker_code]

    def find_all_by_status(self, status: str) -> list[dict]:
        return [i for i in self._items if i.get("status") == status]

    def upsert(self, item: dict) -> None:
        code, broker, atype = item["ticker_code"], item["broker"], item["account_type"]
        for idx, existing in enumerate(self._items):
            if (existing["ticker_code"] == code
                    and existing["broker"] == broker
                    and existing["account_type"] == atype):
                self._items[idx] = item
                return
        self._items.append(item)

    def remove(self, ticker_code: str, broker: str, account_type: str) -> bool:
        before = len(self._items)
        self._items = [
            i for i in self._items
            if not (i["ticker_code"] == ticker_code
                    and i["broker"] == broker
                    and i["account_type"] == account_type)
        ]
        return len(self._items) < before

    def save(self) -> bool:
        return True


# ──────────────────────────────────────────────────────────────
# フィクスチャ
# ──────────────────────────────────────────────────────────────

@pytest.fixture
def store():
    return _InMemoryStore()


@pytest.fixture
def svc(store):
    """PortfolioService をインメモリストアで初期化"""
    with (
        patch("blue_ticker.services.portfolio_service.portfolio_store", store),
        patch("blue_ticker.services.portfolio_service._resolve_name", return_value="テスト銘柄"),
    ):
        from blue_ticker.services.portfolio_service import PortfolioService
        yield PortfolioService(), store


# ──────────────────────────────────────────────────────────────
# ウォッチリスト
# ──────────────────────────────────────────────────────────────

class TestAddWatch:
    def test_adds_new_item(self, svc):
        service, store = svc
        result = service.add_watch("7203")
        assert result["status"] == "added"
        assert store.find("72030", "", "") is not None

    def test_returns_already_exists(self, svc):
        service, store = svc
        service.add_watch("7203")
        result = service.add_watch("7203")
        assert result["status"] == "already_exists"

    def test_normalizes_4digit_to_5digit(self, svc):
        service, store = svc
        service.add_watch("7203")
        assert store.find("72030", "", "") is not None

    def test_invalid_code_raises(self, svc):
        service, _ = svc
        with pytest.raises(ValueError):
            service.add_watch("AB")


class TestRemoveWatch:
    def test_removes_existing(self, svc):
        service, _ = svc
        service.add_watch("7203")
        result = service.remove_watch("7203")
        assert result["status"] == "removed"

    def test_not_found(self, svc):
        service, _ = svc
        result = service.remove_watch("9999")
        assert result["status"] == "not_found"


class TestGetWatchlist:
    def test_returns_only_watch_status(self, svc):
        service, store = svc
        service.add_watch("7203")
        # 保有銘柄を直接ストアに挿入
        store.upsert({
            "ticker_code": "60980",
            "name": "NTT",
            "status": "holding",
            "broker": "",
            "account_type": "特定",
            "lots": [],
            "added_at": "2024-01-01T00:00:00",
        })
        watchlist = service.get_watchlist()
        assert len(watchlist) == 1
        assert watchlist[0]["ticker_code"] == "72030"


# ──────────────────────────────────────────────────────────────
# 保有銘柄
# ──────────────────────────────────────────────────────────────

class TestAddHolding:
    def test_adds_new_position(self, svc):
        service, store = svc
        result = service.add_holding("7203", quantity=100, cost_price=2500.0)
        assert result["status"] == "added"
        pos = store.find("72030", "", "特定")
        assert pos is not None
        assert len(pos["lots"]) == 1
        assert pos["lots"][0]["quantity"] == 100

    def test_appends_lot_to_existing_position(self, svc):
        service, store = svc
        service.add_holding("7203", quantity=100, cost_price=2500.0)
        service.add_holding("7203", quantity=50, cost_price=2600.0)
        pos = store.find("72030", "", "特定")
        assert len(pos["lots"]) == 2
        assert sum(lot["quantity"] for lot in pos["lots"]) == 150

    def test_auto_removes_watch_entry(self, svc):
        service, store = svc
        service.add_watch("7203")
        service.add_holding("7203", quantity=100, cost_price=2500.0)
        assert store.find("72030", "", "") is None

    def test_invalid_quantity_raises(self, svc):
        service, _ = svc
        with pytest.raises(ValueError, match="quantity"):
            service.add_holding("7203", quantity=0, cost_price=2500.0)

    def test_invalid_cost_price_raises(self, svc):
        service, _ = svc
        with pytest.raises(ValueError, match="cost_price"):
            service.add_holding("7203", quantity=100, cost_price=0.0)

    def test_invalid_account_type_raises(self, svc):
        service, _ = svc
        with pytest.raises(ValueError, match="account_type"):
            service.add_holding("7203", quantity=100, cost_price=2500.0, account_type="不明口座")


class TestSellHolding:
    def _setup_position(self, service, code="7203", qty=200, price=2500.0):
        service.add_holding(code, quantity=qty, cost_price=price)

    def test_partial_sell_consolidates_to_single_lot(self, svc):
        service, store = svc
        service.add_holding("7203", quantity=100, cost_price=2000.0)
        service.add_holding("7203", quantity=100, cost_price=3000.0)
        result = service.sell_holding("7203", quantity=50)
        assert result["status"] == "sold"
        assert result["remaining_quantity"] == 150
        pos = store.find("72030", "", "特定")
        assert len(pos["lots"]) == 1
        assert pos["lots"][0]["quantity"] == 150
        assert pos["lots"][0]["cost_price"] == pytest.approx(2500.0)

    def test_full_sell_downgrades_to_watch(self, svc):
        service, store = svc
        self._setup_position(service, qty=100)
        result = service.sell_holding("7203", quantity=100)
        assert result["status"] == "sold"
        assert result["remaining_quantity"] == 0
        # ポジション削除
        assert store.find("72030", "", "特定") is None
        # ウォッチに自動降格
        assert store.find("72030", "", "") is not None

    def test_oversell_raises(self, svc):
        service, _ = svc
        self._setup_position(service, qty=100)
        with pytest.raises(ValueError, match="超えています"):
            service.sell_holding("7203", quantity=200)

    def test_position_not_found_raises(self, svc):
        service, _ = svc
        with pytest.raises(ValueError, match="見つかりません"):
            service.sell_holding("9999", quantity=100)

    def test_invalid_quantity_raises(self, svc):
        service, _ = svc
        with pytest.raises(ValueError, match="quantity"):
            service.sell_holding("7203", quantity=0)


class TestRemoveHolding:
    def test_removes_existing(self, svc):
        service, _ = svc
        service.add_holding("7203", quantity=100, cost_price=2500.0)
        result = service.remove_holding("7203")
        assert result["status"] == "removed"

    def test_not_found(self, svc):
        service, _ = svc
        result = service.remove_holding("9999")
        assert result["status"] == "not_found"


# ──────────────────────────────────────────────────────────────
# 名寄せビュー
# ──────────────────────────────────────────────────────────────

class TestGetConsolidated:
    def test_single_position(self, svc):
        service, _ = svc
        service.add_holding("7203", quantity=100, cost_price=2500.0)
        rows = service.get_consolidated()
        assert len(rows) == 1
        assert rows[0]["ticker_code"] == "72030"
        assert rows[0]["total_quantity"] == 100
        assert rows[0]["avg_cost_price"] == pytest.approx(2500.0)

    def test_multiple_lots_weighted_average(self, svc):
        service, _ = svc
        service.add_holding("7203", quantity=100, cost_price=2000.0)
        service.add_holding("7203", quantity=100, cost_price=3000.0)
        rows = service.get_consolidated()
        assert rows[0]["total_quantity"] == 200
        assert rows[0]["avg_cost_price"] == pytest.approx(2500.0)

    def test_multiple_tickers(self, svc):
        service, _ = svc
        service.add_holding("7203", quantity=100, cost_price=2500.0)
        service.add_holding("6758", quantity=50, cost_price=10000.0)
        rows = service.get_consolidated()
        codes = {r["ticker_code"] for r in rows}
        assert "72030" in codes
        assert "67580" in codes

    def test_empty_holdings(self, svc):
        service, _ = svc
        assert service.get_consolidated() == []
