import argparse
import sys
import json
import logging
from typing import List, Dict, Any, Optional
from backend.settings import settings_store
from backend.services.master_data import master_data_manager

# アスキーアート
WAKABA_ART = r"""
  ███╗   ███╗███████╗██████╗ ██╗   ██╗██╗  ██╗██╗
  ████╗ ████║██╔════╝██╔══██╗██║   ██║██║ ██╔╝██║
  ██╔████╔██║█████╗  ██████╔╝██║   ██║█████╔╝ ██║
  ██║╚██╔╝██║██╔══╝  ██╔══██╗██║   ██║██╔═██╗ ██║
  ██║ ╚═╝ ██║███████╗██████╔╝╚██████╔╝██║  ██╗██║ 🌱
  ╚═╝     ╚═╝╚══════╝╚═════╝  ╚═════╝ ╚═╝  ╚═╝╚═╝
"""

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

async def cmd_analyze(args):
    """銘柄分析コマンド"""
    from backend.services.data_service import data_service
    
    code = args.code
    # 銘柄情報の確認
    info = data_service.fetch_stock_basic_info(code)
    if not info.get("name"):
        print(f"エラー: 銘柄コード {code} が見つかりません。")
        return
    
    print(f"\n分析中: {code} {info['name']} ({info['market_name']}) ...")
    
    try:
        # data_service を使って生の財務データを取得
        years = args.years or settings_store.analysis_years or 5
        result = await data_service.get_raw_analysis_data(code, use_cache=not args.no_cache)
        
        if not result or not result.get("metrics"):
            print("エラー: 財務データの取得に失敗しました。APIキーが正しく設定されているか確認してください。")
            return
            
        if args.format == "json":
            print(json.dumps(result, indent=2, ensure_ascii=False))
            return
            
        # 簡易的なテーブル表示
        metrics = result.get("metrics", {})
        years_data = metrics.get("years", [])
        if not years_data:
            print("エラー: 指標データが見つかりませんでした。")
            return
            
        latest_fy_data = years_data[0]
        calc_data = latest_fy_data.get("CalculatedData", {})
        
        print(f"\n[主要財務指標 (直近年度: {latest_fy_data.get('fy_end', '不明')})]")
        print("-" * 50)
        
        # 指標の計算と整理
        sales = calc_data.get("Sales", 0)
        op = calc_data.get("OP", 0)
        eq = calc_data.get("Eq", 0)
        assets = calc_data.get("TotalAssets", 0) or calc_data.get("Assets", 0)
        
        op_margin = (op / sales * 100) if sales else None
        eq_ratio = (eq / assets * 100) if assets else None
        
        display_list = [
            ("ROE", "ROE (%)", calc_data.get("ROE")),
            ("ROIC", "ROIC (%)", calc_data.get("SimpleROIC")),
            ("Margin", "営業利益率 (%)", op_margin if op_margin is not None else calc_data.get("OperatingMargin")),
            ("Equity", "自己資本比率 (%)", eq_ratio if eq_ratio is not None else calc_data.get("EquityRatio")),
            ("PER", "PER (倍)", calc_data.get("PER")),
            ("PBR", "PBR (倍)", calc_data.get("PBR")),
            ("Yield", "配当利回り (%)", calc_data.get("DividendYield")),
        ]
        
        for key, label, val in display_list:
            if val is not None:
                print(f"{label:<22}: {val:>12.2f}")
        print("-" * 50)
        print("\n詳細な分析や定性情報は MCP版（Claude等）をご利用ください。")
        
    except Exception as e:
        print(f"エラー: 分析中に例外が発生しました: {e}")
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

