import argparse
import logging
from mebuki.infrastructure.settings import settings_store
from mebuki.services.master_data import master_data_manager

logger = logging.getLogger(__name__)


def _ask_broker_and_account(questionary, broker_suggestions: list[str]) -> tuple[str, str]:
    """証券会社と口座種別をインタラクティブに尋ねて返す。"""
    broker = questionary.autocomplete("証券会社:", choices=broker_suggestions, default="").ask()
    account = questionary.select("口座種別:", choices=["特定", "一般", "NISA"]).ask()
    return broker or "", account or "特定"


def cmd_interactive():
    """対話型モードの実装"""
    import questionary
    from .analyze import cmd_search, cmd_analyze
    from .config import cmd_config, _DummyParser
    from .mcp import cmd_mcp
    from .portfolio import cmd_watch, cmd_portfolio

    while True:
        action = questionary.select(
            "実行するアクションを選択してください:",
            choices=[
                {"name": "銘柄検索 (search)", "value": "search"},
                {"name": "銘柄分析 (analyze)", "value": "analyze"},
                {"name": "ウォッチリスト (watch)", "value": "watch"},
                {"name": "ポートフォリオ (portfolio)", "value": "portfolio"},
                {"name": "設定管理 (config)", "value": "config"},
                {"name": "MCP連携 (mcp)", "value": "mcp"},
                {"name": "終了", "value": "exit"}
            ]
        ).ask()

        if action == "exit" or action is None:
            break

        if action == "search":
            query = questionary.text("検索キーワードを入力してください:").ask()
            if query:
                cmd_search(argparse.Namespace(query=query))

        elif action == "analyze":
            code = questionary.text("銘柄コードを入力してください (例: 7203):").ask()
            if code:
                years = questionary.text("分析年数:", default=str(settings_store.analysis_years or 5)).ask()
                import asyncio
                asyncio.run(cmd_analyze(argparse.Namespace(
                    code=code,
                    years=int(years) if years and years.isdigit() else 5,
                    format="table",
                    no_cache=False,
                    scope=None,
                )))

        elif action == "config":
            sub = questionary.select(
                "設定アクション:",
                choices=[
                    {"name": "設定を表示", "value": "show"},
                    {"name": "値を変更", "value": "set"},
                    {"name": "初期設定を開始", "value": "init"},
                    {"name": "戻る", "value": "back"}
                ]
            ).ask()

            if sub == "back" or sub is None: continue

            cfg_args = argparse.Namespace(config_subcommand=sub, key=None, value=None)
            if sub == "set":
                cfg_args.key = questionary.select("変更する項目:", choices=[
                    "jquantsApiKey", "edinetApiKey", "analysisYears", "llmProvider"
                ]).ask()
                if not cfg_args.key:
                    continue
                cfg_args.value = questionary.text(f"{cfg_args.key} の新しい値:").ask()

            cmd_config(cfg_args, _DummyParser())

        elif action == "watch":
            sub = questionary.select(
                "ウォッチリストアクション:",
                choices=[
                    {"name": "追加", "value": "add"},
                    {"name": "削除", "value": "remove"},
                    {"name": "一覧", "value": "list"},
                    {"name": "戻る", "value": "back"},
                ]
            ).ask()

            if sub == "back" or sub is None: continue

            if sub == "add":
                query = questionary.text("銘柄名またはコードで検索:").ask()
                if not query:
                    continue
                results = master_data_manager.search(query)
                if not results:
                    print(f"'{query}' に一致する銘柄は見つかりませんでした。")
                    continue
                from .ui import select_stock_from_results
                selected = select_stock_from_results(results, "ウォッチリストに追加する銘柄:", "↩  キャンセル")
                if selected:
                    cmd_watch(argparse.Namespace(watch_subcommand="add", code=selected["code"], name=selected["name"]))
            elif sub == "remove":
                code = questionary.text("銘柄コード:").ask()
                if code:
                    cmd_watch(argparse.Namespace(watch_subcommand="remove", code=code))
            elif sub == "list":
                cmd_watch(argparse.Namespace(watch_subcommand="list"))

        elif action == "portfolio":
            sub = questionary.select(
                "ポートフォリオアクション:",
                choices=[
                    {"name": "保有追加", "value": "add"},
                    {"name": "売却", "value": "sell"},
                    {"name": "ポジション削除", "value": "remove"},
                    {"name": "銘柄一覧", "value": "list"},
                    {"name": "保有明細", "value": "list_detail"},
                    {"name": "戻る", "value": "back"},
                ]
            ).ask()

            if sub == "back" or sub is None: continue

            broker_suggestions = ["SBI", "楽天", "松井", "マネックス", "auカブコム", "その他"]

            if sub == "add":
                code = questionary.text("銘柄コード:").ask()
                qty_str = questionary.text("数量:").ask()
                price_str = questionary.text("取得単価 (円):").ask()
                broker, account = _ask_broker_and_account(questionary, broker_suggestions)
                date = questionary.text("取得日 (YYYY-MM-DD, 省略可):", default="").ask()
                name = questionary.text("銘柄名 (省略で自動取得):", default="").ask()
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
                        ))
                    except ValueError:
                        print("エラー: 数量・単価は数値で入力してください")
            elif sub == "sell":
                code = questionary.text("銘柄コード:").ask()
                qty_str = questionary.text("売却数量:").ask()
                broker, account = _ask_broker_and_account(questionary, broker_suggestions)
                if code and qty_str:
                    try:
                        cmd_portfolio(argparse.Namespace(
                            portfolio_subcommand="sell",
                            code=code,
                            quantity=int(qty_str),
                            broker=broker,
                            account=account,
                        ))
                    except ValueError:
                        print("エラー: 数量は整数で入力してください")
            elif sub == "remove":
                code = questionary.text("銘柄コード:").ask()
                broker, account = _ask_broker_and_account(questionary, broker_suggestions)
                if code:
                    cmd_portfolio(argparse.Namespace(
                        portfolio_subcommand="remove",
                        code=code,
                        broker=broker,
                        account=account,
                    ))
            elif sub == "list":
                cmd_portfolio(argparse.Namespace(portfolio_subcommand="list", detail=False))
            elif sub == "list_detail":
                cmd_portfolio(argparse.Namespace(portfolio_subcommand="list", detail=True))

        elif action == "mcp":
            sub = questionary.select(
                "MCP連携アクション:",
                choices=[
                    {"name": "サーバー起動 (start)", "value": "start"},
                    {"name": "Claude Desktop への登録 (install-claude)", "value": "install-claude"},
                    {"name": "Goose への登録 (install-goose)", "value": "install-goose"},
                    {"name": "戻る", "value": "back"}
                ]
            ).ask()

            if sub == "back" or sub is None: continue

            cmd_mcp(argparse.Namespace(mcp_subcommand=sub), _DummyParser())

            if sub == "start":
                break  # start はブロッキングなのでループを抜ける
