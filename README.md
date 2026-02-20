# mebuki

**「投資すべきでない銘柄」を特定し、大切な資本を守るための財務分析ツール**

mebukiは、J-QUANTS API、EDINET API を活用し、投資判断における「負の側面」を浮き彫りにすることに特化した財務分析 Electron アプリケーションです。最大10年分の財務データを可視化し、企業の真の姿をあぶり出します。

> [!CAUTION]
> **投資回避の判断をサポートするツールです**
> 本ツールは投資を推奨するものではありません。「投資すべきではない理由」を見つけるためのものです。投資は自己責任で行ってください。

---

## 📸 スクリーンショット

### 財務分析ダッシュボード
![財務分析画面](assets/screenshots/app-ui.png)
*最大10年分の財務データを直感的なグラフで可視化。営業CF、FCF、ROE、ROICなどの重要指標を一目で把握できます。*

### AI アシスタント連携 (Claude / Goose)
![Claude Desktop連携](assets/screenshots/mcp-claude-usage.png)
![Goose Desktop連携](assets/screenshots/mcp-goose-usage.png)
*Claude Desktop (Anthropic提供) や Goose Desktop (Block提供) と連携し、自然言語で財務分析を実行。「日産の業績を調べてください」といった会話形式で、詳細な財務データにアクセスできます。*

---

## 🍃 コンセプト・哲学

多くの投資ツールは「何を買うべきか」を提示しますが、mebukiは **「何を避けるべきか」** を重視します。

- **FCF (フリーキャッシュフロー) 最重視**: 帳簿上の利益ではなく、実際に手元に残る現金を重視します。
- **利益の質の検証**: 営業利益と営業CFの乖離をチェックし、粉飾や脆弱なビジネスモデルを察知します。
- **資本効率の追求**: 簡易ROICやROEを通じて、経営陣の資本配分能力を評価します。
- **定性情報の統合**: 有価証券報告書の重要セクションを抽出し、ワンクリックで一次情報（PDF）にアクセス可能です。

---

## ✨ 主要機能

### 📊 財務データのマルチビュー可視化
直感的なグラフで、企業のトレンドを4つの切り口で分析します。
1. **稼ぐ・蓄える**: 営業CFの蓄積と現預金残高、FCFの推移
2. **増やす**: 簡易ROIC、ROE、CF変換率による資本効率分析
3. **返す・残す**: EPS、BPS、配当性向による株主価値の蓄積
4. **評価**: PER、PBR、株価による市場評価のダイナミクス

---

### 📄 EDINET 連携
- 最新年度の有価証券報告書を自動取得・解析
- 重要なセクション（MD&A、事業リスク等）の自動抽出
- ワンクリックでの PDF ダウンロード機能

### 🤖 AI アシスタント連携 (MCP)
- **Claude / Goose との統合**: ワンクリックで連携設定が完了
- **自然言語での財務分析**: 「トヨタの直近3年の業績推移をまとめて」といった会話形式で分析
- **MCP ツール提供**:
  - `get_japan_stock_official_overview`: 基本情報と主要財務指標の取得
  - `get_japan_stock_10year_financial_history`: 最大10年間の時系列財務データ
  - `analyze_japan_stock_securities_report`: 有価証券報告書からのMD&A抽出
  - その他、企業検索、株価履歴取得など

---

## 🚀 クイックスタート

1. **インストール**
   - [GitHub Releases](https://github.com/sollahiro/mebuki/releases)から最新版をダウンロード
   - **macOS**: `.dmg`ファイルをダウンロードして開き、アプリをアプリケーションフォルダにドラッグ

2. **API キーの設定**
   アプリ起動後、設定画面(右上のギアアイコン)から以下のキーを設定します。
   - `JQUANTS_REFRESH_TOKEN` - [登録・発行サイトへ](https://jpx-jquants.com/)
   - `EDINET_API_KEY` - [登録・発行サイトへ](https://disclosure2.edinet-fsa.go.jp/)

> [!IMPORTANT]
> **J-Quants API プランについて**
> 本ツールの機能を十分に活用（長期の財務データ取得など）するには、**Lightプラン（月額1,650円）以上** の利用を推奨します。
> - **無料プラン**: 財務データは過去2年分のみ、かつリクエスト制限が厳しいため、分析中にエラーが発生しやすくなります。
> - **Lightプラン以上**: 過去5年以上のデータが取得可能になり、スムーズな分析が可能です。

> [!NOTE]
> **プライバシーとセキュリティ**
> - APIキーはお使いのPC内にローカル保存されます(`electron-store` 使用)
> - APIキーが外部サーバーに送信されることはありません
> - 各APIへの通信は、お使いのPCから直接行われます

3. **MCP連携**
   Claude Desktop等のAIアシスタントと連携する場合は、設定画面の「AIアシスタント連携」から設定できます。

### 🔧 その他の環境・手動連携 (Cursor 等)

Cursor やその他の MCP クライアントをご利用の場合は、以下の構成を手動で設定してください。

#### 構成設定 (config.json 用)

```json
{
  "mcpServers": {
    "mebuki": {
      "command": "node",
      "args": ["/Users/shutosorahiro/mebuki/packages/mcp/dist/index.js"],
      "env": {
        "MEBUKI_BACKEND_URL": "http://localhost:8765"
      },
      "metadata": {
        "icon": "/Users/shutosorahiro/mebuki/packages/mcp/icon.png",
        "description": "Expert investment analyst tool for Japanese stocks."
      }
    }
  }
}
```

> [!NOTE]
> `args` と `icon` のパスは、実際のインストール環境に合わせて適宜書き換えてください。

#### 手順
1. 上記の構成設定をコピーします。
2. お使いのクライアント（Cursor の MCP 設定など）を開きます。
3. サーバー一覧に `mebuki` という名前で、コピーした内容を貼り付けます。
4. 設定を保存し、クライアントを再起動してください。

詳細な使用方法は [QUICKSTART.md](QUICKSTART.md) を参照してください。

> [!TIP]
> **開発者向け情報**
> 開発環境のセットアップや、ソースコードからの起動方法については [QUICKSTART.md](QUICKSTART.md#開発者向けセットアップ) を参照してください。

---

## 📂 プロジェクト構造

```text
mebuki/
├── packages/
│   ├── renderer/      # React フロントエンド (Vite)
│   ├── main/          # Electron メインプロセス
│   ├── preload/       # 安全なブリッジ（IPC 通信）
│   ├── mcp/           # MCP サーバー実装
│   └── shared/        # 共通型定義・ユーティリティ
├── backend/           # FastAPI バックエンド (WebSocket / API サーバー)
├── mebuki/            # Python コアロジック (分析エンジン・API クライアント)
│   ├── analysis/     # 財務分析ロジック
│   ├── api/          # 外部 API クライアント (J-QUANTS, EDINET)
│   └── utils/        # ユーティリティ
├── assets/            # アプリアイコン等の静的リソース
├── scripts/           # ビルド・ユーティリティスクリプト
└── start.sh           # 開発・実行用統合起動スクリプト
```

---

## 📘 関連ドキュメント

- [ARCHITECTURE.md](ARCHITECTURE.md) - システム設計の詳細

---

## ⚖️ 免責事項

本ソフトウェアおよび提供される情報は、投資判断の参考として提供されるものであり、投資の勧誘を目的としたものではありません。株価の変動や企業の倒産、財務状況の悪化等により、投資した資本を失う可能性があります。最終的な投資判断は、必ず利用者ご自身の責任において行ってください。

---
Developed with ❤️ by [sollahiro](https://github.com/sollahiro)
