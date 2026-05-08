import json
import sys
import logging
from collections.abc import Mapping
import aiohttp
from blue_ticker.infrastructure.helpers import validate_stock_code
from blue_ticker.infrastructure.settings import settings_store
from blue_ticker.services.master_data import master_data_manager
from blue_ticker.utils.converters import extract_year_month
from blue_ticker.constants.api import EDINET_FILINGS_DEFAULT_YEARS

logger = logging.getLogger(__name__)


def _gross_profit_labels(calculated_data: Mapping[str, object]) -> tuple[str, str, str]:
    """売上総利益系の表示ラベルを返す。"""
    base_label_value = calculated_data.get("GrossProfitLabel", "売上総利益")
    base_label = base_label_value if isinstance(base_label_value, str) else "売上総利益"
    gross_profit_label = f"{base_label} (百万)"
    gross_profit_margin_label = (
        f"{base_label}率 (%)"
        if base_label != "売上総利益"
        else "粗利率 (%)"
    )
    gross_margin_change_label = (
        f"{base_label}率差影響"
        if base_label != "売上総利益"
        else "粗利率差影響"
    )
    return gross_profit_label, gross_profit_margin_label, gross_margin_change_label


def cmd_search(args):
    """銘柄検索コマンド"""
    if not args.query:
        print("検索クエリを指定してください。", file=sys.stderr)
        return

    results = master_data_manager.search(args.query)
    if not results:
        print(f"'{args.query}' に一致する銘柄は見つかりませんでした。", file=sys.stderr)
        return

    if getattr(args, 'format', 'table') == 'json':
        print(json.dumps(results, indent=2, ensure_ascii=False))
        return

    print(f"\n'{args.query}' の検索結果 ({len(results)}件):", file=sys.stderr)
    print("-" * 60, file=sys.stderr)
    print(f"{'コード':<8} {'銘柄名':<20} {'市場':<15} {'業種'}", file=sys.stderr)
    print("-" * 60, file=sys.stderr)
    for item in results:
        print(f"{item['code']:<8} {item['name']:<20} {item['market']:<15} {item['sector']}", file=sys.stderr)
    print("-" * 60, file=sys.stderr)


