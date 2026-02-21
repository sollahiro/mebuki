#!/bin/bash
# mebuki - 投資判断分析ツール起動スクリプト (統合版)

# スクリプトの場所に関わらず、プロジェクトルートに移動
cd "$(dirname "$0")"

# カラー出力
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${GREEN}🚀 mebuki を起動します...${NC}"

# Poetryの仮想環境をチェック
if [ -d "./venv" ] && ./venv/bin/poetry env info --path &> /dev/null; then
    echo -e "${GREEN}✅ Poetry環境を確認しました${NC}"
else
    echo -e "${YELLOW}⚠️  Poetryの仮想環境が正しく設定されていない可能性があります。${NC}"
    echo "   依存パッケージを確認またはインストールしてください: poetry install"
fi

# Ctrl+Cで終了したときにバックグラウンドプロセスを確実に終了させるためのトラップ
cleanup() {
    echo -e "\n${YELLOW}🛑 サーバーを停止中...${NC}"
    kill $FASTAPI_PID $VITE_PID 2>/dev/null || true
    
    # 念のため、ポートを使用しているプロセスも確認して終了
    if lsof -ti:8765 > /dev/null 2>&1; then
        lsof -ti:8765 | xargs kill -9 2>/dev/null || true
    fi
    if lsof -ti:5173 > /dev/null 2>&1; then
        lsof -ti:5173 | xargs kill -9 2>/dev/null || true
    fi
    exit 0
}
trap cleanup INT TERM

# モードの選択
MODE=${1:-electron}

case $MODE in
    electron)
        echo -e "${GREEN}📱 Electronアプリを起動します...${NC}"
        npm run start -w main
        ;;
    
    dev)
        echo -e "${GREEN}🔧 開発モードで起動します...${NC}"
        echo "   FastAPI: http://127.0.0.1:8765"
        echo "   React:   http://localhost:5173"
        
        # 既存のプロセスをクリーンアップ
        echo -e "${YELLOW}🧹 既存のプロセスをクリーンアップ中...${NC}"
        if lsof -ti:8765 > /dev/null 2>&1; then
            lsof -ti:8765 | xargs kill -9 2>/dev/null || true
            sleep 1
        fi
        if lsof -ti:5173 > /dev/null 2>&1; then
            lsof -ti:5173 | xargs kill -9 2>/dev/null || true
            sleep 1
        fi
        
        # 開発モードでも永続データ保存先のパスを設定
        USER_DATA_PATH="$HOME/Library/Application Support/mebuki"
        ASSETS_PATH="$(pwd)/assets"
        
        # ディレクトリが存在することを確認
        mkdir -p "$USER_DATA_PATH/analysis_cache" "$USER_DATA_PATH/data" "$USER_DATA_PATH/reports"

        # FastAPIサーバーをバックグラウンドで起動
        echo -e "${GREEN}🐍 FastAPIサーバーを起動中...${NC}"
        MEBUKI_USER_DATA_PATH="$USER_DATA_PATH" MEBUKI_ASSETS_PATH="$ASSETS_PATH" PYTHONPATH=. ./venv/bin/python3 -m uvicorn backend.main:app --host 127.0.0.1 --port 8765 --reload &
        FASTAPI_PID=$!
        
        # Vite dev serverを起動
        echo -e "${GREEN}⚛️  React開発サーバーを起動中...${NC}"
        npm run dev -w renderer &
        VITE_PID=$!
        
        # 少し待ってからElectronを起動
        echo -e "${YELLOW}⏳ Electron起動まで5秒待機...${NC}"
        sleep 5
        echo -e "${GREEN}📱 Electronを開発モードで起動中...${NC}"
        ELECTRON_DEV=true npm run start -w main
        
        # Electronが終了したら全て終了
        cleanup
        ;;
    
    build)
        echo -e "${GREEN}🔨 本番用ビルドを作成します...${NC}"
        echo -e "${GREEN}⚛️  Reactアプリをビルド中...${NC}"
        npm run build -w renderer
        echo -e "${GREEN}✅ ビルド完了: packages/renderer/dist/${NC}"
        ;;
    
    api)
        echo -e "${GREEN}🐍 FastAPIサーバーのみを起動します...${NC}"
        if lsof -ti:8765 > /dev/null 2>&1; then
            echo -e "${YELLOW}🧹 ポート8765を使用しているプロセスを終了します...${NC}"
            lsof -ti:8765 | xargs kill -9 2>/dev/null || true
            sleep 1
        fi
        PYTHONPATH=. ./venv/bin/python3 -m uvicorn backend.main:app --host 127.0.0.1 --port 8765 --reload
        ;;
    
    *)
        echo -e "${RED}❌ 不明なモード: $MODE${NC}"
        echo ""
        echo "使用方法: ./start.sh [mode]"
        echo ""
        echo "モード:"
        echo "  electron  - Electronアプリを起動 (デフォルト)"
        echo "  dev       - 開発モード (FastAPI + Vite + Electron)"
        echo "  build     - 本番用ビルドを作成"
        echo "  api       - FastAPIサーバーのみを起動"
        exit 1
        ;;
esac
