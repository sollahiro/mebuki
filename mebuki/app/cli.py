import argparse
import sys
import json
import yaml
import logging
from typing import List, Dict, Any, Optional
from mebuki import __version__
from mebuki.infrastructure.settings import settings_store
from mebuki.infrastructure.helpers import validate_stock_code
from mebuki.services.master_data import master_data_manager

logger = logging.getLogger(__name__)

def print_banner():
    """バナーを水平グラデーション表示 (ブランドカラー: Green -> Cyan)"""
    banner_text = r"""
  ███╗   ███╗███████╗██████╗ ██╗   ██╗██╗  ██╗██╗
  ████╗ ████║██╔════╝██╔══██╗██║   ██║██║ ██╔╝██║
  ██╔████╔██║█████╗  ██████╔╝██║   ██║█████╔╝ ██║
  ██║╚██╔╝██║██╔══╝  ██╔══██╗██║   ██║██╔═██╗ ██║
  ██║ ╚═╝ ██║███████╗██████╔╝╚██████╔╝██║  ██╗██║ 🌱
  ╚═╝     ╚═╝╚══════╝╚═════╝  ╚═════╝ ╚═╝  ╚═╝╚═╝
"""
    # ブランドカラーの定義 (RGB)
    start_color = (53, 200, 95)  # #35C85F (Green)
    end_color = (27, 190, 208)    # #1BBED0 (Cyan)
    
    lines = banner_text.strip("\n").split("\n")
    if not lines: return

    print("")
    for line in lines:
        length = len(line)
        colored_line = ""
        for i, char in enumerate(line):
            # 水平方向の補間率
            ratio = i / max(1, length - 1)
            r = int(start_color[0] + (end_color[0] - start_color[0]) * ratio)
            g = int(start_color[1] + (end_color[1] - start_color[1]) * ratio)
            b = int(start_color[2] + (end_color[2] - start_color[2]) * ratio)
            # TrueColor (24-bit) ANSIエスケープコード
            colored_line += f"\033[38;2;{r};{g};{b}m{char}"
        print(colored_line + "\033[0m")
    
    print("\033[3;38;5;250m    Sprouting Investment Insights\033[0m\n")

def cmd_search(args):
    """銘柄検索コマンド"""
    if not args.query:
        print("検索クエリを指定してください。")
        return
    
    results = master_data_manager.search(args.query)
    if not results:
        print(f"'{args.query}' に一致する銘柄は見つかりませんでした。")
        return
    
    print(f"\n'{args.query}' の検索結果 ({len(results)}件):")
    print("-" * 60)
    print(f"{'コード':<8} {'銘柄名':<20} {'市場':<15} {'業種'}")
    print("-" * 60)
    for item in results:
        print(f"{item['code']:<8} {item['name']:<20} {item['market']:<15} {item['sector']}")
    print("-" * 60)

    import questionary
    choices = [
        {"name": f"{item['code']}  {item['name']}  ({item['market']})", "value": item['code']}
        for item in results
    ]
    choices.append({"name": "↩  分析しない / 戻る", "value": None})

    selected = questionary.select(
        "分析する銘柄を選択してください:",
        choices=choices,
    ).ask()

    if selected:
        import asyncio
        asyncio.run(cmd_analyze(argparse.Namespace(
            code=selected,
            years=None,
            format="table",
            no_cache=False,
            scope=None,
        )))