async def cmd_analyze(args):
    """銘柄分析コマンド"""
    from blue_ticker.services.data_service import data_service

    try:
        code = validate_stock_code(args.code)
    except ValueError as e:
        print(f"エラー: {e}", file=sys.stderr)
        return

    include_debug = getattr(args, "include_debug_fields", False)
    requested_years = getattr(args, "years", None)
    if requested_years is not None and requested_years <= 0:
        print("エラー: years には正の整数を指定してください。", file=sys.stderr)
        return

    # --half が指定された場合は半期推移表示
    if getattr(args, "half", False):
        try:
            info = data_service.fetch_stock_basic_info(code)
            if not info.get("name"):
                print(f"エラー: 銘柄コード {code} が見つかりません。", file=sys.stderr)
                return

            half_years = requested_years or 3
            print(f"\n分析中: {code} {info['name']} ({info['market_name']}) ...", file=sys.stderr)
            print(f"分析対象期間: 直近 {half_years} 年分 (上半期 / 下半期)", file=sys.stderr)

            periods = await data_service.get_half_year_periods(
                code, years=half_years, use_cache=not args.no_cache, include_debug_fields=include_debug
            )
            if not periods:
                print("エラー: 財務データの取得に失敗しました。APIキーが正しく設定されているか確認してください。", file=sys.stderr)
                return

            if args.format == "json":
                print(json.dumps(periods, indent=2, ensure_ascii=False))
                return

            print(f"\n[半期財務推移]", file=sys.stderr)
            headers = ["項目 \\ 期"] + [p["label"] for p in periods]
            row_format = "{:<18}" + " {:>10}" * len(periods)
            sep = "-" * (18 + 11 * len(periods))
            print(sep, file=sys.stderr)
            print(row_format.format(*headers), file=sys.stderr)
            print(sep, file=sys.stderr)

            latest_period_data = periods[-1].get("data", {}) if periods else {}
            gross_profit_label, gross_profit_margin_label, gross_margin_change_label = (
                _gross_profit_labels(latest_period_data)
            )

            half_metrics_to_show = [
                ("売上高 (百万)",      lambda d: d.get("Sales")),
                (gross_profit_label,   lambda d: d.get("GrossProfit")),
                (gross_profit_margin_label, lambda d: d.get("GrossProfitMargin")),
                ("営業利益 (百万)",    lambda d: d.get("OP")),
                ("営業利益率 (%)",     lambda d: d.get("OperatingMargin")),
                ("販管費 (百万)",      lambda d: d.get("SellingGeneralAdministrativeExpenses")),
                ("営業利益前年差",      lambda d: d.get("OperatingProfitChange")),
                ("売上差影響",         lambda d: d.get("SalesChangeImpact")),
                (gross_margin_change_label, lambda d: d.get("GrossMarginChangeImpact")),
                ("販管費増影響",       lambda d: d.get("SGAChangeImpact")),
                ("純利益 (百万)",      lambda d: d.get("NP")),
                ("ROIC (%)",           lambda d: d.get("ROIC")),
                ("営業CF (百万)",      lambda d: d.get("CFO")),
                ("投資CF (百万)",      lambda d: d.get("CFI")),
                ("フリーCF (百万)",    lambda d: d.get("CFC", d.get("FreeCF"))),
                ("DocID",              lambda d: d.get("DocID")),
            ]

            for label, func in half_metrics_to_show:
                row = [label]
                for p in periods:
                    val = func(p["data"])
                    if val is None:
                        row.append(f"{'-':>10}")
                    elif isinstance(val, str):
                        row.append(f"{val:>10}")
                    else:
                        row.append(f"{val:>10.2f}")
                print(row_format.format(*row), file=sys.stderr)

            print(sep, file=sys.stderr)
        except ValueError as e:
            print(f"エラー: {e}", file=sys.stderr)
        except aiohttp.ClientError as e:
            print(f"エラー: {e}", file=sys.stderr)
            logger.exception(e)
        finally:
            await data_service.close()
        return

    try:
        # 銘柄情報の確認
        info = data_service.fetch_stock_basic_info(code)
        if not info.get("name"):
            print(f"エラー: 銘柄コード {code} が見つかりません。", file=sys.stderr)
            return

        # 分析年数の決定
        years_to_analyze = requested_years or settings_store.analysis_years

        print(f"\n分析中: {code} {info['name']} ({info['market_name']}) ...", file=sys.stderr)
        years_label = f"直近 {years_to_analyze} 年分" if years_to_analyze else "全期間"
        print(f"分析対象期間: {years_label}", file=sys.stderr)
        # data_service を使って生の財務データを取得
        result = await data_service.get_raw_analysis_data(
            code, use_cache=not args.no_cache, analysis_years=years_to_analyze, include_debug_fields=include_debug,
        )

        if not result or not result.get("metrics"):
            print("エラー: 財務データの取得に失敗しました。APIキーが正しく設定されているか確認してください。", file=sys.stderr)
            return

        if args.format == "json":
            print(json.dumps(result, indent=2, ensure_ascii=False))
            return

        # 指標データの取得
        metrics = result.get("metrics", {})
        years_data = metrics.get("years", [])
        if not years_data:
            print("エラー: 指標データが見つかりませんでした。", file=sys.stderr)
            return

        # 横並びのテーブル表示
        print(f"\n[主要財務指標の推移]", file=sys.stderr)

        # ヘッダー作成（年度）
        headers = ["項目 \\ 年度"]
        periods = []
        for y_data in reversed(years_data): # 古い順に表示
            fy_end = y_data.get("fy_end", "不明")
            year, month = extract_year_month(fy_end)
            if year is not None:
                period_str = f"{str(year)[2:]}/{month:02d}"
            else:
                period_str = fy_end
            per_type = y_data.get("RawData", {}).get("CurPerType", "FY")
            if per_type == "2Q":
                period_str += "(2Q)"
            headers.append(period_str)
            periods.append(y_data)

        row_format = "{:<16}" + " {:>10}" * len(periods)
        print("-" * (16 + 11 * len(periods)), file=sys.stderr)
        print(row_format.format(*headers), file=sys.stderr)
        print("-" * (16 + 11 * len(periods)), file=sys.stderr)

        # 各指標の行を作成
        def get_op_margin(c):
            return c.get("OperatingMargin") or (c.get("OP") / c.get("Sales") * 100 if c.get("OP") and c.get("Sales") else None)

        # IFRS金融会社は純収益・事業利益ラベルを使う（最新年度のラベルで判定）
        latest_cd = periods[-1].get("CalculatedData", {}) if periods else {}
        sales_label = latest_cd.get("SalesLabel", "売上高") + " (百万)"
        gross_profit_label, gross_profit_margin_label, gross_margin_change_label = (
            _gross_profit_labels(latest_cd)
        )
        op_label = latest_cd.get("OPLabel", "営業利益") + " (百万)"
        op_margin_label = latest_cd.get("OPLabel", "営業利益") + "率 (%)"

        metrics_to_show = [
            (sales_label,             lambda c: c.get("Sales")),
            ("受注高 (百万)",          lambda c: c.get("OrderIntake")),
            ("受注残高 (百万)",        lambda c: c.get("OrderBacklog")),
            (gross_profit_label,       lambda c: c.get("GrossProfit")),
            (gross_profit_margin_label, lambda c: c.get("GrossProfitMargin")),
            (op_label,                lambda c: c.get("OP")),
            (op_margin_label,         get_op_margin),
            ("販管費 (百万)",          lambda c: c.get("SellingGeneralAdministrativeExpenses")),
            ("営業利益前年差",          lambda c: c.get("OperatingProfitChange")),
            ("売上差影響",             lambda c: c.get("SalesChangeImpact")),
            (gross_margin_change_label, lambda c: c.get("GrossMarginChangeImpact")),
            ("販管費増影響",           lambda c: c.get("SGAChangeImpact")),
            ("ROE (%)",               lambda c: c.get("ROE")),
            ("ROIC (%)",              lambda c: c.get("ROIC")),
            ("総資産 (百万)",           lambda c: c.get("TotalAssets")),
            ("流動資産 (百万)",         lambda c: c.get("CurrentAssets")),
            ("固定資産 (百万)",         lambda c: c.get("NonCurrentAssets")),
            ("流動負債 (百万)",         lambda c: c.get("CurrentLiabilities")),
            ("固定負債 (百万)",         lambda c: c.get("NonCurrentLiabilities")),
            ("純資産 (百万)",           lambda c: c.get("NetAssets")),
            ("営業CF (百万)",          lambda c: c.get("CFO")),
            ("投資CF (百万)",          lambda c: c.get("CFI")),
            ("フリーCF (百万)",        lambda c: c.get("CFC")),
            ("減価償却費 (百万)",      lambda c: c.get("DepreciationAmortization")),
            ("配当性向 (%)",           lambda c: c.get("PayoutRatio")),
            # ── 税引前利益・実効税率 ──
            ("実効税率 (%)",            lambda c: c.get("EffectiveTaxRate")),
            # ── WACC（暫定: β=1.0, MRP=5.5%, Rf=10年国債利回り） ──
            ("株主資本コスト (%)",      lambda c: c.get("CostOfEquity")),
            ("負債コスト (%)",          lambda c: c.get("CostOfDebt")),
            ("WACC (%)",               lambda c: c.get("WACC") if c.get("WACC") is not None else c.get("WACCLabel")),
            # ── 有利子負債・支払利息 ──
            ("有利子負債合計 (百万)",   lambda c: c.get("InterestBearingDebt")),
            ("支払利息 (百万)",         lambda c: c.get("InterestExpense")),
            ("投下資本 (百万)",         lambda c: (c.get("InterestBearingDebt") + c.get("NetAssets")) if c.get("InterestBearingDebt") is not None and c.get("NetAssets") is not None else None),
            # ── 従業員数 ──
            ("従業員数 (人)",           lambda c: c.get("Employees"),   "int"),
            ("DocID",                  lambda c: c.get("DocID")),
        ]

        for metric_def in metrics_to_show:
            label, func = metric_def[0], metric_def[1]
            fmt_hint = metric_def[2] if len(metric_def) > 2 else None
            values = [func(p.get("CalculatedData", {})) for p in periods]
            if all(v is None for v in values):
                continue
            row = [label]
            for val in values:
                if val is None:
                    row.append(f"{'-':>10}")
                elif isinstance(val, str):
                    row.append(f"{val:>10}")
                elif fmt_hint == "int":
                    row.append(f"{int(val):>10,}")
                else:
                    row.append(f"{val:>10.2f}")
            print(row_format.format(*row), file=sys.stderr)

        print("-" * (16 + 11 * len(periods)), file=sys.stderr)

        print("\n定性情報は ticker filing コマンドで抽出できます。", file=sys.stderr)

        # ウォッチリスト追加の確認（対話端末のみ）
        if args.format == "table" and sys.stdin.isatty():
            from blue_ticker.services.portfolio_service import portfolio_service
            from blue_ticker.infrastructure.portfolio_store import portfolio_store as _ps
            all_entries = _ps.find_all_by_ticker(validate_stock_code(code))
            if not any(e.get("status") in ("watch", "holding") for e in all_entries):
                from blue_ticker.app.cli.ui import confirm
                if confirm(f"{code} {info['name']} をウォッチリストに追加しますか？ (y/N): "):
                    portfolio_service.add_watch(code, name=info.get("name", ""))
                    print(f"ウォッチリストに追加しました: {code} {info['name']}", file=sys.stderr)

    except ValueError as e:
        print(f"エラー: {e}", file=sys.stderr)
    except aiohttp.ClientError as e:
        print(f"エラー: {e}", file=sys.stderr)
        logger.exception(e)
    finally:
        await data_service.close()


