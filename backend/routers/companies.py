from fastapi import APIRouter, Query, HTTPException
from typing import List, Dict, Any
from backend.services.master_data import master_data_manager

router = APIRouter(tags=["companies"])

@router.get("/search")
async def search_companies(query: str = Query(..., min_length=1)):
    """
    銘柄を検索（サジェスト用）
    """
    try:
        # data_service 経由ではなく直接 MasterDataManager を呼ぶ（軽量化）
        results = master_data_manager.search(query, limit=20)
        return results
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/refresh")
async def refresh_master():
    """
    銘柄マスタを再読み込み
    """
    success = master_data_manager.reload()
    if success:
        return {"status": "success", "message": "Master data reloaded"}
    else:
        raise HTTPException(status_code=500, detail="Failed to reload master data")