async def cmd_analyze(args):
    """銘柄分析コマンド"""
    from mebuki.services.data_service import data_service

    code = validate_stock_code(args.code)

    # --scope が指定された場合はスコープ別取得
    if getattr(args, "scope", None):
        try:
            result = await data_service.get_financial_data(code, scope=args.scope, use_cache=not args.no_cache)
            if args.format == "json":
                print(json.dumps(result, indent=2, ensure_ascii=False))
            else:
                print(json.dumps(result, indent=2, ensure_ascii=False))
        except Exception as e:
            print(f"エラー: {e}")
            logger.exception(e)
        return

    # 銘柄情報の確認
    info = data_service.fetch_stock_basic_info(code)
    if not info.get("name"):
        print(f"エラー: 銘柄コード {code} が見つかりません。")
        return
    
    # 分析年数の決定
    years_to_analyze = args.years or settings_store.analysis_years or 5
    
    print(f"\n分析中: {code} {info['name']} ({info['market_name']}) ...")
    print(f"分析対象期間: 直近 {years_to_analyze} 年分")
    
    try:
        # data_service を使って生の財務データを取得
        result = await data_service.get_raw_analysis_data(
            code, use_cache=not args.no_cache, analysis_years=years_to_analyze,
            include_2q=getattr(args, 'include_2q', False)
        )
        
        if not result or not result.get("metrics"):
            print("エラー: 財務データの取得に失敗しました。APIキーが正しく設定されているか確認してください。")
            return
            
        if args.format == "json":
            print(json.dumps(result, indent=2, ensure_ascii=False))
            return
            
        # 指標データの取得
        metrics = result.get("metrics", {})
        years_data = metrics.get("years", [])
        if not years_data:
            print("エラー: 指標データが見つかりませんでした。")
            return
            
        # 横並びのテーブル表示
        print(f"\n[主要財務指標の推移]")

        # ヘッダー作成（年度）
        headers = ["項目 \\ 年度"]
        periods = []
        for y_data in reversed(years_data): # 古い順に表示
            fy_end = y_data.get("fy_end", "不明")
            if len(fy_end) == 8:
                period_str = f"{fy_end[2:4]}/{fy_end[4:6]}"
            else:
                period_str = fy_end[2:7] # YY-MM
            per_type = y_data.get("RawData", {}).get("CurPerType", "FY")
            if per_type == "2Q":
                period_str += "(2Q)"
            headers.append(period_str)
            periods.append(y_data)

        row_format = "{:<16}" + " {:>10}" * len(periods)
        print("-" * (16 + 11 * len(periods)))
        print(row_format.format(*headers))
        print("-" * (16 + 11 * len(periods)))

        # 各指標の行を作成
        def get_op_margin(c):
            return c.get("OperatingMargin") or (c.get("OP") / c.get("Sales") * 100 if c.get("OP") and c.get("Sales") else None)

        metrics_to_show = [
            ("売上高 (百万)", lambda c: c.get("Sales")),
            ("営業利益 (百万)", lambda c: c.get("OP")),
            ("営業利益率 (%)", get_op_margin),
            ("ROE (%)", lambda c: c.get("ROE")),
            ("簡易ROIC (%)", lambda c: c.get("SimpleROIC")),
            ("営業CF (百万)", lambda c: c.get("CFO")),
            ("投資CF (百万)", lambda c: c.get("CFI")),
            ("フリーCF (百万)", lambda c: c.get("CFC")),
            ("配当性向 (%)", lambda c: c.get("PayoutRatio")),
            ("PER (倍)", lambda c: c.get("PER")),
            ("PBR (倍)", lambda c: c.get("PBR")),
            ("年度末株価 (円)", lambda c: c.get("Price")),
        ]

        for label, func in metrics_to_show:
            row = [label]
            for p in periods:
                val = func(p.get("CalculatedData", {}))
                row.append(f"{val:>10.2f}" if val is not None else f"{'-':>10}")
            print(row_format.format(*row))

        print("-" * (16 + 11 * len(periods)))

        upcoming = result.get("upcoming_earnings")
        if upcoming:
            print(f"\n次回決算予定: {upcoming.get('date', '不明')}  {upcoming.get('FQ', '')}")

        print("\n詳細な分析や定性情報は MCP版（Claude等）をご利用ください。")

        # ウォッチリスト追加の確認（対話端末のみ）
        if args.format == "table" and sys.stdin.isatty():
            import questionary
            from mebuki.services.portfolio_service import portfolio_service
            from mebuki.infrastructure.portfolio_store import portfolio_store as _ps
            already = _ps.find(validate_stock_code(code), "", "")
            if not already or already.get("status") != "watch":
                add_watch = await questionary.confirm(
                    f"{code} {info['name']} をウォッチリストに追加しますか？",
                    default=False,
                ).ask_async()
                if add_watch:
                    portfolio_service.add_watch(code, name=info.get("name", ""))
                    print(f"ウォッチリストに追加しました: {code} {info['name']}")

    except Exception as e:
        print(f"エラー: 分析中に例外が発生しました: {e}")
        logger.exception(e)

