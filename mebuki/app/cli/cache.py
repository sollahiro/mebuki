import json
import sys

from mebuki.infrastructure.settings import settings_store
from mebuki.services.cache_pruner import CachePruner


def cmd_cache(args, parser) -> None:
    """キャッシュ管理コマンド"""
    if args.cache_subcommand == "stats":
        pruner = CachePruner(settings_store.cache_dir)
        data = pruner.stats().to_dict()
        if args.format == "json":
            print(json.dumps(data, indent=2, ensure_ascii=False))
            return

        mb = int(data["total_bytes"]) / 1024 / 1024
        print("cache stats", file=sys.stderr)
        print(f"  dir:                {data['cache_dir']}", file=sys.stderr)
        print(f"  total files:        {data['total_files']}", file=sys.stderr)
        print(f"  total dirs:         {data['total_dirs']}", file=sys.stderr)
        print(f"  total size:         {mb:.2f} MB", file=sys.stderr)
        print(f"  metadata entries:   {data['metadata_entries']}", file=sys.stderr)
        print(f"  root json files:    {data['root_json_files']}", file=sys.stderr)
        print(f"  EDINET searches:    {data['edinet_search_files']}", file=sys.stderr)
        print(f"  EDINET XBRL dirs:   {data['edinet_xbrl_dirs']}", file=sys.stderr)
        print(f"  BOJ files:          {data['boj_files']}", file=sys.stderr)
        print(f"  BOJ metadata keys:  {data['boj_metadata_entries']}", file=sys.stderr)
        print(f"  unknown root json:  {data['unknown_root_json_files']}", file=sys.stderr)
        return

    if args.cache_subcommand == "audit":
        pruner = CachePruner(settings_store.cache_dir)
        findings = [finding.to_dict() for finding in pruner.audit()]
        if args.format == "json":
            print(json.dumps({"findings": findings}, indent=2, ensure_ascii=False))
            return

        print("cache audit", file=sys.stderr)
        if not findings:
            print("  findings: 0", file=sys.stderr)
            return
        for finding in findings:
            mb = int(finding["bytes"]) / 1024 / 1024
            print(f"  [{finding['kind']}] {finding['target']} ({mb:.2f} MB)", file=sys.stderr)
            print(f"    {finding['message']}", file=sys.stderr)
        return

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
