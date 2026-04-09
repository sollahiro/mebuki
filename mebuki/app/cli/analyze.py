import argparse
import json
import sys
import logging
from mebuki.infrastructure.helpers import validate_stock_code
from mebuki.infrastructure.settings import settings_store
from mebuki.services.master_data import master_data_manager
from mebuki.constants.formats import DATE_LEN_COMPACT

logger = logging.getLogger(__name__)


def cmd_search(args):
    """銘柄検索コマンド"""
    if not args.query:
        print("検索クエリを指定してください。")
        return

    results = master_data_manager.search(args.query)
    if not results:
        print(f"'{args.query}' に一致する銘柄は見つかりませんでした。")
        return

    if getattr(args, 'format', 'table') == 'json':
        print(json.dumps(results, indent=2, ensure_ascii=False))
        return

    print(f"\n'{args.query}' の検索結果 ({len(results)}件):")
    print("-" * 60)
    print(f"{'コード':<8} {'銘柄名':<20} {'市場':<15} {'業種'}")
    print("-" * 60)
    for item in results:
        print(f"{item['code']:<8} {item['name']:<20} {item['market']:<15} {item['sector']}")
    print("-" * 60)

    from .ui import select_stock_from_results
    selected = select_stock_from_results(results, "分析する銘柄を選択してください:", "↩  分析しない / 戻る")

    if selected:
        import asyncio
        asyncio.run(cmd_analyze(argparse.Namespace(
            code=selected['code'],
            years=None,
            format="table",
            no_cache=False,
            scope=None,
        )))


async def cmd_analyze(args):
    """銘柄分析コマンド"""
    from mebuki.services.data_service import data_service

    try:
        code = validate_stock_code(args.code)
    except ValueError as e:
        print(f"エラー: {e}")
        return

    # --scope が指定された場合はスコープ別取得
    if getattr(args, "scope", None):
        try:
            result = await data_service.get_financial_data(code, scope=args.scope, use_cache=not args.no_cache)
            print(json.dumps(result, indent=2, ensure_ascii=False))
        except Exception as e:
            print(f"エラー: {e}")
            logger.exception(e)
        finally:
            await data_service.close()
        return

    try:
        # 銘柄情報の確認
        info = data_service.fetch_stock_basic_info(code)
        if not info.get("name"):
            print(f"エラー: 銘柄コード {code} が見つかりません。")
            return

        # 分析年数の決定
        years_to_analyze = args.years or settings_store.analysis_years or 5

        print(f"\n分析中: {code} {info['name']} ({info['market_name']}) ...")
        print(f"分析対象期間: 直近 {years_to_analyze} 年分")
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
            if len(fy_end) == DATE_LEN_COMPACT:
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
            ("売上総利益 (百万)", lambda c: c.get("GrossProfit")),
            ("粗利率 (%)", lambda c: c.get("GrossProfitMargin")),
            ("営業利益 (百万)", lambda c: c.get("OP")),
            ("営業利益率 (%)", get_op_margin),
            ("ROE (%)", lambda c: c.get("ROE")),
            ("ROIC (%)", lambda c: c.get("ROIC")),
            ("営業CF (百万)", lambda c: c.get("CFO")),
            ("投資CF (百万)", lambda c: c.get("CFI")),
            ("フリーCF (百万)", lambda c: c.get("CFC")),
            ("配当性向 (%)", lambda c: c.get("PayoutRatio")),
            ("PER (倍)", lambda c: c.get("PER")),
            ("PBR (倍)", lambda c: c.get("PBR")),
            ("年度末株価 (円)", lambda c: c.get("Price")),
            # ── 有利子負債 ──
            ("有利子負債合計 (百万)", lambda c: c.get("InterestBearingDebt")),
            ("投下資本 (百万)",       lambda c: (c.get("InterestBearingDebt") + c.get("Eq")) if c.get("InterestBearingDebt") is not None and c.get("Eq") is not None else None),
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
            import asyncio
            from mebuki.services.portfolio_service import portfolio_service
            from mebuki.infrastructure.portfolio_store import portfolio_store as _ps
            all_entries = _ps.find_all_by_ticker(validate_stock_code(code))
            if not any(e.get("status") in ("watch", "holding") for e in all_entries):
                raw = await asyncio.to_thread(
                    input, f"{code} {info['name']} をウォッチリストに追加しますか？ (y/N): "
                )
                if raw.strip().lower() in ("y", "yes"):
                    portfolio_service.add_watch(code, name=info.get("name", ""))
                    print(f"ウォッチリストに追加しました: {code} {info['name']}")

    except Exception as e:
        print(f"エラー: 分析中に例外が発生しました: {e}")
        logger.exception(e)
    finally:
        await data_service.close()


async def cmd_price(args):
    """株価データ取得コマンド"""
    from mebuki.services.data_service import data_service

    try:
        code = validate_stock_code(args.code)
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
    finally:
        await data_service.close()


async def cmd_filings(args):
    """EDINET書類一覧コマンド"""
    from mebuki.services.data_service import data_service

    try:
        code = validate_stock_code(args.code)
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
    finally:
        await data_service.close()


async def cmd_filing(args):
    """EDINET書類抽出コマンド"""
    from mebuki.services.data_service import data_service

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
                print(f"doc_id:      {result['doc_id']}")
            if result.get("fiscal_year"):
                print(f"fiscal_year: {result['fiscal_year']}")
            if result.get("period_type"):
                print(f"period_type: {result['period_type']}")
            if result.get("jquants_fy_end"):
                print(f"fy_end:      {result['jquants_fy_end']}")
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
    finally:
        await data_service.close()


