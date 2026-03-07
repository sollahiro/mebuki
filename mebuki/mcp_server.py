import logging
import json
import asyncio
from typing import Optional, List, Dict, Any
from mcp.server import Server
from mcp.types import Tool, TextContent, ImageContent, EmbeddedResource
from mcp.server.stdio import stdio_server

from backend.services.data_service import data_service
from backend.services.macro_analyzer import macro_analyzer
from backend.settings import settings_store
from backend.prompts import LLM_PROMPTS
from backend.utils.helpers import validate_stock_code

# ロギング設定
logger = logging.getLogger("mebuki-mcp")

# MCP サーバーの初期化
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
                    "query": {"type": "string", "description": "Company name or partial code."},
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
                    "code": {"type": "string", "description": "Four-digit or five-digit Japanese stock code."},
                    "scope": {
                        "type": "string", 
                        "enum": ["overview", "history", "metrics", "raw"],
                        "default": "overview",
                        "description": "Scope of data: 'overview' (default), 'history' (10y series), 'metrics' (calculated ratios), or 'raw' (J-QUANTS data)."
                    },
                    "use_cache": {"type": "boolean", "default": True}
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
                    "code": {"type": "string", "description": "Four-digit or five-digit Japanese stock code."},
                    "days": {"type": "number", "description": "Number of days to fetch (default: 365)"},
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
                    "code": {"type": "string", "description": "Four-digit or five-digit Japanese stock code."},
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
                    "code": {"type": "string", "description": "Four-digit or five-digit Japanese stock code. If doc_id is not provided, uses the latest Securities Report."},
                    "doc_id": {"type": "string", "description": "Optional: Document ID obtained from search_japan_stock_filings."},
                    "sections": {
                        "type": "array",
                        "items": { "type": "string" },
                        "description": "Sections to extract. e.g., ['business_risks', 'mda', 'management_policy']. Default is 'all'."
                    }
                },
                "required": ["code"],
            },
        ),
        Tool(
            name="get_macro_economic_data",
            description="Fetch macro economic indicators for Japan environment. 日本のマクロ経済指標（為替、金融政策、コストプッシュ圧力）を取得します。",
            inputSchema={
                "type": "object",
                "properties": {
                    "category": {
                        "type": "string",
                        "enum": ["fx", "monetary", "cost_push"],
                        "description": "Category of macro data."
                    },
                    "sector": {"type": "string", "description": "Required for 'cost_push': Industry sector code (e.g., 'transportation_equipment')."},
                    "start_date": {"type": "string", "description": "Start date (Format: YYYYMM)"},
                    "end_date": {"type": "string", "description": "End date (Format: YYYYMM)"},
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
                    "code": {"type": "string", "description": "Four-digit or five-digit Japanese stock code."},
                },
                "required": ["code"],
            },
        )
    ]

