import json
import logging

logger = logging.getLogger(__name__)


def cmd_watch(args):
    """ウォッチリスト管理コマンド"""
    from mebuki.services.portfolio_service import portfolio_service

    sub = args.watch_subcommand
    fmt = getattr(args, 'format', 'table')

    if sub == "add":
        try:
            result = portfolio_service.add_watch(args.code, name=getattr(args, "name", "") or "")
            if fmt == "json":
                print(json.dumps(result, indent=2, ensure_ascii=False))
            elif result["status"] == "already_exists":
                print(f"既にウォッチリストに存在します: {args.code}")
            else:
                item = result["item"]
                print(f"ウォッチリストに追加しました: {item['ticker_code']} {item['name']}")
        except ValueError as e:
            print(f"エラー: {e}")

    elif sub == "remove":
        try:
            result = portfolio_service.remove_watch(args.code)
            if fmt == "json":
                print(json.dumps(result, indent=2, ensure_ascii=False))
            elif result["status"] == "removed":
                print(f"ウォッチリストから削除しました: {args.code}")
            else:
                print(f"見つかりませんでした: {args.code}")
        except ValueError as e:
            print(f"エラー: {e}")

    elif sub == "list":
        watchlist = portfolio_service.get_watchlist()
        if fmt == "json":
            print(json.dumps(watchlist, indent=2, ensure_ascii=False))
            return
        if not watchlist:
            print("ウォッチリストは空です。")
            return
        print(f"\nウォッチリスト ({len(watchlist)}件):")
        print("-" * 40)
        print(f"{'コード':<8} {'銘柄名':<20} {'追加日'}")
        print("-" * 40)
        for item in watchlist:
            added = item.get("added_at", "")[:10]
            print(f"{item['ticker_code']:<8} {item['name']:<20} {added}")
        print("-" * 40)

    else:
        print("サブコマンドを指定してください: add / remove / list")


def cmd_portfolio(args):
    """ポートフォリオ管理コマンド"""
    from mebuki.services.portfolio_service import portfolio_service

    sub = args.portfolio_subcommand
    fmt = getattr(args, 'format', 'table')

    if sub == "add":
        try:
            result = portfolio_service.add_holding(
                code=args.code,
                quantity=args.quantity,
                cost_price=args.cost_price,
                broker=getattr(args, "broker", "") or "",
                account_type=getattr(args, "account", "特定") or "特定",
                bought_at=getattr(args, "date", "") or "",
                name=getattr(args, "name", "") or "",
            )
            if fmt == "json":
                print(json.dumps(result, indent=2, ensure_ascii=False))
            else:
                lot = result["lot"]
                print(f"保有を追加しました: {args.code}  {lot['quantity']}株 @{lot['cost_price']}円  ({lot['bought_at']})")
        except ValueError as e:
            print(f"エラー: {e}")

    elif sub == "sell":
        try:
            result = portfolio_service.sell_holding(
                code=args.code,
                quantity=args.quantity,
                broker=getattr(args, "broker", "") or "",
                account_type=getattr(args, "account", "特定") or "特定",
            )
            if fmt == "json":
                print(json.dumps(result, indent=2, ensure_ascii=False))
            else:
                print(f"売却処理完了: {args.code}  {result['sold_quantity']}株  残{result['remaining_quantity']}株")
        except ValueError as e:
            print(f"エラー: {e}")

    elif sub == "remove":
        try:
            result = portfolio_service.remove_holding(
                code=args.code,
                broker=getattr(args, "broker", "") or "",
                account_type=getattr(args, "account", "特定") or "特定",
            )
            if fmt == "json":
                print(json.dumps(result, indent=2, ensure_ascii=False))
            elif result["status"] == "removed":
                print(f"保有エントリを削除しました: {args.code}")
            else:
                print(f"見つかりませんでした: {args.code}")
        except ValueError as e:
            print(f"エラー: {e}")

    elif sub == "list":
        detail = getattr(args, "detail", False)
        if fmt == "json":
            data = portfolio_service.get_holdings() if detail else portfolio_service.get_consolidated()
            print(json.dumps(data, indent=2, ensure_ascii=False))
            return
        if detail:
            holdings = portfolio_service.get_holdings()
            if not holdings:
                print("保有銘柄はありません。")
                return
            print(f"\nポートフォリオ詳細 ({len(holdings)}ポジション):")
            print("-" * 70)
            for item in holdings:
                qty = sum(lot["quantity"] for lot in item["lots"])
                if qty == 0:
                    continue
                avg = sum(lot["quantity"] * lot["cost_price"] for lot in item["lots"]) / qty
                print(f"  {item['ticker_code']} {item['name']}  [{item['broker']} {item['account_type']}]")
                print(f"    保有数: {qty}株  平均取得単価: {avg:.2f}円")
                for lot in item["lots"]:
                    print(f"      ロット: {lot['quantity']}株 @{lot['cost_price']}円 ({lot['bought_at']})")
            print("-" * 70)
        else:
            consolidated = portfolio_service.get_consolidated()
            if not consolidated:
                print("保有銘柄はありません。")
                return
            print(f"\nポートフォリオ ({len(consolidated)}銘柄):")
            print("-" * 60)
            print(f"{'コード':<8} {'銘柄名':<20} {'保有数':>8} {'平均取得単価':>12}")
            print("-" * 60)
            for c in consolidated:
                print(f"{c['ticker_code']:<8} {c['name']:<20} {c['total_quantity']:>8} {c['avg_cost_price']:>12.2f}")
            print("-" * 60)

    else:
        print("サブコマンドを指定してください: add / sell / remove / list")
