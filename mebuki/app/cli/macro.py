import json
import logging

logger = logging.getLogger(__name__)


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
