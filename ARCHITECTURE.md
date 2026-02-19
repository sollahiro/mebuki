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
│   ├── routers/            # MCP 連携、銘柄検索
│   ├── services/           # サービス層（分析実行管理、データ集約）
│   └── utils/              # バックエンド用ユーティリティ
├── packages/
│   ├── renderer/           # React フロントエンド (Vite) - 設定管理専用
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
AI アシスタント（MCP）に対する API サーバーとして機能します。
- **分析実行管理 (`services/analyzer.py`)**: 財務データ、株価、EDINET 書類を並列・非同期で取得・処理するメインロジック。
- **MCP 対応 (`routers/mcp.py`)**: 外部 LLM クライアント向けに最適化された分析ツール群を提供します。

### 3. `packages/` - モノレポ構造
- **Renderer (React)**: APIキーの設定や、AIアシスタント（Claude等）との連携設定を行うための GUI を提供します。
- **MCP (`packages/mcp`)**: TypeScript 実装の MCP プロトコルサーバー。Stdio 経由で Claude Desktop や Goose Desktop 等と通信し、FastAPI の MCP エンドポイントを呼び出します。
- **Shared**: 設定画面や API 通信で共通して使用される型定義を保持します。

---

## MCP (Model Context Protocol) サーバー

mebukiは、外部の AI アシスタント（Claude や Goose 等）が財務分析を実行できる MCP サーバーとして機能します。

- **提供される主要なツール**:
  - `get_japan_stock_official_overview`: 銘柄の基本情報と主要財務指標を高速に取得（EDINETアクセスなし）。
  - `get_japan_stock_10year_financial_history`: 最大10年間の主要財務指標を時系列で取得。投資判断のトレンド分析に最適。
  - `analyze_japan_stock_securities_report`: 最新の有報から MD&A テキストを抽出し、定性的な背景を把握。
  - `find_japan_stock_code_by_name`: 銘柄名やコードから情報を逆引き。
  - `get_japan_stock_raw_jquants_data`: J-QUANTS の生の財務サマリー（全項目）を取得。
  - `mebuki_japan_stock_expert_analysis`: 専門家基準による財務構造分析と詳細指標を提供。
- **統合の仕組み**: MCP サーバー (`packages/mcp`) が Claude 等の LLM からのリクエストを受け取り、FastAPI の `mcp/` ルーターが提供する JSON エンドポイントを介してデータを返却します。

---

## データフロー

### 1. 設定管理（Electron）
1.  **UI 操作**: ユーザーが、フロントエンド（Renderer）で API キーの入力や AI アシスタント連携設定を行います。
2.  **設定保存**: 設定内容は Electron の安全なストア、およびバックエンド（FastAPI）に保存されます。

### 2. MCP クライアント（Claude等）からの分析実行
1.  **ツール呼び出し**: 外部の AI アシスタントが `get_japan_stock_10year_financial_history` 等を呼び出し。
2.  **プロキシ**: `packages/mcp` が Stdio 経由来のリクエストを FastAPI の特定エンドポイントに転送。
3.  **データ返却**: バックエンドが構造化された財務データを LLM に返し、LLM 側で分析（投資回避の判断等）が行われます。
4.  **リッチコンテンツ（Interactive UI）**: 特定のツール結果には `_meta.ui` が付与され、Claude 等のインターフェース内で React コンポーネント（`FinancialCharts` 等）を用いた視覚的なグラフ表示が行われます。

---

## 設計方針の転換

本プロジェクトは、GUI 上で直接分析結果を表示するモデルから、**「MCP による外部 LLM への高精度なデータ供給と、その中での視覚化」**に特化したモデルへと移行しました。
- GUI（Electron アプリ）は、API キーとインフラ（MCP サーバー）を管理するためのダッシュボードとして機能します。
- 財務データの取得ロジック (`analyzer.py`) や計算ロジック、および視覚化コンポーネント (`packages/renderer`) は、MCP プロトコルを通じて AI アシスタントに提供されます。

---
