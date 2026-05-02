import asyncio

from mebuki.app import mcp_server


def test_mcp_tool_contract_shape():
    tools = asyncio.run(mcp_server.list_tools())
    tool_names = [tool.name for tool in tools]

    expected = {
        "find_japan_stock_code",
        "get_japan_stock_financial_data",
        "search_japan_stock_filings",
        "extract_japan_stock_filing_content",
        "get_japan_stock_cache_stats",
        "get_japan_stock_watchlist",
        "manage_japan_stock_watchlist",
        "get_japan_stock_portfolio",
        "manage_japan_stock_portfolio",
        "search_japan_stocks_by_sector",
    }
    assert set(tool_names) == expected

    for tool in tools:
        assert tool.inputSchema["type"] == "object"
        assert "required" in tool.inputSchema
        assert isinstance(tool.inputSchema["required"], list)