async def cmd_filings(args):
    """EDINET書類一覧コマンド"""
    from blue_ticker.services.data_service import data_service

    try:
        code = validate_stock_code(args.code)
        years = getattr(args, "years", EDINET_FILINGS_DEFAULT_YEARS)
        if years <= 0:
            print("エラー: years には正の整数を指定してください。", file=sys.stderr)
            return
        docs = await data_service.search_filings(
            code,
            max_years=years,
            doc_types=["120", "130", "140", "150", "160", "170"],
            max_documents=10,
        )
        if not docs:
            print(f"書類が見つかりませんでした: {code}", file=sys.stderr)
            return
        if args.format == "json":
            print(json.dumps(docs, indent=2, ensure_ascii=False))
        else:
            print(f"\n[EDINET書類一覧] {code} ({len(docs)}件)", file=sys.stderr)
            print("-" * 80, file=sys.stderr)
            print(f"{'書類ID':<16} {'種別':<6} {'提出日時':<20} {'書類名'}", file=sys.stderr)
            print("-" * 80, file=sys.stderr)
            for doc in docs:
                print(
                    f"{doc.get('docID',''):<16}"
                    f" {doc.get('docTypeCode',''):<6}"
                    f" {doc.get('submitDateTime',''):<20}"
                    f" {doc.get('docDescription','')}",
                    file=sys.stderr,
                )
            print("-" * 80, file=sys.stderr)
    except ValueError as e:
        print(f"エラー: {e}", file=sys.stderr)
    except aiohttp.ClientError as e:
        print(f"エラー: {e}", file=sys.stderr)
        logger.exception(e)
    finally:
        await data_service.close()


