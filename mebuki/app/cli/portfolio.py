import argparse
import json
import logging

logger = logging.getLogger(__name__)

_BROKER_CHOICES = ["SBI", "楽天", "松井", "マネックス", "auカブコム", "その他"]
_ACCOUNT_CHOICES = ["特定", "一般", "NISA"]


def _ask_broker_and_account() -> tuple[str, str]:
    """証券会社と口座種別をインタラクティブに尋ねて返す。"""
    print("証券会社:")
    for i, b in enumerate(_BROKER_CHOICES):
        print(f"  {chr(ord('a') + i)}) {b}")
    raw = input("選択 (a-f, または直接入力): ").strip()
    if len(raw) == 1 and raw.isalpha():
        idx = ord(raw.lower()) - ord("a")
        broker = _BROKER_CHOICES[idx] if 0 <= idx < len(_BROKER_CHOICES) else raw
    else:
        broker = raw

    print("口座種別:")
    for i, a in enumerate(_ACCOUNT_CHOICES):
        print(f"  {chr(ord('a') + i)}) {a}")
    raw = input("選択 (a-c): ").strip()
    if len(raw) == 1 and raw.isalpha():
        idx = ord(raw.lower()) - ord("a")
        account = _ACCOUNT_CHOICES[idx] if 0 <= idx < len(_ACCOUNT_CHOICES) else "特定"
    else:
        account = "特定"

    return broker, account


def cmd_portfolio_interactive() -> None:
    """ポートフォリオ対話モード（mebuki portfolio サブコマンドなし時に起動）"""
    while True:
        print("\nポートフォリオアクション:")
        print("  a) 保有追加")
        print("  b) 売却")
        print("  c) ポジション削除")
        print("  d) 銘柄一覧")
        print("  e) 保有明細")
        print("  q) 終了")
        raw = input("選択: ").strip().lower()

        if raw == "q":
            break

        if raw == "a":
            code = input("銘柄コード: ").strip()
            qty_str = input("数量: ").strip()
            price_str = input("取得単価 (円): ").strip()
            broker, account = _ask_broker_and_account()
            date = input("取得日 (YYYY-MM-DD, 省略可): ").strip()
            name = input("銘柄名 (省略で自動取得): ").strip()
            if code and qty_str and price_str:
                try:
                    cmd_portfolio(argparse.Namespace(
                        portfolio_subcommand="add",
                        code=code,
                        quantity=int(qty_str),
                        cost_price=float(price_str),
                        broker=broker,
                        account=account,
                        date=date or "",
                        name=name or "",
                        format="table",
                    ))
                except ValueError:
                    print("エラー: 数量・単価は数値で入力してください")
            else:
                print("エラー: 銘柄コード・数量・単価は必須です")

        elif raw == "b":
            code = input("銘柄コード: ").strip()
            qty_str = input("売却数量: ").strip()
            broker, account = _ask_broker_and_account()
            if code and qty_str:
                try:
                    cmd_portfolio(argparse.Namespace(
                        portfolio_subcommand="sell",
                        code=code,
                        quantity=int(qty_str),
                        broker=broker,
                        account=account,
                        format="table",
                    ))
                except ValueError:
                    print("エラー: 数量は整数で入力してください")
            else:
                print("エラー: 銘柄コード・数量は必須です")

        elif raw == "c":
            code = input("銘柄コード: ").strip()
            broker, account = _ask_broker_and_account()
            if code:
                cmd_portfolio(argparse.Namespace(
                    portfolio_subcommand="remove",
                    code=code,
                    broker=broker,
                    account=account,
                    format="table",
                ))
            else:
                print("エラー: 銘柄コードは必須です")

        elif raw == "d":
            cmd_portfolio(argparse.Namespace(
                portfolio_subcommand="list",
                detail=False,
                format="table",
            ))

        elif raw == "e":
            cmd_portfolio(argparse.Namespace(
                portfolio_subcommand="list",
                detail=True,
                format="table",
            ))


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
    if sub is None:
        cmd_portfolio_interactive()
        return

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