def cmd_interactive():
    """対話型モードの実装"""
    import questionary
    from backend.services.data_service import data_service

    while True:
        action = questionary.select(
            "実行するアクションを選択してください:",
            choices=[
                {"name": "🔍 銘柄検索 (search)", "value": "search"},
                {"name": "📊 銘柄分析 (analyze)", "value": "analyze"},
                {"name": "⚙️ 設定管理 (config)", "value": "config"},
                {"name": "🔌 MCP連携 (mcp)", "value": "mcp"},
                {"name": "🚪 終了", "value": "exit"}
            ]
        ).ask()

        if action == "exit" or action is None:
            break

        if action == "search":
            query = questionary.text("検索キーワードを入力してください:").ask()
            if query:
                # 擬似的な引数オブジェクトを作成
                class Args: pass
                args = Args(); args.query = query
                cmd_search(args)

        elif action == "analyze":
            code = questionary.text("銘柄コードを入力してください (例: 7203):").ask()
            if code:
                years = questionary.text("分析年数:", default=str(settings_store.analysis_years or 5)).ask()
                class Args: pass
                args = Args(); args.code = code; args.years = int(years) if years.isdigit() else 5
                args.format = "table"; args.no_cache = False
                import asyncio
                asyncio.run(cmd_analyze(args))

        elif action == "config":
            sub = questionary.select(
                "設定アクション:",
                choices=[
                    {"name": "📋 設定を表示", "value": "show"},
                    {"name": "✏️ 値を変更", "value": "set"},
                    {"name": "🌟 初期設定を開始", "value": "init"},
                    {"name": "⬅️ 戻る", "value": "back"}
                ]
            ).ask()

            if sub == "back" or sub is None: continue

            class Args: pass
            args = Args(); args.config_subcommand = sub
            if sub == "set":
                args.key = questionary.select("変更する項目:", choices=[
                    "jquantsApiKey", "edinetApiKey", "analysisYears", "llmProvider"
                ]).ask()
                args.value = questionary.text(f"{args.key} の新しい値:").ask()
            
            # ダミーの parser を渡す
            class DummyParser:
                def print_help(self): print("config help")
            cmd_config(args, DummyParser())

        elif action == "mcp":
            sub = questionary.select(
                "MCP連携アクション:",
                choices=[
                    {"name": "🚀 サーバー起動 (start)", "value": "start"},
                    {"name": "📥 Claude Desktop への登録 (install)", "value": "install"},
                    {"name": "🦆 Goose への登録 (install-goose)", "value": "install-goose"},
                    {"name": "⬅️ 戻る", "value": "back"}
                ]
            ).ask()

            if sub == "back" or sub is None: continue

            class Args: pass
            args = Args(); args.mcp_subcommand = sub
            class DummyParser:
                def print_help(self): print("mcp help")
            cmd_mcp(args, DummyParser())
            
            if sub == "start":
                break # start はブロッキングなのでループを抜ける

def cmd_mcp(args, parser):
    """MCP連携管理コマンド"""
    if not args.mcp_subcommand:
        parser.print_help()
        return
        
    if args.mcp_subcommand == "start":
        print("mebuki native Python MCP server 起動中 (STDIO) ...", file=sys.stderr)
        from mebuki.mcp_server import serve
        import asyncio
        import os
        
        # ロギングを無効化または stderr に向ける（STDIOを汚さないため）
        logging.getLogger().handlers = [logging.StreamHandler(sys.stderr)]
        
        try:
            asyncio.run(serve())
        except KeyboardInterrupt:
            pass

    elif args.mcp_subcommand == "install":
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
            # 実行可能パスの取得（venv環境を優先）
            executable = sys.executable
            project_root = str(Path(__file__).parent.parent.absolute())
            
            # 登録内容の作成
            mcp_config = {
                "command": executable,
                "args": ["-m", "mebuki.cli", "mcp", "start"],
                "env": {
                    "PYTHONPATH": project_root,
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

        executable = sys.executable
        project_root = str(Path(__file__).parent.parent.absolute())

        # Goose用の設定 (YAML形式)
        # 簡易的に追加するために既存のファイルを読み込んで解析するか、追記する
        try:
            import yaml
        except ImportError:
            print("YAMLライブラリが見つからないため、インストールを試みます...")
            import subprocess
            subprocess.run([sys.executable, "-m", "pip", "install", "pyyaml"], check=True)
            import yaml

        try:
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
                "args": ["-m", "mebuki.cli", "mcp", "start"],
                "envs": {
                    "PYTHONPATH": project_root,
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

def main():
    if len(sys.argv) == 1:
        print_banner()
        try:
            cmd_interactive()
        except KeyboardInterrupt:
            print("\n終了します。")
        return

    print_banner()
    parser = argparse.ArgumentParser(description="mebuki: 投資分析ツール CLI")
    subparsers = parser.add_subparsers(dest="command", help="サブコマンド")
    
    # search
    search_parser = subparsers.add_parser("search", help="銘柄を検索")
    search_parser.add_argument("query", help="検索クエリ（銘柄名またはコード）")
    
    # analyze
    analyze_parser = subparsers.add_parser("analyze", help="銘柄を分析")
    analyze_parser.add_argument("code", help="銘柄コード")
    analyze_parser.add_argument("--years", type=int, help="分析年数")
    analyze_parser.add_argument("--format", choices=["table", "json"], default="table", help="出力形式")
    analyze_parser.add_argument("--no-cache", action="store_true", help="キャッシュを使用しない")
    
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
    mcp_sub.add_parser("install", help="Claude Desktop に登録")
    mcp_sub.add_parser("install-goose", help="Goose に登録")
    mcp_sub.add_parser("start", help="MCPサーバーを起動 (STDIO)")

    args = parser.parse_args()
    
    if args.command == "search":
        cmd_search(args)
    elif args.command == "analyze":
        import asyncio
        asyncio.run(cmd_analyze(args))
    elif args.command == "config":
        cmd_config(args, config_parser)
    elif args.command == "mcp":
        cmd_mcp(args, mcp_parser)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
