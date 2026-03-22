import argparse
from mebuki import __version__


def build_parser() -> argparse.ArgumentParser:
    """CLIパーサーを構築します。"""
    parser = argparse.ArgumentParser(description="mebuki: 投資分析ツール CLI")
    parser.add_argument("--version", action="version", version=f"mebuki {__version__}")
    subparsers = parser.add_subparsers(dest="command", help="サブコマンド")

    # search
    search_parser = subparsers.add_parser("search", help="銘柄を検索")
    search_parser.add_argument("query", help="検索クエリ（銘柄名またはコード）")
    search_parser.add_argument("--format", choices=["table", "json"], default="table", help="出力形式")

    # analyze
    analyze_parser = subparsers.add_parser("analyze", help="銘柄を分析")
    analyze_parser.add_argument("code", help="銘柄コード")
    analyze_parser.add_argument("--scope", choices=["overview", "metrics", "raw"], default=None, help="取得スコープ")
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
    mcp_sub.add_parser("install-lm-studio", help="LM Studio に登録")
    mcp_sub.add_parser("start", help="MCPサーバーを起動 (STDIO)")

    # watch
    watch_parser = subparsers.add_parser("watch", help="ウォッチリスト管理")
    watch_sub = watch_parser.add_subparsers(dest="watch_subcommand")
    watch_add = watch_sub.add_parser("add", help="ウォッチリストに追加")
    watch_add.add_argument("code", help="銘柄コード")
    watch_add.add_argument("--name", help="銘柄名（省略時は自動取得）")
    watch_add.add_argument("--format", choices=["table", "json"], default="table", help="出力形式")
    watch_rm = watch_sub.add_parser("remove", help="ウォッチリストから削除")
    watch_rm.add_argument("code", help="銘柄コード")
    watch_rm.add_argument("--format", choices=["table", "json"], default="table", help="出力形式")
    watch_list = watch_sub.add_parser("list", help="ウォッチリストを表示")
    watch_list.add_argument("--format", choices=["table", "json"], default="table", help="出力形式")

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
    pf_add.add_argument("--format", choices=["table", "json"], default="table", help="出力形式")

    pf_sell = pf_sub.add_parser("sell", help="保有銘柄を売却")
    pf_sell.add_argument("code", help="銘柄コード")
    pf_sell.add_argument("quantity", type=int, help="売却数量")
    pf_sell.add_argument("--broker", default="", help="証券会社名")
    pf_sell.add_argument("--account", choices=["特定", "一般", "NISA"], default="特定", help="口座種別")
    pf_sell.add_argument("--format", choices=["table", "json"], default="table", help="出力形式")

    pf_rm = pf_sub.add_parser("remove", help="保有エントリを削除")
    pf_rm.add_argument("code", help="銘柄コード")
    pf_rm.add_argument("--broker", default="", help="証券会社名")
    pf_rm.add_argument("--account", choices=["特定", "一般", "NISA"], default="特定", help="口座種別")
    pf_rm.add_argument("--format", choices=["table", "json"], default="table", help="出力形式")

    pf_list = pf_sub.add_parser("list", help="ポートフォリオを表示")
    pf_list.add_argument("--detail", action="store_true", help="口座別詳細を表示")
    pf_list.add_argument("--format", choices=["table", "json"], default="table", help="出力形式")

    return parser
