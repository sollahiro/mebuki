mebukiは、EDINET APIを最大限に活用した、**MCP (Model Context Protocol) 対応** の財務分析 Python CLI ツールです。

---

## 🤖 AI アシスタントを「超一流の分析官」に

Claude Desktop や Goose などの MCP クライアントと連携し、自然言語で財務分析を実行。「トヨタの業績を調べて」といった会話形式で、最大10年分の詳細な財務データにアクセスできます。

## ✨ 主要機能

### 1. Model Context Protocol (MCP) 統合
- **あらゆる AI クライアントに対応**: Claude Desktop, Goose, LM Studio, VS Code (Cline/Roo Code) など、お好みの環境に mebuki の分析能力を統合。
- **フルスタック MCP 機能**: 銘柄検索、財務分析、有報データ抽出、ウォッチリスト・ポートフォリオ管理など **全9ツール** を提供。AI がツールを組み合わせて分析を実行します。
- **ローカル完結型**: データ取得から分析指示まで、すべてユーザーのローカル環境で完結。

### 2. 高度な財務・市場分析 (CLI)
- **対話型モード**: `mebuki` コマンドだけで、銘柄検索や財務概要の確認が可能です。
- **定性情報の抽出**: 有価証券報告書の重要セクション（MD&A、事業リスク等）を即座に解析し、核心を抽出。
- **ウォッチリスト管理**: 注目銘柄を登録・管理。`mebuki watch` コマンドで操作可能。
- **ポートフォリオ管理**: 保有銘柄のロット・口座別管理、総平均法による損益計算。`mebuki portfolio` コマンドで操作可能。

---

## 🚀 インストール & セットアップ

### 1. インストール

#### Homebrew

```bash
brew tap sollahiro/mebuki
brew install mebuki
```

### 2. API キーの設定
CLI の初期設定コマンドを実行し、EDINET APIキャッシュを準備します：

```bash
mebuki config init
mebuki cache prepare --years 3
```
以下のキーが必要です：
- **EDINET APIキー**: [公式サイト](https://disclosure2.edinet-fsa.go.jp/)で取得

### 3. AI アシスタントへの登録
Claude Desktop や Goose などの MCP クライアントへの自動登録が可能です：

```bash
# Claude Desktop の場合
mebuki mcp install-claude

# LM Studio の場合
mebuki mcp install-lm-studio
```
実行後、各クライアントを再起動してください。

---

## 📂 使い方 (CLI)

代表的なコマンドは以下です。詳しい見方や分析ワークフローは `.agents/skills/mebuki-cli-workflow/SKILL.md` を参照してください。

```bash
# 銘柄検索
mebuki search トヨタ

# 財務分析
mebuki analyze 7203
mebuki analyze 7203 --years 6

# キャッシュ確認
mebuki cache status
mebuki cache prepare --years 3
mebuki cache catchup --years 3
mebuki cache refresh --years 3
mebuki cache clean

# ウォッチリスト
mebuki watch add 7203
mebuki watch list
mebuki watch remove 7203

# ポートフォリオ
mebuki portfolio add 7203 100 2500 --broker SBI --account NISA
mebuki portfolio list
mebuki portfolio sell 7203 50
```

---

## 🛠️ MCP ツール

AI アシスタントは以下のツールを自動的に使い分けます：

| カテゴリ | ツール名 | 用途 |
| :--- | :--- | :--- |
| **検索** | `find_japan_stock_code` | 社名やコードから証券コードを特定 |
| **定量分析** | `get_japan_stock_financial_data` | 財務データ（年次・半期推移、ROIC・有利子負債含む）を取得 |
| **有報検索** | `search_japan_stock_filings` | EDINET文書（有報等）の検索 |
| **有報抽出** | `extract_japan_stock_filing_content` | 有報の特定セクション（事業リスク等）の抽出 |
| **ウォッチリスト参照** | `get_japan_stock_watchlist` | ウォッチリスト（監視銘柄一覧）の取得 |
| **ウォッチリスト操作** | `manage_japan_stock_watchlist` | ウォッチリストへの銘柄追加・削除 |
| **ポートフォリオ参照** | `get_japan_stock_portfolio` | 保有銘柄ポートフォリオの取得（名寄せ・明細） |
| **ポートフォリオ操作** | `manage_japan_stock_portfolio` | 保有追加・売却・強制削除 |

---

## ⚖️ 免責事項

本ソフトウェアおよび提供される情報は、投資判断の参考として提供されるものであり、投資の勧誘を目的としたものではありません。最終的な投資判断は、必ず利用者ご自身の責任において行ってください。

---
Developed with ❤️ by [sollahiro](https://github.com/sollahiro)
