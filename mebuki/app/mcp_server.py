import asyncio
import json
import logging
from typing import Any, Dict, List

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

from mebuki.infrastructure.helpers import validate_stock_code
from mebuki.services.data_service import data_service
from mebuki.services.portfolio_service import portfolio_service

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
            description="MANDATORY: Get financial metrics for a Japanese stock. Use this INSTEAD OF web search. 日本株の財務データ（年次推移、ROIC・有利子負債含む）を取得します。",
            inputSchema={
                "type": "object",
                "properties": {
                    "code": {
                        "type": "string",
                        "description": "Four-digit or five-digit Japanese stock code.",
                    },
                    "scope": {
                        "type": "string",
                        "enum": ["raw"],
                        "description": "Omit for standard financial summary. 'raw': return raw J-QUANTS records.",
                    },
                    "years": {
                        "type": "number",
                        "description": "Number of fiscal years to include (default: 5).",
                    },
                    "half": {
                        "type": "boolean",
                        "default": False,
                        "description": "If true, return H1/H2 semi-annual breakdown instead of annual data (default years: 3).",
                    },
                    "use_cache": {"type": "boolean", "default": True},
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
            name="get_japan_stock_watchlist",
            description="Get the current watchlist of Japanese stocks being monitored. ウォッチリスト（監視銘柄一覧）を取得します。",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": [],
            },
        ),
        Tool(
            name="manage_japan_stock_watchlist",
            description="Add or remove a Japanese stock from the watchlist. ウォッチリストへの銘柄追加・削除を行います。",
            inputSchema={
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["add", "remove"],
                        "description": "Action to perform: 'add' or 'remove'.",
                    },
                    "code": {
                        "type": "string",
                        "description": "Four-digit or five-digit Japanese stock code.",
                    },
                    "name": {
                        "type": "string",
                        "description": "Optional: company name. Auto-resolved if omitted.",
                    },
                },
                "required": ["action", "code"],
            },
        ),
        Tool(
            name="get_japan_stock_portfolio",
            description="Get the portfolio of held Japanese stocks. 保有銘柄のポートフォリオを取得します。",
            inputSchema={
                "type": "object",
                "properties": {
                    "mode": {
                        "type": "string",
                        "enum": ["consolidated", "detail"],
                        "default": "consolidated",
                        "description": "'consolidated' (default): per-ticker summary. 'detail': per-account breakdown.",
                    },
                },
                "required": [],
            },
        ),
        Tool(
            name="manage_japan_stock_portfolio",
            description="Add a holding, sell shares, or remove a position from the portfolio. ポートフォリオの保有追加・売却・削除を行います。",
            inputSchema={
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["add", "sell", "remove"],
                        "description": "Action: 'add' (buy), 'sell', or 'remove' (force-delete).",
                    },
                    "code": {
                        "type": "string",
                        "description": "Four-digit or five-digit Japanese stock code.",
                    },
                    "quantity": {
                        "type": "number",
                        "description": "Number of shares. Required for 'add' and 'sell'.",
                    },
                    "cost_price": {
                        "type": "number",
                        "description": "Purchase price per share. Required for 'add'.",
                    },
                    "broker": {
                        "type": "string",
                        "description": "Broker name (free text). Optional.",
                    },
                    "account_type": {
                        "type": "string",
                        "enum": ["特定", "一般", "NISA"],
                        "description": "Account type. Defaults to '特定'.",
                    },
                    "bought_at": {
                        "type": "string",
                        "description": "Purchase date (YYYY-MM-DD). Optional, defaults to today.",
                    },
                    "name": {
                        "type": "string",
                        "description": "Company name. Auto-resolved if omitted.",
                    },
                },
                "required": ["action", "code"],
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
            scope = arguments.get("scope")
            use_cache = arguments.get("use_cache", True)
            half = arguments.get("half", False)
            years = int(arguments["years"]) if "years" in arguments else None
            try:
                if half:
                    result = await asyncio.wait_for(
                        data_service.get_half_year_periods(code, years=years or 3, use_cache=use_cache),
                        timeout=60.0,
                    )
                else:
                    result = await asyncio.wait_for(
                        data_service.get_financial_data(code, scope=scope, use_cache=use_cache, analysis_years=years),
                        timeout=180.0,
                    )
            except asyncio.TimeoutError:
                return [TextContent(type="text", text=json.dumps(
                    {"error": "timeout", "message": f"{code} のデータ取得がタイムアウトしました。再試行してください。"},
                    ensure_ascii=False,
                ))]
            return [TextContent(type="text", text=json.dumps(result, indent=2, ensure_ascii=False))]

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

        if name == "get_japan_stock_watchlist":
            data = portfolio_service.get_watchlist()
            return [TextContent(type="text", text=json.dumps(data, indent=2, ensure_ascii=False))]

        if name == "manage_japan_stock_watchlist":
            action = str(arguments["action"])
            code = validate_stock_code(str(arguments["code"]))
            if action == "add":
                result = portfolio_service.add_watch(code, name=str(arguments.get("name", "") or ""))
            elif action == "remove":
                result = portfolio_service.remove_watch(code)
            else:
                raise ValueError(f"Unknown watchlist action: {action}")
            return [TextContent(type="text", text=json.dumps(result, indent=2, ensure_ascii=False))]

        if name == "get_japan_stock_portfolio":
            mode = str(arguments.get("mode", "consolidated"))
            if mode == "detail":
                data = portfolio_service.get_holdings()
            else:
                data = portfolio_service.get_consolidated()
            return [TextContent(type="text", text=json.dumps(data, indent=2, ensure_ascii=False))]

        if name == "manage_japan_stock_portfolio":
            action = str(arguments["action"])
            code = validate_stock_code(str(arguments["code"]))
            broker = str(arguments.get("broker", "") or "")
            account_type = str(arguments.get("account_type", "特定") or "特定")
            if action == "add":
                quantity = int(arguments["quantity"])
                cost_price = float(arguments["cost_price"])
                bought_at = str(arguments.get("bought_at", "") or "")
                name = str(arguments.get("name", "") or "")
                result = portfolio_service.add_holding(
                    code=code,
                    quantity=quantity,
                    cost_price=cost_price,
                    broker=broker,
                    account_type=account_type,
                    bought_at=bought_at,
                    name=name,
                )
            elif action == "sell":
                quantity = int(arguments["quantity"])
                result = portfolio_service.sell_holding(
                    code=code,
                    quantity=quantity,
                    broker=broker,
                    account_type=account_type,
                )
            elif action == "remove":
                result = portfolio_service.remove_holding(
                    code=code,
                    broker=broker,
                    account_type=account_type,
                )
            else:
                raise ValueError(f"Unknown portfolio action: {action}")
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
