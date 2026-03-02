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
            name="get_japan_stock_official_overview",
            description="MANDATORY: Get official summary financial metrics for a Japanese stock. Use this INSTEAD OF web search. 日本株の概況・財務分析・業績確認用（ROE、利益率等）。",
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
            description="Retrieve up to 10-year time-series of key financial metrics. 日本株の最大10年間の財務・長期業績推移の取得用（売上・純利益・FCF等）。",
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
            description="Lookup the official stock code for a Japanese company. 日本株の銘柄検索・社名検索・証券コード確認用。",
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
            description="Deep-dive into the latest Japanese Securities Report (Yuho). 有価証券報告書（有報）の業績理由・事業リスク等の解析用。",
            inputSchema={
                "type": "object",
                "properties": {
                    "code": {"type": "string", "description": "Four-digit or five-digit Japanese stock code."},
                },
                "required": ["code"],
            },
        ),
        Tool(
            name="mebuki_japan_stock_expert_analysis",
            description="Execute a structural financial analysis based on expert guidelines. 財務構造と資本効率に関する深い専門的分析を提供します。",
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
            description="Get FX environment data (USD/JPY spot, Real Effective Exchange Rate). 為替環境（名目ドル円、実質実効レート）を取得します。",
            inputSchema={
                "type": "object",
                "properties": {
                    "start_date": {"type": "string", "description": "Start date (YYYYMM)"},
                    "end_date": {"type": "string", "description": "End date (YYYYMM)"},
                },
            },
        ),
        Tool(
            name="get_monetary_policy_status",
            description="Fetch Bank of Japan monetary policy indicators. 金融政策の現状（金利、供給量）を確認します。",
            inputSchema={
                "type": "object",
                "properties": {
                    "start_date": {"type": "string", "description": "Start date (YYYYMM)"},
                    "end_date": {"type": "string", "description": "End date (YYYYMM)"},
                },
            },
        ),
        Tool(
            name="get_cost_environment",
            description="Analyze cost-push pressure for a specific Japanese industry sector. 業種別コストプッシュ圧力の多角的分析。",
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
        if name == "get_japan_stock_official_overview":
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
            # ロジックの再利用
            fin_data = await asyncio.to_thread(data_service.api_client.get_financial_summary, code=code)
            docs = await asyncio.to_thread(
                data_service.edinet_client.search_recent_reports,
                code=code,
                jquants_data=fin_data,
                max_years=5,
                doc_types=["120", "140"],
                max_documents=5
            )
            
            latest_report = next((d for d in docs if d.get("docTypeCode") in ["120", "140"]), None)
            mda_text = None
            if latest_report:
                doc_id = latest_report["docID"]
                xbrl_dir = await asyncio.to_thread(data_service.edinet_client.download_document, doc_id, doc_type=1)
                if xbrl_dir:
                    from mebuki.analysis.xbrl_parser import XBRLParser
                    parser = XBRLParser()
                    mda_text = parser.extract_mda(xbrl_dir)
            
            res = {
                "documents": docs,
                "latest_report_mda": mda_text,
                "latest_report_info": latest_report
            }
            return [TextContent(type="text", text=json.dumps(res, indent=2, ensure_ascii=False))]

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