async def cmd_price(args):
    """株価データ取得コマンド"""
    from mebuki.services.data_service import data_service

    code = validate_stock_code(args.code)
    try:
        data = await data_service.get_price_data(code, days=args.days)
        if not data:
            print(f"株価データが見つかりませんでした: {code}")
            return
        if args.format == "json":
            print(json.dumps(data, indent=2, ensure_ascii=False))
        else:
            print(f"\n[株価データ] {code}  直近{args.days}日")
            print("-" * 70)
            print(f"{'日付':<12} {'始値':>8} {'高値':>8} {'安値':>8} {'終値':>8} {'出来高':>12}")
            print("-" * 70)
            for row in data:
                o = row.get('AdjO') or row.get('O', '-')
                h = row.get('AdjH') or row.get('H', '-')
                l = row.get('AdjL') or row.get('L', '-')
                c = row.get('AdjC') or row.get('C', '-')
                v = row.get('AdjVo') or row.get('Vo', '-')
                print(
                    f"{row.get('Date',''):<12}"
                    f" {o:>8}"
                    f" {h:>8}"
                    f" {l:>8}"
                    f" {c:>8}"
                    f" {v:>12}"
                )
            print("-" * 70)
    except Exception as e:
        print(f"エラー: {e}")
        logger.exception(e)


async def cmd_filings(args):
    """EDINET書類一覧コマンド"""
    from mebuki.services.data_service import data_service

    code = validate_stock_code(args.code)
    try:
        docs = await data_service.search_filings(
            code,
            max_years=10,
            doc_types=["120", "130", "140", "150", "160", "170"],
            max_documents=10,
        )
        if not docs:
            print(f"書類が見つかりませんでした: {code}")
            return
        if args.format == "json":
            print(json.dumps(docs, indent=2, ensure_ascii=False))
        else:
            print(f"\n[EDINET書類一覧] {code} ({len(docs)}件)")
            print("-" * 80)
            print(f"{'書類ID':<16} {'種別':<6} {'提出日時':<20} {'書類名'}")
            print("-" * 80)
            for doc in docs:
                print(
                    f"{doc.get('docID',''):<16}"
                    f" {doc.get('docTypeCode',''):<6}"
                    f" {doc.get('submitDateTime',''):<20}"
                    f" {doc.get('docDescription','')}"
                )
            print("-" * 80)
    except Exception as e:
        print(f"エラー: {e}")
        logger.exception(e)


async def cmd_filing(args):
    """EDINET書類抽出コマンド"""
    from mebuki.services.data_service import data_service

    code = validate_stock_code(args.code)
    doc_id = getattr(args, "doc_id", None)
    sections = getattr(args, "sections", None) or []
    try:
        result = await data_service.extract_filing_content(
            code,
            doc_id=doc_id or None,
            sections=sections or None,
        )
        if args.format == "json":
            print(json.dumps(result, indent=2, ensure_ascii=False))
        else:
            secs = result.get("sections", {})
            if not secs:
                print("セクションデータが見つかりませんでした。")
                return
            for sec_name, sec_text in secs.items():
                print(f"\n[{sec_name}]")
                print("-" * 60)
                text = sec_text if isinstance(sec_text, str) else json.dumps(sec_text, ensure_ascii=False)
                print(text[:2000] + ("..." if len(text) > 2000 else ""))
    except Exception as e:
        print(f"エラー: {e}")
        logger.exception(e)


def cmd_macro(args):
    """マクロ経済データ取得コマンド"""
    from mebuki.services.macro_analyzer import macro_analyzer

    start = getattr(args, "start", None)
    end = getattr(args, "end", None)
    try:
        if args.category == "fx":
            data = macro_analyzer.get_fx_environment(start, end)
        else:
            data = macro_analyzer.get_monetary_policy_status(start, end)

        if args.format == "json":
            print(json.dumps(data, indent=2, ensure_ascii=False))
        else:
            # リスト形式のデータを想定して直近12件を表示
            if isinstance(data, list):
                rows = data[-12:] 
                print(f"\n[マクロ経済データ] {args.category}  (直近{len(rows)}件)")
                print("-" * 60)
                for row in rows:
                    print(json.dumps(row, ensure_ascii=False))
                print("-" * 60)
            elif isinstance(data, dict):
                print(json.dumps(data, indent=2, ensure_ascii=False))
            else:
                print(data)
    except Exception as e:
        print(f"エラー: {e}")
        logger.exception(e)


async def cmd_visualize(args):
    """財務データ可視化コマンド"""
    from mebuki.services.data_service import data_service

    code = validate_stock_code(args.code)
    try:
        result = await data_service.visualize_financial_data(code)
        print(json.dumps(result, indent=2, ensure_ascii=False))
    except Exception as e:
        print(f"エラー: {e}")
        logger.exception(e)


