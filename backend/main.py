"""
FastAPI Backend - エントリーポイント

Electronアプリから呼び出されるAPIサーバー。
"""

import sys
import uvicorn
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

# プロジェクトルートをパスに追加
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from backend.routers import mcp, companies
from backend.settings import settings_store


import logging

# ロギングの設定
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """アプリケーションのライフサイクル管理"""
    logger.info("🚀 FastAPI Server starting...")
    # 起動時に銘柄マスタを強制ロード
    from backend.services.master_data import master_data_manager
    master_data_manager.reload()
    yield
    logger.info("👋 FastAPI Server shutting down...")


app = FastAPI(
    title="mebuki API",
    description="投資判断分析ツール API",
    version="1.1.0",
    lifespan=lifespan
)

# CORS設定（Electronからのリクエストを許可）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_origin_regex=r"http://localhost:\d+",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ルーターを登録
app.include_router(mcp.router, prefix="/api/mcp", tags=["mcp"])
app.include_router(companies.router, prefix="/api/companies", tags=["companies"])


@app.get("/api/health")
async def health_check():
    """ヘルスチェックエンドポイント"""
    return {"status": "ok", "message": "mebuki API is running"}


@app.post("/api/settings")
async def update_settings(settings: dict):
    """
    設定を更新（Electronから起動時に呼び出される）
    """
    settings_store.update(settings)
    
    # サービス層の再初期化
    from backend.services.data_service import data_service
    
    data_service.reinitialize()
    
    return {"status": "ok", "message": "Settings updated"}


@app.get("/api/settings")
async def get_settings():
    """現在の設定を取得（APIキーはマスクして返す）"""
    return settings_store.get_masked()


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8765)