async def cmd_filing(args):
    """EDINET書類抽出コマンド"""
    from blue_ticker.services.data_service import data_service

    try:
        code = validate_stock_code(args.code)
        doc_id = getattr(args, "doc_id", None)
        sections = getattr(args, "sections", None) or []
        result = await data_service.extract_filing_content(
            code,
            doc_id=doc_id or None,
            sections=sections or None,
        )
        if args.format == "json":
            print(json.dumps(result, indent=2, ensure_ascii=False))
        else:
            if result.get("doc_id"):
                print(f"doc_id:      {result['doc_id']}", file=sys.stderr)
            if result.get("fiscal_year"):
                print(f"fiscal_year: {result['fiscal_year']}", file=sys.stderr)
            if result.get("period_type"):
                print(f"period_type: {result['period_type']}", file=sys.stderr)
            if result.get("edinet_fy_end"):
                print(f"fy_end:      {result['edinet_fy_end']}", file=sys.stderr)
            secs = result.get("sections", {})
            if not secs:
                print("セクションデータが見つかりませんでした。", file=sys.stderr)
                return
            for sec_name, sec_text in secs.items():
                print(f"\n[{sec_name}]", file=sys.stderr)
                print("-" * 60, file=sys.stderr)
                text = sec_text if isinstance(sec_text, str) else json.dumps(sec_text, ensure_ascii=False)
                print(text[:2000] + ("..." if len(text) > 2000 else ""), file=sys.stderr)
    except ValueError as e:
        print(f"エラー: {e}", file=sys.stderr)
    except aiohttp.ClientError as e:
        print(f"エラー: {e}", file=sys.stderr)
        logger.exception(e)
    finally:
        await data_service.close()
