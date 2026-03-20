import sys
import logging
from .ui import print_banner
from .analyze import cmd_search, cmd_analyze, cmd_price, cmd_filings, cmd_filing, cmd_visualize
from .macro import cmd_macro
from .config import cmd_config
from .mcp import cmd_mcp
from .portfolio import cmd_watch, cmd_portfolio
from .interactive import cmd_interactive
from .parser import build_parser

logger = logging.getLogger(__name__)


def main():
    if len(sys.argv) == 1:
        print_banner()
        try:
            cmd_interactive()
        except KeyboardInterrupt:
            print("\n終了します。")
        return

    print_banner()
    parser = build_parser()

    args = parser.parse_args()

    if args.command == "search":
        cmd_search(args)
    elif args.command == "analyze":
        import asyncio
        asyncio.run(cmd_analyze(args))
    elif args.command == "config":
        cmd_config(args, parser)
    elif args.command == "mcp":
        cmd_mcp(args, parser)
    elif args.command == "price":
        import asyncio
        asyncio.run(cmd_price(args))
    elif args.command == "filings":
        import asyncio
        asyncio.run(cmd_filings(args))
    elif args.command == "filing":
        import asyncio
        asyncio.run(cmd_filing(args))
    elif args.command == "macro":
        cmd_macro(args)
    elif args.command == "visualize":
        import asyncio
        asyncio.run(cmd_visualize(args))
    elif args.command == "watch":
        cmd_watch(args)
    elif args.command == "portfolio":
        cmd_portfolio(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
