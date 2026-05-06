import sys
import logging
from pathlib import Path
from .parser import build_parser

logger = logging.getLogger(__name__)


def _print_legacy_command_notice() -> None:
    invoked_name = Path(sys.argv[0]).name
    if invoked_name == "mebuki":
        print(
            "注意: `mebuki` コマンドは非推奨です。今後は `ticker` または `blt` を使ってください。",
            file=sys.stderr,
        )


def main() -> int:
    parser = build_parser()

    try:
        _print_legacy_command_notice()

        if len(sys.argv) == 1:
            parser.print_help()
            return 0

        args = parser.parse_args()

        if args.command == "search":
            from .analyze import cmd_search

            cmd_search(args)
        elif args.command == "analyze":
            import asyncio
            from .analyze import cmd_analyze

            asyncio.run(cmd_analyze(args))
        elif args.command == "config":
            from .config import cmd_config

            cmd_config(args, parser)
        elif args.command == "cache":
            from .cache import cmd_cache

            cmd_cache(args, parser)
        elif args.command == "mcp":
            from .mcp import cmd_mcp

            cmd_mcp(args, parser)
        elif args.command == "filings":
            import asyncio
            from .analyze import cmd_filings

            asyncio.run(cmd_filings(args))
        elif args.command == "filing":
            import asyncio
            from .analyze import cmd_filing

            asyncio.run(cmd_filing(args))
        elif args.command == "sector":
            from .sector import cmd_sector

            cmd_sector(args)
        elif args.command == "watch":
            from .portfolio import cmd_watch

            cmd_watch(args)
        elif args.command == "portfolio":
            from .portfolio import cmd_portfolio

            cmd_portfolio(args)
        else:
            parser.print_help()
        return 0
    except KeyboardInterrupt:
        print("\n中断しました。", file=sys.stderr)
        return 130


if __name__ == "__main__":
    sys.exit(main())
