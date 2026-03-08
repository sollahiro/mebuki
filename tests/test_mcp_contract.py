import asyncio

from mebuki.app import mcp_server


def test_mcp_tool_contract_shape():
    tools = asyncio.run(mcp_server.list_tools())
    tool_names = [tool.name for tool in tools]

    expected = {
        "find_japan_stock_code",
        "get_japan_stock_financial_data",
        "get_japan_stock_price_data",
        "search_japan_stock_filings",
        "extract_japan_stock_filing_content",
        "get_macro_economic_data",
        "visualize_financial_data",
    }
    assert set(tool_names) == expected

    for tool in tools:
        assert tool.inputSchema["type"] == "object"
        assert "required" in tool.inputSchema
        assert isinstance(tool.inputSchema["required"], list)
