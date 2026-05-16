from typing import TYPE_CHECKING

from .main import main

if TYPE_CHECKING:
    from .parser import build_parser
    from .analyze import cmd_analyze, cmd_search, cmd_filings, cmd_filing
    from .config import cmd_config
    from blue_ticker.infrastructure.settings import settings_store

__all__ = [
    "main",
    "build_parser",
    "cmd_analyze",
    "cmd_search",
    "cmd_filings",
    "cmd_filing",
    "cmd_config",
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
    if name == "settings_store":
        from blue_ticker.infrastructure.settings import settings_store

        return settings_store
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
