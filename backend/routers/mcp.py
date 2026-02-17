"""
MCP専用エンドポイント
"""

import logging
from typing import Dict, Any
from fastapi import APIRouter, HTTPException
from backend.services.data_service import data_service
from backend.utils.helpers import validate_stock_code
from backend.settings import settings_store
from backend.prompts import LLM_PROMPTS

logger = logging.getLogger(__name__)

router = APIRouter()

@router.get("/analyze/{code}")
async def analyze_stock_mcp(code: str, use_cache: bool = True):
    """
    MCP用の軽量な分析取得。
    有報等の取得（EDINETアクセス）を含まず、銘柄基本情報と財務指標のみを高速に返却します。
    """
    code = validate_stock_code(code)
    try:
        # EDINETアクセスを含まない基本データのみを高速に取得
        analyzer = data_service.get_analyzer(use_cache=use_cache)
        
        # 財務データの取得
        import asyncio
        stock_info, financial_data, annual_data = await asyncio.to_thread(analyzer._fetch_financial_data, code)
        if not stock_info:
            raise HTTPException(status_code=404, detail="Financial data not found")
            
        # 指標計算
        available_years = len(annual_data)
        max_years = settings_store.get_max_analysis_years()
        analysis_years = min(available_years, max_years)
        
        prices = await asyncio.to_thread(analyzer._fetch_prices, code, annual_data, analysis_years)
        metrics = await asyncio.to_thread(analyzer._calculate_metrics, code, annual_data, prices, analysis_years)
        
        from datetime import datetime
        result = {
            "code": code,
            **data_service.fetch_stock_basic_info(code),
            "metrics": metrics,
            "edinet_data": [], # 軽量版では空にする
            "analyzed_at": datetime.now().isoformat()
        }
        
        return {"status": "ok", "data": result}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"MCP分析エラー: {code} - {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"データ取得中にエラーが発生しました: {str(e)}")


@router.get("/search_companies")
async def search_companies(query: str):
    """企業検索 (コードまたは名称)"""
    try:
        # data_serviceの新設メソッドを使用して高速検索（名称対応）
        data = await data_service.search_companies(query)
        return {"status": "ok", "data": data}
            
    except Exception as e:
        logger.error(f"MCP検索エラー: {query} - {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/financials/{code}")
async def get_financials(code: str):
    """
    J-QUANTSの生の財務サマリーを取得。
    MCPレスポンスの肥大化を防ぐため、値がNoneまたは空文字のフィールドを除去して返却します。
    """
    code = validate_stock_code(code)
    try:
        raw_data = data_service.api_client.get_financial_summary(code=code)
        
        # クリーンアップ処理: 値がないフィールドを削除してトークンを節約
        cleaned_data = []
        for record in raw_data:
            cleaned_record = {k: v for k, v in record.items() if v is not None and v != ""}
            cleaned_data.append(cleaned_record)
            
        return {"status": "ok", "data": cleaned_data}
    except Exception as e:
        logger.error(f"MCP財務データエラー: {code} - {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/financial_history/{code}")
async def get_financial_history(code: str):
    """
    GUIの「データ」タブ同様、主要な財務指標を時系列で取得。
    LLMが傾向を把握しやすいように整形されています。
    """
    code = validate_stock_code(code)
    try:
        analyzer = data_service.get_analyzer(use_cache=True)
        import asyncio
        stock_info, financial_data, annual_data = await asyncio.to_thread(analyzer._fetch_financial_data, code)
        
        if not annual_data:
            raise HTTPException(status_code=404, detail="Financial data not found")
            
        # 指標計算
        analysis_years = min(len(annual_data), settings_store.get_max_analysis_years())
        prices = await asyncio.to_thread(analyzer._fetch_prices, code, annual_data, analysis_years)
        metrics = await asyncio.to_thread(analyzer._calculate_metrics, code, annual_data, prices, analysis_years)
        
        # GUIのFinancialTable.tsxに準拠した項目をリスト化
        # Backendの内部データ構造（YearData）をそのまま活用することでフロントエンドとの整合性を高める
        history = metrics.get("years", [])
            
        return {
            "status": "ok", 
            "data": {
                "code": code,
                **data_service.fetch_stock_basic_info(code),
                "history": history
            }
        }
    except Exception as e:
        logger.error(f"MCP財務履歴エラー: {code} - {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/metrics/{code}")
async def get_metrics(code: str):
    """財務指標取得"""
    code = validate_stock_code(code)
    try:
        # 指標計算には財務データと株価データが必要
        # analyzerをインスタンス化して計算ロジックを再利用
        analyzer = data_service.get_analyzer(use_cache=True)
        
        # threadで実行
        import asyncio
        stock_info, financial_data, annual_data = await asyncio.to_thread(analyzer._fetch_financial_data, code)
        if not annual_data:
            raise HTTPException(status_code=404, detail="Financial data not found")
            
        analysis_years = min(len(annual_data), settings_store.get_max_analysis_years())
        prices = await asyncio.to_thread(analyzer._fetch_prices, code, annual_data, analysis_years)
        metrics = await asyncio.to_thread(analyzer._calculate_metrics, code, annual_data, prices, analysis_years)
        
        return {"status": "ok", "data": metrics}
    except Exception as e:
        logger.error(f"MCP指標計算エラー: {code} - {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/prices/{code}")
async def get_prices(code: str, days: int = 365):
    """株価履歴取得"""
    code = validate_stock_code(code)
    try:
        from datetime import datetime, timedelta
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        
        data = data_service.api_client.get_daily_bars(
            code=code,
            from_date=start_date.strftime("%Y-%m-%d"),
            to_date=end_date.strftime("%Y-%m-%d")
        )
        return {"status": "ok", "data": data}
    except Exception as e:
        logger.error(f"MCP株価取得エラー: {code} - {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/edinet/{code}")
