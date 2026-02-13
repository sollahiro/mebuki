#!/bin/bash
# バックエンドビルドスクリプト
# FastAPIサーバーを1つの実行ファイルに固めます。

set -e

PROJECT_ROOT=$(pwd)
VENV_BIN="${PROJECT_ROOT}/venv/bin"
PYINSTALLER="${VENV_BIN}/pyinstaller"
MAIN_PY="backend/main.py"
DIST_DIR="dist_backend"

echo "🧹 以前のビルドをクリーンアップ中..."
rm -rf "$DIST_DIR" build backend.spec

echo "🏗️  PyInstaller でバックエンドをビルド中..."
# --onedir: フォルダ形式で出力（macOSではこちらが推奨）
# --name: 出力ファイル名
# --collect-all: FastAPI関連の依存関係を確実に含める
"$PYINSTALLER" --noconfirm --onedir \
    --name "mebuki-backend" \
    --clean \
    --collect-all "fastapi" \
    --collect-all "uvicorn" \
    --collect-all "sse_starlette" \
    --collect-all "google.genai" \
    --add-data "mebuki:mebuki" \
    --paths "." \
    "$MAIN_PY"

echo "✅ ビルド完了: dist/mebuki-backend"

# 作成されたフォルダを dist_backend に移動
mkdir -p "$DIST_DIR"
cp -r dist/mebuki-backend "$DIST_DIR/"

echo "🛠️  Python.framework の構造を修正中 (署名エラー回避のため)..."
# macOS の署名 (codesign) は Python.framework/Python が実体ファイルだとエラーになるため、
# 正しい symlink 構造に作り変えます。
FRAMEWORK_DIR="${DIST_DIR}/mebuki-backend/_internal/Python.framework"
if [ -d "$FRAMEWORK_DIR" ]; then
    pushd "$FRAMEWORK_DIR" > /dev/null
    
    # 1. Versions/Current をシンボリックリンクにする
    if [ -d "Versions" ]; then
        pushd Versions > /dev/null
        # 実際のバージョン名を取得 (例: 3.14)
        REAL_VERSION=$(ls -1 | grep -v "Current" | head -n 1)
        if [ -n "$REAL_VERSION" ]; then
            if [ -d "Current" ] && [ ! -L "Current" ]; then
                rm -rf Current
                ln -s "$REAL_VERSION" Current
            elif [ ! -e "Current" ]; then
                ln -s "$REAL_VERSION" Current
            fi
        fi
        popd > /dev/null
    fi

    # 2. トップレベルのファイルをシンボリックリンクにする
    if [ -f "Python" ] && [ ! -L "Python" ]; then
        rm -f Python
        ln -s Versions/Current/Python Python
    fi
    if [ -d "Resources" ] && [ ! -L "Resources" ]; then
        rm -rf Resources
        ln -s Versions/Current/Resources Resources
    fi
    
    popd > /dev/null
fi

rm -rf dist

echo "🚀 実行ファイルは ${DIST_DIR}/mebuki-backend に格納されました。"
