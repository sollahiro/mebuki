import json
import sys

from mebuki.infrastructure.settings import settings_store
from mebuki.services.cache_pruner import CachePruner


def cmd_cache(args, parser) -> None:
    """キャッシュ管理コマンド"""
    if args.cache_subcommand == "prune":
        pruner = CachePruner(settings_store.cache_dir)
        summary = pruner.prune(
            dry_run=not args.execute,
            include_boj=not args.keep_boj,
            edinet_search_days=args.edinet_search_days,
            edinet_xbrl_days=args.edinet_xbrl_days,
        )
        data = summary.to_dict()
        if args.format == "json":
            print(json.dumps(data, indent=2, ensure_ascii=False))
            return

        mode = "dry-run" if data["dry_run"] else "executed"
        mb = data["freed_bytes"] / 1024 / 1024
        print(f"cache prune ({mode})", file=sys.stderr)
        print(f"  removed files: {data['removed_files']}", file=sys.stderr)
        print(f"  removed dirs:  {data['removed_dirs']}", file=sys.stderr)
        print(f"  freed:         {mb:.2f} MB", file=sys.stderr)
        return

    parser.print_help()