def cmd_config(args, parser):
    """設定管理コマンド"""
    if not args.config_subcommand:
        parser.print_help()
        return

    if args.config_subcommand == "show":
        settings = settings_store.get_masked()
        print("\n現在の設定 (機密情報はマスクされています):")
        print("-" * 40)
        for k, v in settings.items():
            print(f"{k:<20}: {v}")
        print("-" * 40)
        print(f"設定ファイルパス: {settings_store.config_path}")
        
    elif args.config_subcommand == "set":
        if not args.key or args.value is None:
            print("キーと値を指定してください。例: mebuki config set jquantsApiKey YOUR_KEY")
            return
        
        # マッピング（CLIからの入力をバックエンドのキー名に変換）
        key_map = {
            "jquantsApiKey": "jquantsApiKey",
            "jquants-key": "jquantsApiKey",
            "edinetApiKey": "edinetApiKey",
            "edinet-key": "edinetApiKey",
            "years": "analysisYears",
            "analysisYears": "analysisYears",
            "llm": "llmProvider",
            "llmProvider": "llmProvider"
        }
        
        target_key = key_map.get(args.key, args.key)
        target_value = args.value

        # LLMプロバイダーのバリデーション
        if target_key == "llmProvider":
            allowed = ["gemini", "grok", "claude", "none"]
            if target_value.lower() not in allowed:
                print(f"エラー: 無効なLLMプロバイダーです。{allowed} から選択してください。")
                return
            target_value = target_value.lower()

        settings_store.update({target_key: target_value}, save=True) 
        print(f"設定を更新しました: {target_key}")

    elif args.config_subcommand == "init":
        print("\nmebuki 初期設定")
        print("-" * 40)
        j_key = input("J-QUANTS APIキー (空でスキップ): ").strip()
        e_key = input("EDINET APIキー (空でスキップ): ").strip()
        
        updates = {}
        if j_key: updates["jquantsApiKey"] = j_key
        if e_key: updates["edinetApiKey"] = e_key
        
        if updates:
            settings_store.update(updates, save=True)
            print("設定を保存しました。")
        else:
            print("変更はありません。")

class _DummyParser:
    """対話型モードで cmd_config / cmd_mcp に渡すダミーパーサー"""
    def print_help(self):
        pass


