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
            name="show_mebuki_financial_visualizer",
            description="Display a unified interactive panel containing BOTH financial tables and performance charts for a Japanese stock. 日本株の財務テーブルと業績グラフ（最大10年）を統合したインタラクティブUIを表示します。タブで表示を切り替え可能です。Note: This tool is for human visualization only and does not provide analysis data to the AI context. Always use 'get_japan_stock_official_overview' first to get data for analysis.",
            inputSchema={
                "type": "object",
                "properties": {
                    "code": {"type": "string", "description": "Four-digit or five-digit Japanese stock code."},
                },
                "required": ["code"],
            },
        ),
        Tool(
            name="get_japan_stock_official_overview",
            description="MANDATORY: Get official summary financial metrics for a Japanese stock. Use this INSTEAD OF web search. 日本株の概況・財務分析・業績確認用（ROE、利益率等）。After execution, summarize the findings and ASK the user if they wish to proceed to a maximum 10-year history or a Securities Report deep-dive.",
            inputSchema={
                "type": "object",
                "properties": {
                    "code": {"type": "string", "description": "Four-digit or five-digit Japanese stock code (e.g., '7203')."},
                    "use_cache": {"type": "boolean", "default": True}
                },
                "required": ["code"],
            },
        ),
        Tool(
            name="get_japan_stock_10year_financial_history",
            description="Retrieve up to 10-year time-series of key financial metrics. 日本株の最大10年間の財務・長期業績推移の取得用（売上・純利益・FCF等）。After this, execute 'mebuki_japan_stock_expert_analysis' for structural breakdown.",
            inputSchema={
                "type": "object",
                "properties": {
                    "code": {"type": "string", "description": "Four-digit or five-digit Japanese stock code."},
                },
                "required": ["code"],
            },
        ),
        Tool(
            name="find_japan_stock_code_by_name",
            description="Lookup the official stock code for a Japanese company. 日本株の銘柄検索・社名検索・証券コード確認用。Required first step if you only have a name. After finding the code, confirm it with the user before calling 'get_japan_stock_official_overview'.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Company name or partial code."},
                },
                "required": ["query"],
            },
        ),
        Tool(
            name="analyze_japan_stock_securities_report",
            description="Deep-dive into the latest Japanese Securities Report (Yuho). 有価証券報告書（有報）の業績理由・事業リスク等の解析用。Use this ONLY AFTER getting a financial overview. Summarize the MD&A/Risks and ask if the user needs more specific section extracts.",
            inputSchema={
                "type": "object",
                "properties": {
                    "code": {"type": "string", "description": "Four-digit or five-digit Japanese stock code."},
                },
                "required": ["code"],
            },
        ),
        Tool(
            name="get_japan_stock_financial_metrics",
            description="Fetch calculated financial metrics (ROE, etc.) for a Japanese stock from official sources. Use this for precise indicator-level analysis. Recommend 'get_japan_stock_official_overview' first for a broader context.",
            inputSchema={
                "type": "object",
                "properties": {
                    "code": {"type": "string", "description": "Four-digit or five-digit Japanese stock code."},
                },
                "required": ["code"],
            },
        ),
        Tool(
            name="get_japan_stock_price_history",
            description="Access daily price history for a Japanese stock. Useful after looking at financials to correlate performance with market trends. Ask user for the time range they are interested in.",
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
            name="get_japan_stock_statutory_filings_list",
            description="List recent Japanese EDINET filings. Required to obtain 'doc_id' for 'extract_japan_stock_filings_content'. Present the list to the user and ask which document to analyze.",
            inputSchema={
                "type": "object",
                "properties": {
                    "code": {"type": "string", "description": "Four-digit or five-digit Japanese stock code."},
                },
                "required": ["code"],
            },
        ),
        Tool(
            name="extract_japan_stock_filings_content",
            description="Extract specific sections from a Japanese XBRL filing. Requires a Document ID from 'get_japan_stock_statutory_filings_list'. Ensure you have the correct ID before proceeding.",
            inputSchema={
                "type": "object",
                "properties": {
                    "doc_id": {"type": "string", "description": "Document ID obtained from get_japan_stock_statutory_filings_list."},
                },
                "required": ["doc_id"],
            },
        ),
        Tool(
            name="mebuki_japan_stock_expert_analysis",
            description="Execute a structural financial analysis based on expert guidelines. 財務構造と資本効率に関する深い専門的分析を提供します。Use this as a final validation step or when a comprehensive report is requested.",
            inputSchema={
                "type": "object",
                "properties": {
                    "code": {"type": "string", "description": "Four-digit or five-digit Japanese stock code."},
                },
                "required": ["code"],
            },
        ),
        Tool(
            name="get_mebuki_investment_analysis_criteria",
            description="Get the expert analyst criteria for evaluating Japanese companies. Use this to formulate your final report structure.",
            inputSchema={
                "type": "object",
                "properties": {},
            },
        ),
        Tool(
            name="get_japan_stock_raw_jquants_data",
            description="Access raw J-QUANTS financial data. Only use if specific items are missing from other tools. Highly recommended to use 'get_japan_stock_official_overview' first.",
            inputSchema={
                "type": "object",
                "properties": {
                    "code": {"type": "string", "description": "Four-digit or five-digit Japanese stock code."},
                },
                "required": ["code"],
            },
        ),
        Tool(
            name="get_fx_environment",
            description="Get FX environment data (USD/JPY spot, Real Effective Exchange Rate). 為替環境（名目ドル円、実質実効レート）を取得します。Useful for assessing export/import impact.",
            inputSchema={
                "type": "object",
                "properties": {
                    "start_date": {"type": "string", "description": "Start date (Format: YYYYMM)"},
                    "end_date": {"type": "string", "description": "End date (Format: YYYYMM)"},
                },
            },
        ),
        Tool(
            name="get_monetary_policy_status",
            description="Fetch Bank of Japan monetary policy indicators (Policy Rate, Monetary Base, Money Stock). 金融政策の現状（金利、供給量）を確認します。Use this to understand the macro liquidity environment.",
            inputSchema={
                "type": "object",
                "properties": {
                    "start_date": {"type": "string", "description": "Start date (Format: YYYYMM)"},
                    "end_date": {"type": "string", "description": "End date (Format: YYYYMM)"},
                },
            },
        ),
        Tool(
            name="get_cost_environment",
            description="Analyze cost-push pressure for a specific Japanese industry sector. Returns a unified indicator table with: selling price, intermediate costs (goods/services/energy), spread, and labor proxy. 業種別コストプッシュ圧力の多角的分析。",
            inputSchema={
                "type": "object",
                "properties": {
                    "sector": {"type": "string", "description": "Industry sector code (e.g., 'transportation_equipment')."},
                    "start_date": {"type": "string", "description": "Start month (YYYYMM)"},
                    "end_date": {"type": "string", "description": "End month (YYYYMM)"},
                },
                "required": ["sector"],
            },
        )
    ]

