"""
ポートフォリオサービス（ウォッチリスト・保有銘柄のビジネスロジック）
"""
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional

from mebuki.infrastructure.helpers import validate_stock_code
from mebuki.infrastructure.portfolio_store import portfolio_store

logger = logging.getLogger(__name__)

VALID_ACCOUNT_TYPES = ["特定", "一般", "NISA"]


def _validate_account_type(account_type: str) -> str:
    if account_type not in VALID_ACCOUNT_TYPES:
        raise ValueError(f"account_type は {VALID_ACCOUNT_TYPES} のいずれかを指定してください: {account_type!r}")
    return account_type


def _resolve_name(code: str, name: str) -> str:
    """name が空の場合、data_service から自動解決する"""
    if name:
        return name
    try:
        from mebuki.services.data_service import data_service
        info = data_service.fetch_stock_basic_info(code)
        return info.get("name", "")
    except Exception as e:
        logger.warning(f"Failed to resolve name for {code}: {e}")
        return ""


class PortfolioService:
    """ウォッチリスト・保有銘柄の管理サービス"""

    # ──────────────────────────────
    # ウォッチリスト操作
    # ──────────────────────────────

    def add_watch(self, code: str, name: str = "") -> Dict[str, Any]:
        """銘柄をウォッチリストに追加する"""
        code = validate_stock_code(code)
        existing = portfolio_store.find(code, "", "")
        if existing:
            return {"status": "already_exists", "item": existing}

        name = _resolve_name(code, name)
        item = {
            "ticker_code": code,
            "name": name,
            "status": "watch",
            "broker": "",
            "account_type": "",
            "lots": [],
            "added_at": datetime.now().isoformat(timespec="seconds"),
        }
        portfolio_store.upsert(item)
        portfolio_store.save()
        return {"status": "added", "item": item}

    def remove_watch(self, code: str) -> Dict[str, Any]:
        """ウォッチリストから銘柄を削除する"""
        code = validate_stock_code(code)
        removed = portfolio_store.remove(code, "", "")
        portfolio_store.save()
        return {"status": "removed" if removed else "not_found"}

    def get_watchlist(self) -> List[Dict[str, Any]]:
        """ウォッチリスト（status="watch"）を返す"""
        return portfolio_store.find_all_by_status("watch")

    # ──────────────────────────────
    # 保有銘柄操作
    # ──────────────────────────────

    def add_holding(
        self,
        code: str,
        quantity: int,
        cost_price: float,
        broker: str = "",
        account_type: str = "特定",
        bought_at: str = "",
        name: str = "",
    ) -> Dict[str, Any]:
        """保有銘柄（ロット）を追加する。同一ポジション既存なら lots に追記。"""
        code = validate_stock_code(code)
        _validate_account_type(account_type)

        if quantity <= 0:
            raise ValueError("quantity は正の整数を指定してください")
        if cost_price <= 0:
            raise ValueError("cost_price は正の数値を指定してください")

        name = _resolve_name(code, name)
        if not bought_at:
            bought_at = datetime.now().date().isoformat()

        lot = {
            "quantity": quantity,
            "cost_price": float(cost_price),
            "bought_at": bought_at,
        }

        existing = portfolio_store.find(code, broker, account_type)
        if existing:
            existing["lots"].append(lot)
            portfolio_store.upsert(existing)
        else:
            item = {
                "ticker_code": code,
                "name": name,
                "status": "holding",
                "broker": broker,
                "account_type": account_type,
                "lots": [lot],
                "added_at": datetime.now().isoformat(timespec="seconds"),
            }
            portfolio_store.upsert(item)

        # 同 ticker のウォッチエントリが存在すれば自動削除
        watch_entry = portfolio_store.find(code, "", "")
        if watch_entry and watch_entry.get("status") == "watch":
            portfolio_store.remove(code, "", "")

        portfolio_store.save()
        return {"status": "added", "lot": lot}

    def sell_holding(
        self,
        code: str,
        quantity: int,
        broker: str = "",
        account_type: str = "特定",
    ) -> Dict[str, Any]:
        """総平均法で売却処理を行う"""
        code = validate_stock_code(code)
        _validate_account_type(account_type)

        if quantity <= 0:
            raise ValueError("quantity は正の整数を指定してください")

        position = portfolio_store.find(code, broker, account_type)
        if not position:
            raise ValueError(f"保有ポジションが見つかりません: {code} {broker} {account_type}")

        total_qty = sum(lot["quantity"] for lot in position["lots"])
        if quantity > total_qty:
            raise ValueError(f"売却数量 ({quantity}) が保有数量 ({total_qty}) を超えています")

        # 総平均法: 売却後も平均取得単価は不変
        total_cost = sum(lot["quantity"] * lot["cost_price"] for lot in position["lots"])
        avg_cost = round(total_cost / total_qty, 2)
        remaining_qty = total_qty - quantity

        if remaining_qty > 0:
            # 残数量を加重平均単価の1ロットに集約
            earliest_date = position["lots"][0]["bought_at"]
            position["lots"] = [{
                "quantity": remaining_qty,
                "cost_price": avg_cost,
                "bought_at": earliest_date,
            }]

        if remaining_qty == 0:
            # このポジションを削除
            portfolio_store.remove(code, broker, account_type)

            # 他の口座の保有が残っているか確認
            other_holdings = [
                item for item in portfolio_store.find_all_by_ticker(code)
                if item.get("status") == "holding"
            ]
            if not other_holdings:
                # 全保有がゼロ → ウォッチエントリがなければ自動でウォッチに降格
                watch_entry = portfolio_store.find(code, "", "")
                if not watch_entry:
                    name = position.get("name", "")
                    watch_item = {
                        "ticker_code": code,
                        "name": name,
                        "status": "watch",
                        "broker": "",
                        "account_type": "",
                        "lots": [],
                        "added_at": datetime.now().isoformat(timespec="seconds"),
                    }
                    portfolio_store.upsert(watch_item)
        else:
            portfolio_store.upsert(position)

        portfolio_store.save()
        return {"status": "sold", "sold_quantity": quantity, "remaining_quantity": remaining_qty}

    def remove_holding(
        self,
        code: str,
        broker: str = "",
        account_type: str = "特定",
    ) -> Dict[str, Any]:
        """保有エントリを強制削除する（売却処理なし）"""
        code = validate_stock_code(code)
        _validate_account_type(account_type)
        removed = portfolio_store.remove(code, broker, account_type)
        portfolio_store.save()
        return {"status": "removed" if removed else "not_found"}

    def get_holdings(self) -> List[Dict[str, Any]]:
        """全保有エントリを返す"""
        return portfolio_store.find_all_by_status("holding")

    # ──────────────────────────────
    # 名寄せビュー
    # ──────────────────────────────

    def get_consolidated(self) -> List[Dict[str, Any]]:
        """ticker 単位で保有を集計した名寄せビューを返す"""
        holdings = self.get_holdings()

        # ticker_code でグループ化
        groups: Dict[str, List[Dict[str, Any]]] = {}
        for item in holdings:
            tc = item["ticker_code"]
            groups.setdefault(tc, []).append(item)

        result = []
        for tc, items in groups.items():
            total_quantity = 0
            total_cost = 0.0
            accounts = []

            for item in items:
                qty = sum(lot["quantity"] for lot in item["lots"])
                if qty == 0:
                    continue
                cost = sum(lot["quantity"] * lot["cost_price"] for lot in item["lots"])
                avg = cost / qty

                total_quantity += qty
                total_cost += cost
                accounts.append({
                    "broker": item["broker"],
                    "account_type": item["account_type"],
                    "quantity": qty,
                    "avg_cost_price": round(avg, 2),
                })

            if total_quantity == 0:
                continue

            avg_cost_price = round(total_cost / total_quantity, 2)
            name = items[0].get("name", "")

            result.append({
                "ticker_code": tc,
                "name": name,
                "total_quantity": total_quantity,
                "avg_cost_price": avg_cost_price,
                "accounts": accounts,
            })

        return result


# グローバルシングルトン
portfolio_service = PortfolioService()
