"""Backward-compatible CLI entrypoint.

Deprecated internal path: use `mebuki.app.cli` for new imports.
"""

from mebuki.app.cli import (  # noqa: F401
    build_parser,
    cmd_analyze,
    cmd_config,
    cmd_mcp,
    cmd_search,
    main,
    print_banner,
)


if __name__ == "__main__":
    main()