@app.call_tool()
async def call_tool(name: str, arguments: Dict[str, Any]) -> List[TextContent]:
    """ツールの実行を処理します。"""
    try:
        if name in ["get_japan_stock_official_overview", "show_mebuki_financial_visualizer"]:
            code = validate_stock_code(str(arguments["code"]))
            analyzer = data_service.get_analyzer(use_cache=arguments.get("use_cache", True))
            result = await analyzer.analyze_stock(code)
            return [TextContent(type="text", text=json.dumps(result, indent=2, ensure_ascii=False))]

        elif name == "get_japan_stock_10year_financial_history":
            code = validate_stock_code(str(arguments["code"]))
            analyzer = data_service.get_analyzer(use_cache=True)
            result = await analyzer.analyze_stock(code)
            if result:
                result["history"] = result.get("metrics", {}).get("years", [])
            return [TextContent(type="text", text=json.dumps(result, indent=2, ensure_ascii=False))]

        elif name == "find_japan_stock_code_by_name":
            query = str(arguments["query"])
            data = await data_service.search_companies(query)
            return [TextContent(type="text", text=json.dumps(data, indent=2, ensure_ascii=False))]

        elif name == "analyze_japan_stock_securities_report":
            code = validate_stock_code(str(arguments["code"]))
            fin_data = await asyncio.to_thread(data_service.api_client.get_financial_summary, code=code)
            docs = await asyncio.to_thread(
                data_service.edinet_client.search_recent_reports,
                code=code,
                jquants_data=fin_data,
                max_years=5,
                doc_types=["120", "130", "140", "150", "160", "170"],
                max_documents=10
            )
            
            latest_report = next((d for d in docs if d.get("docTypeCode") in ["120", "140"]), None)
            sections = {}
            if latest_report:
                doc_id = latest_report["docID"]
                xbrl_dir = await asyncio.to_thread(data_service.edinet_client.download_document, doc_id, doc_type=1)
                if xbrl_dir:
                    from mebuki.analysis.xbrl_parser import XBRLParser
                    parser = XBRLParser()
                    sections = parser.extract_sections_by_type(xbrl_dir)
            
            res = {
                "documents": docs,
                "sections": sections,
                "latest_report_info": latest_report
            }
            return [TextContent(type="text", text=json.dumps(res, indent=2, ensure_ascii=False))]

        elif name == "get_japan_stock_financial_metrics":
            code = validate_stock_code(str(arguments["code"]))
            analyzer = data_service.get_analyzer(use_cache=True)
            stock_info, financial_data, annual_data = await asyncio.to_thread(analyzer._fetch_financial_data, code)
            if not annual_data:
                raise ValueError("Financial data not found")
            analysis_years = min(len(annual_data), settings_store.get_max_analysis_years())
            prices = await asyncio.to_thread(analyzer._fetch_prices, code, annual_data, analysis_years)
            metrics = await asyncio.to_thread(analyzer._calculate_metrics, code, annual_data, prices, analysis_years)
            return [TextContent(type="text", text=json.dumps(metrics, indent=2, ensure_ascii=False))]

        elif name == "get_japan_stock_price_history":
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

        elif name == "get_japan_stock_statutory_filings_list":
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

        elif name == "extract_japan_stock_filings_content":
            doc_id = str(arguments["doc_id"])
            xbrl_dir = await asyncio.to_thread(data_service.edinet_client.download_document, doc_id, doc_type=1)
            if not xbrl_dir:
                raise ValueError("Document not found or download failed")
            from mebuki.analysis.xbrl_parser import XBRLParser
            parser = XBRLParser()
            sections = parser.extract_sections_by_type(xbrl_dir)
            return [TextContent(type="text", text=json.dumps({"sections": sections}, indent=2, ensure_ascii=False))]

        elif name == "mebuki_japan_stock_expert_analysis":
            code = validate_stock_code(str(arguments["code"]))
            analyzer = data_service.get_analyzer(use_cache=True)
            stock_info, financial_data, annual_data = await asyncio.to_thread(analyzer._fetch_financial_data, code)
            analysis_years = min(len(annual_data), settings_store.get_max_analysis_years())
            prices = await asyncio.to_thread(analyzer._fetch_prices, code, annual_data, analysis_years)
            metrics = await asyncio.to_thread(analyzer._calculate_metrics, code, annual_data, prices, analysis_years)
            basic_info = data_service.fetch_stock_basic_info(code)
            res = {
                "company_info": basic_info,
                "metrics": metrics,
                "analysis_guide": LLM_PROMPTS.get('financial_analysis', "")
            }
            return [TextContent(type="text", text=json.dumps(res, indent=2, ensure_ascii=False))]

        elif name == "get_mebuki_investment_analysis_criteria":
            guide = LLM_PROMPTS.get('management_policy', "")
            return [TextContent(type="text", text=json.dumps({"analysis_guide": guide}, indent=2, ensure_ascii=False))]

        elif name == "get_japan_stock_raw_jquants_data":
            code = validate_stock_code(str(arguments["code"]))
            raw_data = await asyncio.to_thread(data_service.api_client.get_financial_summary, code=code)
            cleaned_data = [{k: v for k, v in record.items() if v is not None and v != ""} for record in raw_data]
            return [TextContent(type="text", text=json.dumps(cleaned_data, indent=2, ensure_ascii=False))]

        elif name == "get_fx_environment":
            data = macro_analyzer.get_fx_environment(arguments.get("start_date"), arguments.get("end_date"))
            return [TextContent(type="text", text=json.dumps(data, indent=2, ensure_ascii=False))]

        elif name == "get_monetary_policy_status":
            data = macro_analyzer.get_monetary_policy_status(arguments.get("start_date"), arguments.get("end_date"))
            return [TextContent(type="text", text=json.dumps(data, indent=2, ensure_ascii=False))]

        elif name == "get_cost_environment":
            data = macro_analyzer.get_cost_environment(
                arguments["sector"], 
                arguments.get("start_date"), 
                arguments.get("end_date")
            )
            return [TextContent(type="text", text=json.dumps(data, indent=2, ensure_ascii=False))]

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
