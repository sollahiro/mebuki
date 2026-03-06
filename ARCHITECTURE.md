# プロジェクト構造とファイル説明

このドキュメントでは、mebuki (投資判断分析ツール) のプロジェクト構造と各ファイルの役割を説明します。

## プロジェクト構造

```
mebuki/
├── mebuki/                 # Python コアロジック (分析・API クライアント)
│   ├── api/                # J-QUANTS, EDINET API 連携
│   ├── analysis/           # 指標計算、XBRL 解析
│   ├── constants/          # 各種定数定義
│   ├── utils/              # キャッシュ管理、共通ユーティリティ
│   ├── cli.py              # メイン CLI エントリポイント
│   └── mcp_server.py       # MCP サーバー実装 (STDIO)
├── backend/                # ロジック・サービス層
│   ├── services/           # サービス層（分析実行管理、データ集約）
│   ├── utils/              # バックエンド用ユーティリティ
│   ├── settings.py         # 設定管理
│   └── prompts.py          # LLM 用プロンプト定義
└── assets/                 # 銘柄マスタ (data_j.csv) 等のデータ
```

---

## コンポーネント別説明

### 1. `mebuki/` - Python コアロジック & CLI
アプリケーションのメインロジックとインターフェースです。
- **CLI (`cli.py`)**: 銘柄検索、分析、設定管理、MCP インストールを行う対話型/コマンドラインインターフェースを提供します。
- **MCP サーバー (`mcp_server.py`)**: Claude 等の AI アシスタントから直接財務分析を実行するための STDIO サーバーです。
- **指標計算 (`analysis/calculator.py`)**: 財務データから FCF, ROE, ROIC などを算出します。
- **XBRL 解析 (`analysis/xbrl_parser.py`)**: 有価証券報告書を解析し、MD&A 等のセクションを抽出します。

### 2. `backend/` - サービス層
分析ロジックの実行管理とデータ集約を担当します。
- **データサービス (`services/data_service.py`)**: API クライアント、キャッシュ、分析ロジックを統合し、高レベルなデータアクセスを提供します。
- **設定管理 (`settings.py`)**: API キーや分析設定をローカルに安全に保存します。

---

## MCP (Model Context Protocol)
mebuki は、外部の AI アシスタント（Claude や Goose 等）から利用可能な MCP サーバーとして機能します。

- **提供される主要なツール**:
  - `get_japan_stock_official_overview`: 銘柄の基本情報と主要財務指標を取得。
  - `get_japan_stock_10year_financial_history`: 最大10年間の主要財務指標を時系列で取得。
  - `analyze_japan_stock_securities_report`: 最新の有報から MD&A テキストを抽出。
- **登録方法**: `mebuki mcp install-claude` コマンドで Claude Desktop に自動登録できます。

---

## データフロー

1.  **CLI 操作**: ユーザーが `mebuki` コマンドを使用して、設定（APIキー等）の管理や簡易的な分析を実行します。
2.  **MCP 連携**: AI アシスタントが MCP ツールを呼び出すと、`mcp_server.py` が `backend/services/` を介してデータを取得・加工し、結果を返却します。
3.  **データ取得**: `mebuki/api/` が J-QUANTS や EDINET から最新情報を取得し、`analysis/` が指標を計算します。

---
