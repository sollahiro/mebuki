# プロジェクト構造とファイル説明

このドキュメントでは、投資判断分析ツールのプロジェクト構造と各ファイルの役割を説明します。

## プロジェクト構造

```
mebuki/
├── mebuki/                 # Python コアロジック (分析・API クライアント)
│   ├── api/                # J-QUANTS, EDINET API 連携
│   ├── analysis/           # 指標計算、XBRL 解析
│   ├── constants/          # 各種定数定義
│   └── utils/              # キャッシュ管理、共通ユーティリティ
├── backend/                # FastAPI バックエンド
│   ├── routers/            # API エンドポイント (分析、MCP)
│   ├── services/           # サービス層（分析実行管理、データ集約）
│   └── utils/              # バックエンド用ユーティリティ
├── packages/
│   ├── renderer/           # React フロントエンド (Vite)
│   ├── main/               # Electron メインプロセス (ウィンドウ・ライフサイクル管理)
│   ├── preload/            # IPC 通信の安全なブリッジ
│   ├── mcp/                # TypeScript 版 MCP サーバープロキシ
│   └── shared/             # フロントエンド・バックエンド間の共通型定義
├── assets/                 # アプリアイコン等のリソース
├── scripts/                # ビルド・パッケージング用ユーティリティ
└── dist_backend/           # PyInstaller で生成されたバックエンドバイナリ
```

---

## コンポーネント別説明

### 1. `mebuki/` - Python コアロジック
アプリケーションの計算エンジンとデータ取得レイヤーです。
- **指標計算 (`analysis/calculator.py`)**: 財務データから FCF, ROE, ROIC などを算出します。
- **XBRL 解析 (`analysis/xbrl_parser.py`)**: 有価証券報告書（XBRL/HTML）を解析し、MD&A（経営者による分析）等のセクションを抽出します。
- **API クライアント (`api/`)**: J-QUANTS API および EDINET API との通信を担当し、データの正規化を行います。

### 2. `backend/` - FastAPI サーバー
Electron アプリケーションおよび MCP クライアントに対する API サーバーとして機能します。
- **分析実行管理 (`services/analyzer.py`)**: 財務データ、株価、EDINET 書類を並列・非同期で取得・処理するメインロジック。
- **リアルタイム通信**: Server-Sent Events (SSE) を使用して、分析の進捗状況をフロントエンドへ逐次通知します。
- **MCP 対応 (`routers/mcp.py`)**: 外部 LLM クライアント向けに最適化された分析ツール群を提供します。

### 3. `packages/` - モノレポ構造
- **Renderer (React)**: Modern UI (Tailwind CSS, Radix UI) を提供。Recharts による財務データの時系列分析。
- **MCP (`packages/mcp`)**: TypeScript 実装の MCP プロトコルサーバー。Stdio 経由で Claude Desktop や Goose Desktop 等と通信し、FastAPI の MCP エンドポイントを呼び出します（プロキシ機能）。
- **Shared**: IPC 通信や API 通信、設定画面で共通して使用される型定義を保持します。

---

## MCP (Model Context Protocol) サーバー

mebukiは、外部の AI アシスタント（Claude や Goose 等）が財務分析を実行できる MCP サーバーとして機能します。

- **提供される主要なツール**:
  - `analyze_stock`: 銘柄の基本情報と主要財務指標を高速に取得（EDINETアクセスなし）。
  - `get_financial_history`: 最大10年分の主要財務指標を時系列で取得。投資判断のトレンド分析に最適。
  - `analyze_securities_report`: 最新の有報から MD&A テキストを抽出し、定性的な背景を把握。
  - `search_companies`: 銘柄名やコードから情報を逆引き。
  - `get_raw_financial_summaries`: J-QUANTS の生の財務サマリー（全項目）を取得。
  - `mebuki_analyze_financials`: 財務分析のガイドラインと詳細指標をセットで提供。
- **統合の仕組み**: MCP サーバー (`packages/mcp`) が Claude 等の LLM からのリクエストを受け取り、FastAPI の `mcp/` ルーターが提供する JSON エンドポイントを介してデータを返却します。

---

## データフロー

### 1. アプリ（Electron）からの実行
1.  **UI 操作**: ユーザーが銘柄コードを入力し分析を開始。
2.  **IPC 通信**: `renderer` -> `main` へリクエスト。
3.  **HTTP/SSE**: メインプロセスから FastAPI (`localhost:8765`) へリクエスト。
4.  **並列処理**: `analyzer.py` が `asyncio` を利用し、以下の処理を並列で実行：
    - J-QUANTS からの財務データ取得と指標計算（第1段階）。
    - 株価履歴の取得。
    - EDINET での提出書類の検索と PDF 準備。
5.  **リアルタイム更新**: 分析の各ステップの結果が SSE を通じて UI へストリーミングされ、グラフが段階的に描画されます。

### 2. MCP クライアントからの実行
1.  **ツール呼び出し**: 外部の AI アシスタントが `get_financial_history` 等を呼び出し。
2.  **プロキシ**: `packages/mcp` が Stdio 経由来のリクエストを FastAPI の特定エンドポイントに転送。
3.  **データ返却**: バックエンドが構造化された財務データを LLM に返し、LLM 側で分析（投資回避の判断等）が行われます。

---

## LLM 戦略の変更

本プロジェクトは当初「Gemini による自動要約」を内蔵していましたが、現在は**「MCP による外部 LLM への高精度なデータ供給」**に注力しています。
- 内蔵版の LLM 要約機能は現在、安定性と自由度の観点から MCP ツールによる外部分析に移行されています。
- `mebuki/llm` や `backend/prompts.py` は、MCP ツールが LLM へ提供する分析基準やガイドラインとして活用されています。

---