def cmd_interactive():
    """対話型モードの実装"""
    import questionary
    from mebuki.services.data_service import data_service

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
                    years=int(years) if years.isdigit() else 5,
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
                choices = [
                    {"name": f"{item['code']}  {item['name']}  ({item['market']})", "value": item}
                    for item in results
                ]
                choices.append({"name": "↩  キャンセル", "value": None})
                selected = questionary.select("ウォッチリストに追加する銘柄:", choices=choices).ask()
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
                broker = questionary.autocomplete("証券会社:", choices=broker_suggestions, default="").ask()
                account = questionary.select("口座種別:", choices=["特定", "一般", "NISA"]).ask()
                date = questionary.text("取得日 (YYYY-MM-DD, 省略可):", default="").ask()
                name = questionary.text("銘柄名 (省略で自動取得):", default="").ask()
                if code and qty_str and price_str:
                    try:
                        cmd_portfolio(argparse.Namespace(
                            portfolio_subcommand="add",
                            code=code,
                            quantity=int(qty_str),
                            cost_price=float(price_str),
                            broker=broker or "",
                            account=account or "特定",
                            date=date or "",
                            name=name or "",
                        ))
                    except ValueError:
                        print("エラー: 数量・単価は数値で入力してください")
            elif sub == "sell":
                code = questionary.text("銘柄コード:").ask()
                qty_str = questionary.text("売却数量:").ask()
                broker = questionary.autocomplete("証券会社:", choices=broker_suggestions, default="").ask()
                account = questionary.select("口座種別:", choices=["特定", "一般", "NISA"]).ask()
                if code and qty_str:
                    try:
                        cmd_portfolio(argparse.Namespace(
                            portfolio_subcommand="sell",
                            code=code,
                            quantity=int(qty_str),
                            broker=broker or "",
                            account=account or "特定",
                        ))
                    except ValueError:
                        print("エラー: 数量は整数で入力してください")
            elif sub == "remove":
                code = questionary.text("銘柄コード:").ask()
                broker = questionary.autocomplete("証券会社:", choices=broker_suggestions, default="").ask()
                account = questionary.select("口座種別:", choices=["特定", "一般", "NISA"]).ask()
                if code:
                    cmd_portfolio(argparse.Namespace(
                        portfolio_subcommand="remove",
                        code=code,
                        broker=broker or "",
                        account=account or "特定",
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
                break # start はブロッキングなのでループを抜ける

def _get_mcp_command():
    """PyInstaller実行時とPython直接実行時で異なるMCPコマンドを返す"""
    if getattr(sys, 'frozen', False):
        import shutil
        symlink = shutil.which("mebuki")
        executable = symlink if symlink else sys.executable
        return executable, ["mcp", "start"]
    return sys.executable, ["-m", "mebuki.cli", "mcp", "start"]


def cmd_mcp(args, parser):
    """MCP連携管理コマンド"""
    if not args.mcp_subcommand:
        parser.print_help()
        return

    if args.mcp_subcommand == "start":
        print("mebuki native Python MCP server 起動中 (STDIO) ...", file=sys.stderr)
        from mebuki.app.mcp_server import serve
        import asyncio
        import os
        
        # ロギングを無効化または stderr に向ける（STDIOを汚さないため）
        logging.getLogger().handlers = [logging.StreamHandler(sys.stderr)]
        
        try:
            asyncio.run(serve())
        except KeyboardInterrupt:
            pass

    elif args.mcp_subcommand == "install-claude":
        print("\nClaude Desktop への MCP サーバー登録を試みています...")
        
        import os
        from pathlib import Path
        
        # 設定ファイルの特定
        if sys.platform == "darwin":
            config_path = Path.home() / "Library" / "Application Support" / "Claude" / "claude_desktop_config.json"
        elif sys.platform == "win32":
            config_path = Path(os.environ.get("APPDATA", "")) / "Claude" / "claude_desktop_config.json"
        else:
            print(f"OS {sys.platform} は自動インストールに対応していません。手動で設定してください。")
            return

        if not config_path.parent.exists():
            print(f"Claude Desktop の設定ディレクトリが見つかりません: {config_path.parent}")
        else:
            executable, cmd_args = _get_mcp_command()

            # 登録内容の作成
            mcp_config = {
                "command": executable,
                "args": cmd_args,
                "env": {
                    "MEBUKI_USER_DATA_PATH": str(settings_store.user_data_path)
                }
            }

            try:
                config_data = {}
                if config_path.exists():
                    with open(config_path, "r", encoding="utf-8") as f:
                        config_data = json.load(f)
                
                if "mcpServers" not in config_data:
                    config_data["mcpServers"] = {}
                
                config_data["mcpServers"]["mebuki"] = mcp_config
                
                with open(config_path, "w", encoding="utf-8") as f:
                    json.dump(config_data, f, indent=2, ensure_ascii=False)
                
                print(f"成功: Claude Desktop に 'mebuki' MCP サーバーを登録しました。")
                print(f"設定ファイル: {config_path}")
                print("Claude Desktop を再起動して反映させてください。")
            except Exception as e:
                print(f"エラー: Claude Desktop への登録中に問題が発生しました: {e}")

    elif args.mcp_subcommand == "install-goose":
        print("\nGoose への MCP 拡張登録を試みています...")
        import os
        from pathlib import Path
        
        config_path = Path.home() / ".config" / "goose" / "config.yaml"
        if not config_path.parent.exists():
            print(f"Goose の設定ディレクトリが見つかりません: {config_path.parent}")
            return

        try:
            executable, cmd_args = _get_mcp_command()

            # Goose用の設定 (YAML形式)
            config_data = {"extensions": {}}
            if config_path.exists():
                with open(config_path, "r", encoding="utf-8") as f:
                    config_data = yaml.safe_load(f) or {"extensions": {}}

            if "extensions" not in config_data:
                config_data["extensions"] = {}

            config_data["extensions"]["mebuki"] = {
                "enabled": True,
                "name": "mebuki",
                "description": "Expert investment analyst tool for Japanese stocks. Provides high-precision financial data from J-QUANTS and EDINET.",
                "type": "stdio",
                "cmd": executable,
                "args": cmd_args,
                "envs": {
                    "MEBUKI_USER_DATA_PATH": str(settings_store.user_data_path)
                },
                "timeout": 300
            }

            with open(config_path, "w", encoding="utf-8") as f:
                yaml.dump(config_data, f, sort_keys=False)
            
            print(f"成功: Goose に 'mebuki' 拡張を登録しました。")
            print(f"設定ファイル: {config_path}")
        except Exception as e:
            print(f"エラー: Goose への登録中に問題が発生しました: {e}")

def cmd_watch(args):
    """ウォッチリスト管理コマンド"""
    from mebuki.services.portfolio_service import portfolio_service

    sub = args.watch_subcommand

    if sub == "add":
        try:
            result = portfolio_service.add_watch(args.code, name=getattr(args, "name", "") or "")
            if result["status"] == "already_exists":
                print(f"既にウォッチリストに存在します: {args.code}")
            else:
                item = result["item"]
                print(f"ウォッチリストに追加しました: {item['ticker_code']} {item['name']}")
        except ValueError as e:
            print(f"エラー: {e}")

    elif sub == "remove":
        try:
            result = portfolio_service.remove_watch(args.code)
            if result["status"] == "removed":
                print(f"ウォッチリストから削除しました: {args.code}")
            else:
                print(f"見つかりませんでした: {args.code}")
        except ValueError as e:
            print(f"エラー: {e}")

    elif sub == "list":
        watchlist = portfolio_service.get_watchlist()
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
            if result["status"] == "removed":
                print(f"保有エントリを削除しました: {args.code}")
            else:
                print(f"見つかりませんでした: {args.code}")
        except ValueError as e:
            print(f"エラー: {e}")

    elif sub == "list":
        detail = getattr(args, "detail", False)
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


def build_parser() -> argparse.ArgumentParser:
    """CLIパーサーを構築します。"""
    parser = argparse.ArgumentParser(description="mebuki: 投資分析ツール CLI")
    parser.add_argument("--version", action="version", version=f"mebuki {__version__}")
    subparsers = parser.add_subparsers(dest="command", help="サブコマンド")

    # search
    search_parser = subparsers.add_parser("search", help="銘柄を検索")
    search_parser.add_argument("query", help="検索クエリ（銘柄名またはコード）")

    # analyze
    analyze_parser = subparsers.add_parser("analyze", help="銘柄を分析")
    analyze_parser.add_argument("code", help="銘柄コード")
    analyze_parser.add_argument("--scope", choices=["overview", "history", "metrics", "raw"], default=None, help="取得スコープ")
    analyze_parser.add_argument("--years", type=int, help="分析年数")
    analyze_parser.add_argument("--format", choices=["table", "json"], default="table", help="出力形式")
    analyze_parser.add_argument("--no-cache", action="store_true", help="キャッシュを使用しない")
    analyze_parser.add_argument(
        "--include-2q", action="store_true", dest="include_2q",
        help="2Q（中間）データも含めて集計する"
    )

    # price
    price_parser = subparsers.add_parser("price", help="株価データを取得")
    price_parser.add_argument("code", help="銘柄コード")
    price_parser.add_argument("--days", type=int, default=30, help="取得日数 (デフォルト: 30)")
    price_parser.add_argument("--format", choices=["table", "json"], default="table", help="出力形式")

    # filings
    filings_parser = subparsers.add_parser("filings", help="EDINET書類一覧を取得")
    filings_parser.add_argument("code", help="銘柄コード")
    filings_parser.add_argument("--format", choices=["table", "json"], default="table", help="出力形式")

    # filing
    filing_parser = subparsers.add_parser("filing", help="EDINET書類の内容を抽出")
    filing_parser.add_argument("code", help="銘柄コード")
    filing_parser.add_argument("--doc-id", dest="doc_id", help="書類ID (省略時は最新の有価証券報告書)")
    filing_parser.add_argument("--sections", nargs="+", help="抽出するセクション名 (複数指定可)")
    filing_parser.add_argument("--format", choices=["table", "json"], default="table", help="出力形式")

    # macro
    macro_parser = subparsers.add_parser("macro", help="マクロ経済データを取得")
    macro_parser.add_argument("category", choices=["fx", "monetary"], help="カテゴリ (fx: 為替, monetary: 金融政策)")
    macro_parser.add_argument("--start", help="開始月 (YYYYMM)")
    macro_parser.add_argument("--end", help="終了月 (YYYYMM)")
    macro_parser.add_argument("--format", choices=["table", "json"], default="table", help="出力形式")

    # visualize
    visualize_parser = subparsers.add_parser("visualize", help="財務データを可視化形式で取得")
    visualize_parser.add_argument("code", help="銘柄コード")

    # config
    config_parser = subparsers.add_parser("config", help="設定の表示・変更")
    config_sub = config_parser.add_subparsers(dest="config_subcommand", help="設定サブコマンド")
    config_sub.add_parser("show", help="設定を表示")
    set_parser = config_sub.add_parser("set", help="値を設定")
    set_parser.add_argument("key", help="設定キー (jquants-key, edinet-key, years 等)")
    set_parser.add_argument("value", help="設定値")
    config_sub.add_parser("init", help="対話形式で初期設定")

    # mcp
    mcp_parser = subparsers.add_parser("mcp", help="MCP連携管理")
    mcp_sub = mcp_parser.add_subparsers(dest="mcp_subcommand")
    mcp_sub.add_parser("install-claude", help="Claude Desktop に登録")
    mcp_sub.add_parser("install-goose", help="Goose に登録")
    mcp_sub.add_parser("start", help="MCPサーバーを起動 (STDIO)")

    # watch
    watch_parser = subparsers.add_parser("watch", help="ウォッチリスト管理")
    watch_sub = watch_parser.add_subparsers(dest="watch_subcommand")
    watch_add = watch_sub.add_parser("add", help="ウォッチリストに追加")
    watch_add.add_argument("code", help="銘柄コード")
    watch_add.add_argument("--name", help="銘柄名（省略時は自動取得）")
    watch_rm = watch_sub.add_parser("remove", help="ウォッチリストから削除")
    watch_rm.add_argument("code", help="銘柄コード")
    watch_sub.add_parser("list", help="ウォッチリストを表示")

    # portfolio
    pf_parser = subparsers.add_parser("portfolio", help="ポートフォリオ管理")
    pf_sub = pf_parser.add_subparsers(dest="portfolio_subcommand")

    pf_add = pf_sub.add_parser("add", help="保有銘柄を追加")
    pf_add.add_argument("code", help="銘柄コード")
    pf_add.add_argument("quantity", type=int, help="数量")
    pf_add.add_argument("cost_price", type=float, help="取得単価")
    pf_add.add_argument("--broker", default="", help="証券会社名")
    pf_add.add_argument("--account", choices=["特定", "一般", "NISA"], default="特定", help="口座種別")
    pf_add.add_argument("--date", help="取得日 (YYYY-MM-DD)")
    pf_add.add_argument("--name", help="銘柄名（省略時は自動取得）")

    pf_sell = pf_sub.add_parser("sell", help="保有銘柄を売却")
    pf_sell.add_argument("code", help="銘柄コード")
    pf_sell.add_argument("quantity", type=int, help="売却数量")
    pf_sell.add_argument("--broker", default="", help="証券会社名")
    pf_sell.add_argument("--account", choices=["特定", "一般", "NISA"], default="特定", help="口座種別")

    pf_rm = pf_sub.add_parser("remove", help="保有エントリを削除")
    pf_rm.add_argument("code", help="銘柄コード")
    pf_rm.add_argument("--broker", default="", help="証券会社名")
    pf_rm.add_argument("--account", choices=["特定", "一般", "NISA"], default="特定", help="口座種別")

    pf_list = pf_sub.add_parser("list", help="ポートフォリオを表示")
    pf_list.add_argument("--detail", action="store_true", help="口座別詳細を表示")

    return parser


def main():
    if len(sys.argv) == 1:
        print_banner()
        try:
            cmd_interactive()
        except KeyboardInterrupt:
            print("\n終了します。")
        return

    print_banner()
    parser = build_parser()

    args = parser.parse_args()
    
    if args.command == "search":
        cmd_search(args)
    elif args.command == "analyze":
        import asyncio
        asyncio.run(cmd_analyze(args))
    elif args.command == "config":
        cmd_config(args, parser)
    elif args.command == "mcp":
        cmd_mcp(args, parser)
    elif args.command == "price":
        import asyncio
        asyncio.run(cmd_price(args))
    elif args.command == "filings":
        import asyncio
        asyncio.run(cmd_filings(args))
    elif args.command == "filing":
        import asyncio
        asyncio.run(cmd_filing(args))
    elif args.command == "macro":
        cmd_macro(args)
    elif args.command == "visualize":
        import asyncio
        asyncio.run(cmd_visualize(args))
    elif args.command == "watch":
        cmd_watch(args)
    elif args.command == "portfolio":
        cmd_portfolio(args)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
