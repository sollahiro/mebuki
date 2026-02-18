"""
分析APIエンドポイント
"""

import json
import logging
from typing import Dict, Any
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse, FileResponse
from pydantic import BaseModel
from pathlib import Path

from backend.services.data_service import data_service
from backend.utils.helpers import validate_stock_code

logger = logging.getLogger(__name__)

router = APIRouter()

class AnalysisRequest(BaseModel):
    """分析リクエスト"""
    code: str
    force_refresh: bool = False

def create_sse_message(event: str, data: dict) -> str:
    """SSEメッセージを作成"""
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"

@router.get("/analyze/{code}/stream")
async def analyze_stock_stream(code: str, force_refresh: bool = False):
    """
    銘柄分析をSSEストリームで実行
    """
    code = validate_stock_code(code)
    
    async def event_generator():
        try:
            analyzer = data_service.get_analyzer(use_cache=not force_refresh)
            async for partial_result in analyzer.analyze_stock_stream(code):
                status = partial_result.get("status", "analyzing")
                message = partial_result.get("message", "分析中...")
                
                # ステップ名のマッピング
                step_mapping = {
                    "initializing": ("準備中", 10),
                    "fetching_metrics": ("データ取得", 20),
                    "fetching_prices": ("株価取得", 40),
                    "fetching_edinet": ("EDINET取得", 70),
                    "complete": ("完了", 100)
                }
                step_name, progress_val = step_mapping.get(status, ("分析中", 50))
                
                if status == "complete":
                    yield create_sse_message("complete", {"result": partial_result})
                else:
                    # 個別詳細メッセージがあればそれを優先
                    display_message = message if message else f"{step_name}..."
                    
                    yield create_sse_message("progress", {
                        "step": step_name,
                        "progress": progress_val,
                        "message": display_message,
                        "company_code": code,
                        "company_name": partial_result.get('name'),
                        "data": partial_result
                    })
        except Exception as e:
            logger.error(f"分析エラー: {code} - {e}", exc_info=True)
            yield create_sse_message("app-error", {"message": f"分析中にエラーが発生しました: {str(e)}"})

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )

@router.post("/analyze/{code}")
async def analyze_stock(code: str, force_refresh: bool = False):
    """銘柄分析を実行（非ストリーミング版）"""
    code = validate_stock_code(code)
    try:
        # 非ストリーミング版もDataService経由でAnalyzerを取得
        analyzer = data_service.get_analyzer(use_cache=not force_refresh)
        result = await analyzer.analyze_stock(code)
        if not result:
            raise HTTPException(status_code=404, detail=f"銘柄コード {code} の分析に失敗しました。")
        
        return {"status": "ok", "data": result}
    except ValueError as e:
        logger.warning(f"分析バリデーションエラー: {code} - {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"分析エラー: {code} - {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"分析中にエラーが発生しました: {str(e)}")

@router.get("/history")
async def get_analysis_history():
    """分析履歴を取得"""
    try:
        from datetime import datetime
        from backend.settings import settings_store
        cache_manager = data_service.cache_manager
        cache_dir = Path(settings_store.cache_dir)
        history = []
        
        if cache_dir.exists():
            for cache_file in cache_dir.glob("individual_analysis_*.pkl"):
                cache_key = cache_file.stem.replace("individual_analysis_", "")
                cached_data = cache_manager.get(f"individual_analysis_{cache_key}", skip_date_check=True)
                
                if cached_data:
                    try:
                        timestamp = datetime.fromtimestamp(cache_file.stat().st_mtime).isoformat()
                    except:
                        timestamp = datetime.now().isoformat()
                    
                    history.append({
                        "code": cache_key,
                        "name": cached_data.get("name", ""),
                        "timestamp": timestamp,
                    })
        
        history.sort(key=lambda x: x["code"])
        return {"status": "ok", "data": history}
    except Exception as e:
        logger.error(f"履歴取得エラー: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"履歴の取得に失敗しました: {str(e)}")

@router.delete("/cache/{code}")
async def clear_cache(code: str):
    """指定銘柄のキャッシュを削除"""
    try:
        # 銘柄コードを正規化（例: 1332 -> 13320）
        code = validate_stock_code(code)
        
        # 銘柄コードに関連するすべてのキャッシュ（分析結果、指標等）を削除
        data_service.cache_manager.clear_by_code(code)
        
        # レポートディレクトリも削除
        from backend.settings import settings_store
        import shutil
        reports_dir = Path(settings_store.reports_dir) / f"{code}_edinet"
        if reports_dir.exists():
            shutil.rmtree(reports_dir)
        # 4桁のフォルダが存在する場合も考慮
        if len(code) == 5 and code.endswith("0"):
            code_4 = code[:4]
            reports_dir_4 = Path(settings_store.reports_dir) / f"{code_4}_edinet"
            if reports_dir_4.exists():
                shutil.rmtree(reports_dir_4)
            
        return {"status": "ok", "message": f"銘柄コード {code} のキャッシュとレポートを削除しました"}
    except Exception as e:
        logger.error(f"キャッシュ削除エラー: {code} - {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"キャッシュの削除に失敗しました: {str(e)}")

@router.get("/pdf/{doc_id}")
async def download_pdf(doc_id: str):
    """EDINET PDFをダウンロード"""
    try:
        from backend.settings import settings_store
        reports_dir = Path(settings_store.reports_dir)
        
        if not reports_dir.exists():
            raise HTTPException(status_code=404, detail="PDFが見つかりませんでした")
        
        pdf_files = list(reports_dir.rglob(f"{doc_id}.pdf"))
        if not pdf_files:
            raise HTTPException(status_code=404, detail="PDFが見つかりませんでした")
        
        return FileResponse(
            path=str(pdf_files[0]),
            media_type="application/pdf",
            filename=f"{doc_id}.pdf"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"PDFダウンロードエラー: {doc_id} - {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"PDFのダウンロードに失敗しました: {str(e)}")

    return StreamingResponse(event_generator(), media_type="text/event-stream")
