import asyncio
import json
import logging
from typing import Any, Dict, List

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

from mebuki.infrastructure.helpers import validate_stock_code
from mebuki.services.data_service import data_service
from mebuki.services.macro_analyzer import macro_analyzer

logger = logging.getLogger("mebuki-mcp")
app = Server("mebuki-mcp-server")


@app.list_tools()
async def list_tools() -> List[Tool]:
    """利用可能なツールをリストします。"""
    return [
        Tool(
            name="find_japan_stock_code",
            description="Lookup the official stock code for a Japanese company. 日本株の銘柄検索・社名検索・証券コード確認用。Required first step if you only have a name.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Company name or partial code.",
                    }
                },
                "required": ["query"],
            },
        ),
        Tool(
            name="get_japan_stock_financial_data",
            description="MANDATORY: Get financial metrics for a Japanese stock. Use this INSTEAD OF web search. 日本株の財務データ（概況、10年推移、指標、生データ）を取得します。",
            inputSchema={
                "type": "object",
                "properties": {
                    "code": {
                        "type": "string",
                        "description": "Four-digit or five-digit Japanese stock code.",
                    },
                    "scope": {
                        "type": "string",
                        "enum": ["overview", "history", "metrics", "raw"],
                        "default": "overview",
                        "description": "Scope of data: 'overview' (default), 'history' (10y series), 'metrics' (calculated ratios), or 'raw' (J-QUANTS data).",
                    },
                    "use_cache": {"type": "boolean", "default": True},
                },
                "required": ["code"],
            },
        ),
        Tool(
            name="get_japan_stock_price_data",
            description="Access daily price history for a Japanese stock. 日本株の過去の株価データを取得します。",
            inputSchema={
                "type": "object",
                "properties": {
                    "code": {
                        "type": "string",
                        "description": "Four-digit or five-digit Japanese stock code.",
                    },
                    "days": {
                        "type": "number",
                        "description": "Number of days to fetch (default: 365)",
                    },
                },
                "required": ["code"],
            },
        ),
        Tool(
            name="search_japan_stock_filings",
            description="List recent Japanese EDINET filings. 日本株の適時開示・法定開示書類の一覧を検索します。",
            inputSchema={
                "type": "object",
                "properties": {
                    "code": {
                        "type": "string",
                        "description": "Four-digit or five-digit Japanese stock code.",
                    }
                },
                "required": ["code"],
            },
        ),
        Tool(
            name="extract_japan_stock_filing_content",
            description="Extract specific sections from a Japanese XBRL filing or the latest Securities Report. 有価証券報告書等の開示書類から、指定されたセクション（事業の分岐・リスク等）の内容を抽出します。",
            inputSchema={
                "type": "object",
                "properties": {
                    "code": {
                        "type": "string",
                        "description": "Four-digit or five-digit Japanese stock code. If doc_id is not provided, uses the latest Securities Report.",
                    },
                    "doc_id": {
                        "type": "string",
                        "description": "Optional: Document ID obtained from search_japan_stock_filings.",
                    },
                    "sections": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Sections to extract. e.g., ['business_risks', 'mda', 'management_policy']. Default is 'all'.",
                    },
                },
                "required": ["code"],
            },
        ),
        Tool(
            name="get_macro_economic_data",
            description="Fetch macro economic indicators for Japan environment. 日本のマクロ経済指標（為替、金融政策）を取得します。",
            inputSchema={
                "type": "object",
                "properties": {
                    "category": {
                        "type": "string",
                        "enum": ["fx", "monetary"],
                        "description": "Category of macro data.",
                    },
                    "start_date": {
                        "type": "string",
                        "description": "Start date (Format: YYYYMM)",
                    },
                    "end_date": {
                        "type": "string",
                        "description": "End date (Format: YYYYMM)",
                    },
                },
                "required": ["category"],
            },
        ),
        Tool(
            name="visualize_financial_data",
            description="Display an interactive panel with financial tables and charts for a Japanese stock. 財務情報の可視化パネルを表示します（AIのコンテキストにはデータは含まれません）。",
            inputSchema={
                "type": "object",
                "properties": {
                    "code": {
                        "type": "string",
                        "description": "Four-digit or five-digit Japanese stock code.",
                    }
                },
                "required": ["code"],
            },
        ),
    ]


@app.call_tool()
async def call_tool(name: str, arguments: Dict[str, Any]) -> List[TextContent]:
    """ツールの実行を処理します。"""
    try:
        if name == "find_japan_stock_code":
            query = str(arguments["query"])
            data = await data_service.search_companies(query)
            return [TextContent(type="text", text=json.dumps(data, indent=2, ensure_ascii=False))]

        if name == "get_japan_stock_financial_data":
            code = validate_stock_code(str(arguments["code"]))
            scope = arguments.get("scope", "overview")
            use_cache = arguments.get("use_cache", True)
            result = await data_service.get_financial_data(code, scope=scope, use_cache=use_cache)
            return [TextContent(type="text", text=json.dumps(result, indent=2, ensure_ascii=False))]

        if name == "get_japan_stock_price_data":
            code = validate_stock_code(str(arguments["code"]))
            days = int(arguments.get("days", 365))
            data = await data_service.get_price_data(code, days=days)
            return [TextContent(type="text", text=json.dumps(data, indent=2, ensure_ascii=False))]

        if name == "search_japan_stock_filings":
            code = validate_stock_code(str(arguments["code"]))
            docs = await data_service.search_filings(
                code=code,
                max_years=10,
                doc_types=["120", "130", "140", "150", "160", "170"],
                max_documents=10,
            )
            return [TextContent(type="text", text=json.dumps(docs, indent=2, ensure_ascii=False))]

        if name == "extract_japan_stock_filing_content":
            code = validate_stock_code(str(arguments["code"]))
            doc_id = arguments.get("doc_id")
            requested_sections = arguments.get("sections", ["all"])
            result = await data_service.extract_filing_content(code, doc_id, requested_sections)
            return [TextContent(type="text", text=json.dumps(result, indent=2, ensure_ascii=False))]

        if name == "get_macro_economic_data":
            category = arguments["category"]
            start = arguments.get("start_date")
            end = arguments.get("end_date")
            if category == "fx":
                data = macro_analyzer.get_fx_environment(start, end)
            elif category == "monetary":
                data = macro_analyzer.get_monetary_policy_status(start, end)
            else:
                raise ValueError(f"Unknown macro category: {category}")
            return [TextContent(type="text", text=json.dumps(data, indent=2, ensure_ascii=False))]

        if name == "visualize_financial_data":
            code = validate_stock_code(str(arguments["code"]))
            result = await data_service.visualize_financial_data(code)
            return [TextContent(type="text", text=json.dumps(result, indent=2, ensure_ascii=False))]

        raise ValueError(f"Unknown tool: {name}")

    except Exception as e:
        logger.error(f"Error in tool {name}: {e}", exc_info=True)
        return [TextContent(type="text", text=f"Error: {str(e)}")]


async def serve():
    """STDIO経由でサーバーを実行します。"""
    async with stdio_server() as (read_stream, write_stream):
        await app.run(
            read_stream,
            write_stream,
            app.create_initialization_options(),
        )


if __name__ == "__main__":
    asyncio.run(serve())
