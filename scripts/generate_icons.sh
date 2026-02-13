#!/bin/bash
# アイコン変換スクリプト
# mebuki_icon.png から .icns (macOS) と .ico (Windows) を作成します。

set -e

ICON_SOURCE="mebuki_icon.png"
ASSETS_DIR="assets"
ICONSET_DIR="${ASSETS_DIR}/icon.iconset"

if [ ! -f "$ICON_SOURCE" ]; then
    echo "Error: $ICON_SOURCE not found."
    exit 1
fi

echo "🎨 アイコンの変換を開始します..."

# 共通の変換関数
generate_icns() {
    local source=$1
    local name=$2
    local iconset_dir="${ASSETS_DIR}/${name}.iconset"
    
    echo "🍏 macOS用 ${name}.icns を作成中..."
    mkdir -p "$iconset_dir"
    
    sips -z 16 16     "$source" --out "${iconset_dir}/icon_16x16.png" > /dev/null 2>&1
    sips -z 32 32     "$source" --out "${iconset_dir}/icon_16x16@2x.png" > /dev/null 2>&1
    sips -z 32 32     "$source" --out "${iconset_dir}/icon_32x32.png" > /dev/null 2>&1
    sips -z 64 64     "$source" --out "${iconset_dir}/icon_32x32@2x.png" > /dev/null 2>&1
    sips -z 128 128   "$source" --out "${iconset_dir}/icon_128x128.png" > /dev/null 2>&1
    sips -z 256 256   "$source" --out "${iconset_dir}/icon_128x128@2x.png" > /dev/null 2>&1
    sips -z 256 256   "$source" --out "${iconset_dir}/icon_256x256.png" > /dev/null 2>&1
    sips -z 512 512   "$source" --out "${iconset_dir}/icon_256x256@2x.png" > /dev/null 2>&1
    sips -z 512 512   "$source" --out "${iconset_dir}/icon_512x512.png" > /dev/null 2>&1
    sips -z 1024 1024 "$source" --out "${iconset_dir}/icon_512x512@2x.png" > /dev/null 2>&1

    iconutil -c icns "$iconset_dir" -o "${ASSETS_DIR}/${name}.icns"
    rm -rf "$iconset_dir"
}

# 通常アイコン
generate_icns "$ICON_SOURCE" "icon"

# ダークモード用アイコン（存在する場合）
if [ -f "icon_dark.png" ]; then
    generate_icns "icon_dark.png" "icon_dark"
    sips -z 256 256 "icon_dark.png" --out "${ASSETS_DIR}/icon_dark.png" > /dev/null 2>&1
fi

# Windows用リソース (通常版)
echo "🪟 Windows用リソースを準備中..."
sips -z 256 256 "$ICON_SOURCE" --out "${ASSETS_DIR}/icon.png" > /dev/null 2>&1

echo "✅ 変換完了: assets/icon.icns $([ -f "icon_dark.png" ] && echo "および assets/icon_dark.icns")"
