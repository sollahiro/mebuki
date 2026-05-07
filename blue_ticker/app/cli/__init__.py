from typing import TYPE_CHECKING

from .main import main

if TYPE_CHECKING:
    from .parser import build_parser
    from .analyze import cmd_analyze, cmd_search, cmd_filings, cmd_filing
    from .config import cmd_config
    from .mcp import cmd_mcp
    from .portfolio import cmd_watch, cmd_portfolio
    from blue_ticker.infrastructure.settings import settings_store

__all__ = [
    "main",
    "build_parser",
    "cmd_analyze",
    "cmd_search",
    "cmd_filings",
    "cmd_filing",
    "cmd_config",
    "cmd_mcp",
    "cmd_watch",
    "cmd_portfolio",
]


def __getattr__(name: str) -> object:
    if name == "main":
        from .main import main

        return main
    if name == "build_parser":
        from .parser import build_parser

        return build_parser
    if name in {"cmd_analyze", "cmd_search", "cmd_filings", "cmd_filing"}:
        from . import analyze

        return getattr(analyze, name)
    if name == "cmd_config":
        from .config import cmd_config

        return cmd_config
    if name == "cmd_mcp":
        from .mcp import cmd_mcp

        return cmd_mcp
    if name in {"cmd_watch", "cmd_portfolio"}:
        from . import portfolio

        return getattr(portfolio, name)
    if name == "settings_store":
        from blue_ticker.infrastructure.settings import settings_store

        return settings_store
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