@app.call_tool()
async def call_tool(name: str, arguments: Dict[str, Any]) -> List[TextContent]:
    """ツールの実行を処理します。"""
    try:
        # 1. 検索
        if name == "find_japan_stock_code":
            query = str(arguments["query"])
            data = await data_service.search_companies(query)
            return [TextContent(type="text", text=json.dumps(data, indent=2, ensure_ascii=False))]

        # 2. 財務データ取得 (統合)
        elif name == "get_japan_stock_financial_data":
            code = validate_stock_code(str(arguments["code"]))
            scope = arguments.get("scope", "overview")
            use_cache = arguments.get("use_cache", True)

            if scope == "overview" or scope == "history":
                analyzer = data_service.get_analyzer(use_cache=use_cache)
                result = await analyzer.analyze_stock(code)
                if scope == "history" and result:
                    result["history"] = result.get("metrics", {}).get("years", [])
                return [TextContent(type="text", text=json.dumps(result, indent=2, ensure_ascii=False))]
            
            elif scope == "metrics":
                analyzer = data_service.get_analyzer(use_cache=use_cache)
                stock_info, financial_data, annual_data = await asyncio.to_thread(analyzer._fetch_financial_data, code)
                if not annual_data:
                    raise ValueError("Financial data not found")
                analysis_years = min(len(annual_data), settings_store.get_max_analysis_years())
                prices = await asyncio.to_thread(analyzer._fetch_prices, code, annual_data, analysis_years)
                metrics = await asyncio.to_thread(analyzer._calculate_metrics, code, annual_data, prices, analysis_years)
                return [TextContent(type="text", text=json.dumps(metrics, indent=2, ensure_ascii=False))]
            
            elif scope == "raw":
                raw_data = await asyncio.to_thread(data_service.api_client.get_financial_summary, code=code)
                cleaned_data = [{k: v for k, v in record.items() if v is not None and v != ""} for record in raw_data]
                return [TextContent(type="text", text=json.dumps(cleaned_data, indent=2, ensure_ascii=False))]
            
            raise ValueError(f"Invalid scope: {scope}")

        # 3. 株価データ
        elif name == "get_japan_stock_price_data":
            code = validate_stock_code(str(arguments["code"]))
            days = int(arguments.get("days", 365))
            from datetime import datetime, timedelta
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days)
            data = await asyncio.to_thread(
                data_service.api_client.get_daily_bars,
                code=code,
                from_date=start_date.strftime("%Y-%m-%d"),
                to_date=end_date.strftime("%Y-%m-%d")
            )
            return [TextContent(type="text", text=json.dumps(data, indent=2, ensure_ascii=False))]

        # 4. 書類検索
        elif name == "search_japan_stock_filings":
            code = validate_stock_code(str(arguments["code"]))
            fin_data = await asyncio.to_thread(data_service.api_client.get_financial_summary, code=code)
            docs = await asyncio.to_thread(
                data_service.edinet_client.search_recent_reports,
                code=code,
                jquants_data=fin_data,
                max_years=10,
                doc_types=["120", "130", "140", "150", "160", "170"],
                max_documents=10
            )
            return [TextContent(type="text", text=json.dumps(docs, indent=2, ensure_ascii=False))]

        # 5. 書類内容抽出 (統合)
        elif name == "extract_japan_stock_filing_content":
            code = validate_stock_code(str(arguments["code"]))
            doc_id = arguments.get("doc_id")
            requested_sections = arguments.get("sections", ["all"])
            
            if not doc_id:
                # doc_idがない場合は最新の有報を探す
                fin_data = await asyncio.to_thread(data_service.api_client.get_financial_summary, code=code)
                docs = await asyncio.to_thread(
                    data_service.edinet_client.search_recent_reports,
                    code=code,
                    jquants_data=fin_data,
                    max_years=5,
                    doc_types=["120", "140"], # 有価証券報告書
                    max_documents=5
                )
                if not docs:
                    raise ValueError(f"No Securities Report found for {code}")
                doc_id = docs[0]["docID"]

            xbrl_dir = await asyncio.to_thread(data_service.edinet_client.download_document, doc_id, doc_type=1)
            if not xbrl_dir:
                raise ValueError("Document not found or download failed")
                
            from mebuki.analysis.xbrl_parser import XBRLParser
            parser = XBRLParser()
            all_sections = parser.extract_sections_by_type(xbrl_dir)
            
            result = {}
            if "all" in requested_sections:
                result = all_sections
            else:
                for s in requested_sections:
                    if s in all_sections:
                        result[s] = all_sections[s]
            
            return [TextContent(type="text", text=json.dumps({"sections": result}, indent=2, ensure_ascii=False))]

        # 6. マクロデータ (統合)
        elif name == "get_macro_economic_data":
            category = arguments["category"]
            start = arguments.get("start_date")
            end = arguments.get("end_date")
            
            if category == "fx":
                data = macro_analyzer.get_fx_environment(start, end)
            elif category == "monetary":
                data = macro_analyzer.get_monetary_policy_status(start, end)
            elif category == "cost_push":
                if "sector" not in arguments:
                    raise ValueError("'sector' is required for cost_push category")
                data = macro_analyzer.get_cost_environment(arguments["sector"], start, end)
            else:
                raise ValueError(f"Unknown macro category: {category}")
                
            return [TextContent(type="text", text=json.dumps(data, indent=2, ensure_ascii=False))]

        # 7. 可視化
        elif name == "visualize_financial_data":
            code = validate_stock_code(str(arguments["code"]))
            analyzer = data_service.get_analyzer(use_cache=True)
            result = await analyzer.analyze_stock(code)
            return [TextContent(type="text", text=json.dumps(result, indent=2, ensure_ascii=False))]

        else:
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
            app.create_initialization_options()
        )

if __name__ == "__main__":
    asyncio.run(serve())
