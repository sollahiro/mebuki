import json
import sys
import asyncio
from pathlib import Path
from typing import Any

from mebuki.api.edinet_client import EdinetAPIClient
from mebuki.infrastructure.settings import settings_store
from mebuki.services.cache_pruner import CachePruner
from mebuki.services.edinet_smoke_cache import (
    prepare_edinet_smoke_cache,
    smoke_companies_from_codes,
)


async def _prepare_smoke_cache_async(api_key: str, cache_dir: str, codes: list[str] | None, initial_scan_days: int):
    companies = smoke_companies_from_codes(codes)
    client = EdinetAPIClient(
        api_key=api_key,
        cache_dir=str(Path(cache_dir) / "edinet"),
    )
    try:
        return await prepare_edinet_smoke_cache(
            client,
            companies,
            initial_scan_days=initial_scan_days,
        )
    finally:
        await client.close()


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
        print("  EDINET", file=sys.stderr)
        print(f"    searches:         {data['edinet_search_files']} ({_mb(data['edinet_search_bytes'])})", file=sys.stderr)
        print(f"    doc indexes:      {data['edinet_doc_index_files']} ({_mb(data['edinet_doc_index_bytes'])})", file=sys.stderr)
        print(f"    XBRL dirs:        {data['edinet_xbrl_dirs']} ({_mb(data['edinet_xbrl_bytes'])})", file=sys.stderr)
        print(f"    doc caches:       {data['edinet_docs_cache_files']} ({_mb(data['edinet_docs_cache_bytes'])})", file=sys.stderr)
        print(f"    parse caches:     {data['xbrl_parse_cache_files']} ({_mb(data['xbrl_parse_cache_bytes'])})", file=sys.stderr)
        print("  analysis", file=sys.stderr)
        print(f"    annual:           {data['individual_analysis_files']} ({_mb(data['individual_analysis_bytes'])})", file=sys.stderr)
        print(f"    half-year:        {data['half_year_analysis_files']} ({_mb(data['half_year_analysis_bytes'])})", file=sys.stderr)
        print(f"    MOF rates:        {data['mof_cache_files']} ({_mb(data['mof_cache_bytes'])})", file=sys.stderr)
        print(f"  unknown root json:  {data['unknown_root_json_files']}", file=sys.stderr)
        return

    if args.cache_subcommand == "audit":
        pruner = CachePruner(settings_store.cache_dir)
        data = pruner.audit().to_dict()
        if args.format == "json":
            print(json.dumps(data, indent=2, ensure_ascii=False))
            return

        print("cache audit", file=sys.stderr)
        print(f"  dir: {data['cache_dir']}", file=sys.stderr)
        for key, value in data.items():
            if key == "cache_dir" or not isinstance(value, list):
                continue
            print(f"  {key}: {len(value)}", file=sys.stderr)
            for name in value[:20]:
                print(f"    {name}", file=sys.stderr)
            if len(value) > 20:
                print(f"    ... ({len(value) - 20} more)", file=sys.stderr)
        return

    if args.cache_subcommand == "prune":
        pruner = CachePruner(settings_store.cache_dir)
        summary = pruner.prune(
            dry_run=not args.execute,
            edinet_search_days=args.edinet_search_days,
            edinet_xbrl_days=args.edinet_xbrl_days,
            edinet_doc_index_years=args.edinet_doc_index_years,
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

    if args.cache_subcommand == "prepare-smoke":
        if not settings_store.edinet_api_key:
            print("EDINET APIキーが未設定です。mebuki config set edinet-key <KEY> を実行してください。", file=sys.stderr)
            return
        summary = asyncio.run(
            _prepare_smoke_cache_async(
                settings_store.edinet_api_key,
                settings_store.cache_dir,
                args.codes,
                args.initial_scan_days,
            )
        )

        data = summary.to_dict()
        if args.format == "json":
            print(json.dumps(data, indent=2, ensure_ascii=False))
            return

        print("cache prepare-smoke", file=sys.stderr)
        print(f"  requested: {data['requested']}", file=sys.stderr)
        print(f"  prepared:  {data['prepared']}", file=sys.stderr)
        print(f"  skipped:   {data['skipped']}", file=sys.stderr)
        print(f"  failed:    {data['failed']}", file=sys.stderr)
        entries = data["entries"]
        if isinstance(entries, list):
            for entry in entries:
                if not isinstance(entry, dict):
                    continue
                _print_smoke_entry(entry)
        return

    parser.print_help()


def _print_smoke_entry(entry: dict[str, Any]) -> None:
    status = str(entry.get("status") or "-")
    code = str(entry.get("code") or "-")
    name = str(entry.get("name") or "-")
    doc_id = str(entry.get("doc_id") or "-")
    fy_end = str(entry.get("fy_end") or "-")
    print(f"  {status:<8} {code} {name} doc={doc_id} fy={fy_end}", file=sys.stderr)


def _mb(value: object) -> str:
    if isinstance(value, int):
        size = value
    elif isinstance(value, str) and value.isdigit():
        size = int(value)
    else:
        size = 0
    return f"{size / 1024 / 1024:.2f} MB"
