import argparse
from blue_ticker import __version__
from blue_ticker.constants.api import ANALYZE_DEFAULT_YEARS, EDINET_FILINGS_DEFAULT_YEARS, EDINET_PREPARE_DEFAULT_YEARS


def build_parser() -> argparse.ArgumentParser:
    """CLIパーサーを構築します。"""
    parser = argparse.ArgumentParser(prog="ticker", description="BLUE TICKER: 日本株分析ツール CLI")
    parser.add_argument("--version", action="version", version=f"BLUE TICKER {__version__}")
    subparsers = parser.add_subparsers(dest="command", help="サブコマンド")

    # search
    search_parser = subparsers.add_parser("search", help="銘柄を検索")
    search_parser.add_argument("query", help="検索クエリ（銘柄名またはコード）")
    search_parser.add_argument("--format", choices=["table", "json"], default="json", help="出力形式")

    # analyze
    analyze_parser = subparsers.add_parser("analyze", help="銘柄を分析")
    analyze_parser.add_argument("code", help="銘柄コード")
    analyze_parser.add_argument("--years", type=int, help=f"分析年数（デフォルト: {ANALYZE_DEFAULT_YEARS}）")
    analyze_parser.add_argument("--format", choices=["table", "json"], default="json", help="出力形式")
    analyze_parser.add_argument(
        "--no-cache",
        action="store_true",
        help="分析結果キャッシュを使用せず再計算する。最新の財務省金利を反映したWACCを確認したい場合も指定",
    )
    analyze_parser.add_argument(
        "--half", action="store_true",
        help="上半期(H1)・下半期(H2)の半期推移を表示する"
    )
    analyze_parser.add_argument(
        "--include-debug-fields", dest="include_debug_fields", action="store_true",
        help="MetricSources・IBDComponents 等のデバッグフィールドを JSON に含める"
    )

    # filings
    filings_parser = subparsers.add_parser("filings", help="EDINET書類一覧を取得")
    filings_parser.add_argument("code", help="銘柄コード")
    filings_parser.add_argument(
        "--years",
        type=int,
        default=EDINET_FILINGS_DEFAULT_YEARS,
        help=f"探索年数（デフォルト: {EDINET_FILINGS_DEFAULT_YEARS}）",
    )
    filings_parser.add_argument("--format", choices=["table", "json"], default="json", help="出力形式")

    # filing
    filing_parser = subparsers.add_parser("filing", help="EDINET書類の内容を抽出（JSON出力）")
    filing_parser.add_argument("code", help="銘柄コード")
    filing_parser.add_argument("--doc-id", dest="doc_id", help="書類ID (省略時は最新の有価証券報告書)")
    filing_parser.add_argument("--sections", nargs="+", help="抽出するセクション名 (複数指定可)")

    # config
    config_parser = subparsers.add_parser("config", help="設定の表示・変更")
    config_sub = config_parser.add_subparsers(dest="config_subcommand", help="設定サブコマンド")
    config_sub.add_parser("show", help="設定を表示")
    set_parser = config_sub.add_parser("set", help="値を設定")
    set_parser.add_argument("key", help="設定キー (edinet-key 等)")
    set_parser.add_argument("value", help="設定値")
    config_sub.add_parser("init", help="対話形式で初期設定")
    config_sub.add_parser("check", help="API設定の確認")

    # cache
    cache_parser = subparsers.add_parser("cache", help="キャッシュ管理")
    cache_sub = cache_parser.add_subparsers(dest="cache_subcommand", help="キャッシュサブコマンド")
    status_parser = cache_sub.add_parser("status", help="キャッシュ状態を表示")
    status_parser.add_argument(
        "--years",
        type=int,
        default=EDINET_PREPARE_DEFAULT_YEARS,
        help=f"確認する直近年数（デフォルト: {EDINET_PREPARE_DEFAULT_YEARS}）",
    )
    status_parser.add_argument("--format", choices=["table", "json"], default="table", help="出力形式")
    prepare_parser = cache_sub.add_parser("prepare", help="EDINET年次インデックスを事前準備")
    prepare_parser.add_argument(
        "--years",
        type=int,
        default=EDINET_PREPARE_DEFAULT_YEARS,
        help=f"準備する直近年数（デフォルト: {EDINET_PREPARE_DEFAULT_YEARS}）",
    )
    prepare_parser.add_argument("--format", choices=["table", "json"], default="table", help="出力形式")
    catchup_parser = cache_sub.add_parser("catchup", help="EDINET年次インデックスの不足分を取得")
    catchup_parser.add_argument(
        "--years",
        type=int,
        default=EDINET_PREPARE_DEFAULT_YEARS,
        help=f"差分更新する直近年数（デフォルト: {EDINET_PREPARE_DEFAULT_YEARS}）",
    )
    catchup_parser.add_argument("--format", choices=["table", "json"], default="table", help="出力形式")
    refresh_parser = cache_sub.add_parser("refresh", help="EDINET年次インデックスを更新")
    refresh_parser.add_argument(
        "--years",
        type=int,
        default=EDINET_PREPARE_DEFAULT_YEARS,
        help=f"更新する直近年数（デフォルト: {EDINET_PREPARE_DEFAULT_YEARS}）",
    )
    refresh_parser.add_argument("--format", choices=["table", "json"], default="table", help="出力形式")
    clean_parser = cache_sub.add_parser("clean", help="不要なキャッシュを削除")
    clean_parser.add_argument("--execute", action="store_true", help="実際に削除する（未指定時は dry-run）")
    clean_parser.add_argument(
        "--edinet-search-days",
        type=int,
        default=None,
        help="指定日数以上古い EDINET 検索キャッシュを削除",
    )
    clean_parser.add_argument(
        "--edinet-xbrl-days",
        type=int,
        default=None,
        help="指定日数以上古い EDINET XBRL 展開ディレクトリを削除",
    )
    clean_parser.add_argument(
        "--edinet-doc-index-years",
        type=int,
        default=6,
        help="保持する EDINET 年次インデックス年数（デフォルト: 6、0で全削除）",
    )
    clean_parser.add_argument("--format", choices=["table", "json"], default="table", help="出力形式")

    # sector
    sector_parser = subparsers.add_parser("sector", help="東証33業種で銘柄を検索")
    sector_parser.add_argument("sector", nargs="?", help="業種名（省略時は全業種一覧を表示）")
    sector_parser.add_argument("--format", choices=["table", "json"], default="json", help="出力形式")

    # watch
    watch_parser = subparsers.add_parser("watch", help="ウォッチリスト管理")
    watch_sub = watch_parser.add_subparsers(dest="watch_subcommand")
    watch_add = watch_sub.add_parser("add", help="ウォッチリストに追加")
    watch_add.add_argument("code", help="銘柄コード")
    watch_add.add_argument("--name", help="銘柄名（省略時は自動取得）")
    watch_add.add_argument("--format", choices=["table", "json"], default="json", help="出力形式")
    watch_rm = watch_sub.add_parser("remove", help="ウォッチリストから削除")
    watch_rm.add_argument("code", help="銘柄コード")
    watch_rm.add_argument("--format", choices=["table", "json"], default="json", help="出力形式")
    watch_list = watch_sub.add_parser("list", help="ウォッチリストを表示")
    watch_list.add_argument("--format", choices=["table", "json"], default="json", help="出力形式")

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
    pf_add.add_argument("--format", choices=["table", "json"], default="json", help="出力形式")

    pf_sell = pf_sub.add_parser("sell", help="保有銘柄を売却")
    pf_sell.add_argument("code", help="銘柄コード")
    pf_sell.add_argument("quantity", type=int, help="売却数量")
    pf_sell.add_argument("--broker", default="", help="証券会社名")
    pf_sell.add_argument("--account", choices=["特定", "一般", "NISA"], default="特定", help="口座種別")
    pf_sell.add_argument("--format", choices=["table", "json"], default="json", help="出力形式")

    pf_rm = pf_sub.add_parser("remove", help="保有エントリを削除")
    pf_rm.add_argument("code", help="銘柄コード")
    pf_rm.add_argument("--broker", default="", help="証券会社名")
    pf_rm.add_argument("--account", choices=["特定", "一般", "NISA"], default="特定", help="口座種別")
    pf_rm.add_argument("--format", choices=["table", "json"], default="json", help="出力形式")

    pf_list = pf_sub.add_parser("list", help="ポートフォリオを表示")
    pf_list.add_argument("--detail", action="store_true", help="口座別詳細を表示")
    pf_list.add_argument("--format", choices=["table", "json"], default="json", help="出力形式")

    pf_sector = pf_sub.add_parser("sector", help="セクター別配分を表示")
    pf_sector.add_argument("--format", choices=["table", "json"], default="table", help="出力形式")

    return parser
