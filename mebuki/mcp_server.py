"""Backward-compatible MCP server entrypoint.

Deprecated internal path: use `mebuki.app.mcp_server` for new imports.
"""

from mebuki.app.mcp_server import app, call_tool, list_tools, serve  # noqa: F401


if __name__ == "__main__":
    import asyncio

    asyncio.run(serve())