async def list_edinet_documents(code: str):
    """EDINET書類一覧取得"""
    code = validate_stock_code(code)
    try:
        # 効率化のため、まずJ-QUANTSで財務情報を取得（決算発表日を知るため）
        fin_data = data_service.api_client.get_financial_summary(code=code)
        if not fin_data:
             # 財務データがない場合は直近の検索ができないため空を返すか、期間指定なしで検索するか
             # ここでは安全に空を返す
             return {"status": "ok", "data": []}
             
        # 直近の有報・半報等を検索（余裕を持たせるため max_years=10 に拡大）
        docs = data_service.edinet_client.search_recent_reports(
            code=code,
            jquants_data=fin_data,
            max_years=10,
            doc_types=["120", "130", "140", "150", "160", "170"], # 有報、四半期、半期など
            max_documents=10
        )
        return {"status": "ok", "data": docs}
    except Exception as e:
        logger.error(f"MCP EDINET検索エラー: {code} - {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/edinet/xbrl/{doc_id}")
async def get_edinet_xbrl_content(doc_id: str):
    """EDINET書類(XBRL)のMD&Aセクション取得"""
    try:
        # ダウンロード（キャッシュされる）
        # doc_type=1 は XBRL(zip)
        xbrl_dir = data_service.edinet_client.download_document(doc_id, doc_type=1)
        if not xbrl_dir:
            raise HTTPException(status_code=404, detail="Document not found or download failed")
            
        # 解析
        from mebuki.analysis.xbrl_parser import XBRLParser
        parser = XBRLParser()
        
        # MD&Aのみ抽出
        mda_text = parser.extract_mda(xbrl_dir)
        
        if not mda_text:
            return {"status": "ok", "data": None, "message": "MD&A section not found"}
            
        return {"status": "ok", "data": mda_text}
        
    except Exception as e:
        logger.error(f"MCP XBRL解析エラー: {doc_id} - {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/securities_report/{code}")
async def get_securities_report_analysis(code: str):
    """
    有価証券報告書の分析用データ取得。
    直近の書類一覧と、最新の有報からMD&Aテキストを抽出して返します。
    """
    code = validate_stock_code(code)
    try:
        # 1. 書類一覧取得
        fin_data = data_service.api_client.get_financial_summary(code=code)
        docs = data_service.edinet_client.search_recent_reports(
            code=code,
            jquants_data=fin_data,
            max_years=5,
            doc_types=["120", "130", "140", "150", "160", "170"],
            max_documents=10
        )
        
        # 2. 最新の有報(120)または四半期報告書(140)からMD&Aを抽出
        latest_report = next((d for d in docs if d.get("docTypeCode") in ["120", "140"]), None)
        mda_text = None
        if latest_report:
            doc_id = latest_report["docID"]
            xbrl_dir = data_service.edinet_client.download_document(doc_id, doc_type=1)
            if xbrl_dir:
                from mebuki.analysis.xbrl_parser import XBRLParser
                parser = XBRLParser()
                mda_text = parser.extract_mda(xbrl_dir)
        
        return {
            "status": "ok",
            "data": {
                "documents": docs,
                "latest_report_mda": mda_text,
                "latest_report_info": latest_report
            }
        }
    except Exception as e:
        logger.error(f"MCP 有報分析エラー: {code} - {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/mebuki_analysis/{code}")
async def get_mebuki_analysis_details(code: str):
    """
    Claude自身に分析をさせるための詳細データと分析ガイドを返却。
    Geminiを介さず、詳細指標とプロンプト基準を直接デリバリします。
    """
    code = validate_stock_code(code)
    try:
        analyzer = data_service.get_analyzer(use_cache=True)
        
        # 指標計算
        import asyncio
        stock_info, financial_data, annual_data = await asyncio.to_thread(analyzer._fetch_financial_data, code)
        if not annual_data:
            raise HTTPException(status_code=404, detail="Financial data not found")
            
        analysis_years = min(len(annual_data), settings_store.get_max_analysis_years())
        prices = await asyncio.to_thread(analyzer._fetch_prices, code, annual_data, analysis_years)
        metrics = await asyncio.to_thread(analyzer._calculate_metrics, code, annual_data, prices, analysis_years)
        
        # 基本情報
        basic_info = data_service.fetch_stock_basic_info(code)
        
        # 分析ガイド (prompts.py から財務分析プロンプトを抽出)
        analysis_guide = LLM_PROMPTS.get('financial_analysis', "")
        
        return {
            "status": "ok",
            "data": {
                "company_info": basic_info,
                "metrics": metrics,
                "analysis_guide": analysis_guide,
                "note": "Please perform a deep financial analysis based on the provided metrics and the 'analysis_guide' criteria. Focus on the 4 perspectives mentioned in the guide."
            }
        }
    except Exception as e:
        logger.error(f"MCP詳細分析データ取得エラー: {code} - {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/management_policy_guide")
async def get_management_policy_guide():
    """
    経営方針要約のためのガイドライン（プロンプト基準）を返却。
    投資家目線の5つの重要項目（資本効率、還元等）を含みます。
    """
    try:
        # prompts.py から経営方針要約プロンプトを抽出
        guide = LLM_PROMPTS.get('management_policy', "")
        
        return {
            "status": "ok",
            "data": {
                "analysis_guide": guide,
                "note": "Claude, please summarize the management policy text based on the criteria in the 'analysis_guide'. Focus on the 5 investor-centric points."
            }
        }
    except Exception as e:
        logger.error(f"MCP経営方針ガイド取得エラー: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
