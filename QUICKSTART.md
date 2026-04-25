# クイックスタートガイド

## 一般ユーザー向け (macOS)

### インストール

1. macOS (Homebrew) - **推奨**
   ```bash
   brew tap sollahiro/mebuki
   brew install mebuki
   ```

2. バイナリ直接ダウンロード
   - [GitHub Releases](https://github.com/sollahiro/mebuki/releases)から最新版をダウンロード
   - **macOS**: `mebuki-macos-arm64.tar.gz` をダウンロード

3. 展開と配置
   - ダウンロードしたファイルを解凍し、中にある `mebuki` バイナリを手元の適当なパスの通ったディレクトリ（例: `/usr/local/bin`）にコピーするか、そのまま実行してください。

3. 初期設定
   - ターミナルを開き、以下のコマンドを実行して API キーの設定を行ってください。
     ```bash
     mebuki config init
     ```

---

## 開発者向けセットアップ

### 1. 依存パッケージのインストール

Python 3.11 以上が必要です。

#### Python パッケージのインストール

```bash
# リポジトリのクローン
git clone https://github.com/sollahiro/mebuki.git
cd mebuki

# 依存関係のインストール (Poetry推奨)
poetry install

# または pip でインストール
pip install -e .
```

### 2. CLI の起動

```bash
mebuki
```

## アプリの使い方

### APIキーの設定

初回起動時、または以下のコマンドで API キーを設定してください。

```bash
mebuki config init
```

- **J-QUANTS API**: [登録・発行サイトへ](https://jpx-jquants.com/)
- **EDINET API**: [登録・発行サイトへ](https://disclosure2.edinet-fsa.go.jp/)

### J-Quants API プランについて

mebukiでは、J-Quants APIを通じて株価や財務データを取得します。プランによって取得可能なデータ期間やリクエスト制限が異なります。

| プラン | 月額(税込) | 財務データ期間 | レート制限 | 推奨度 |
| :--- | :--- | :--- | :--- | :--- |
| **Free** | 0円 | 過去2年間 | 5回/分 | 試用のみ |
| **Light** | 1,650円 | 過去5年間 | 60回/分 | **最低推奨** |
| **Standard** | 3,300円 | 過去10年間 | 120回/分 | 強力推奨 |
| **Premium** | 16,500円 | 全期間 | 500回/分 | プロフェッショナル |

> [!IMPORTANT]
> - **長期分析**: 投資判断には少なくとも3〜5年程度のトレンド確認が不可欠ですが、無料プランでは2年分しか取得できません。
> - **安定性**: 無料プランはレート制限が非常に厳しいため、バックエンドでの並列取得時に「レート制限エラー」が発生しやすくなります。
> - **快適さ**: 10年分の可視化機能をフルに活用するには、Standardプラン以上が最適です。

---

## AIアシスタント連携 (MCP)

mebukiは、Claude Desktop や Goose などのAIアシスタントと連携して、対話形式で銘柄分析を行うことができます。

### MCP連携の設定

**前提条件:**
- `mebuki` コマンドがパスの通った場所にあること
- Claude Desktop や Goose など、MCP対応のAIアシスタントがインストールされていること

**設定手順:**

1. ターミナルで以下のコマンドを実行します。

```bash
# Claude Desktop の場合
mebuki mcp install-claude

# Goose の場合
mebuki mcp install-goose

# LM Studio の場合
mebuki mcp install-lm-studio
```

2. 実行後、AIアシスタントを**再起動**してください。

### Claude Desktopでの使用例

連携後、Claude Desktopで以下のような質問ができます:

- 「トヨタの直近3年間の業績推移をまとめて」
- 「最新の有価証券報告書から、事業リスクについて要約して」
- 「この企業の資本効率(ROE)の推移はどうなっている?」

AIアシスタントがmebukiのツールを使用して、自動的に以下の情報を取得・分析します:

- 銘柄情報の検索
- 財務データの取得・推移分析
- 有価証券報告書の取得とセクション抽出

### 利用可能なMCPツール

連携により、以下のツールがAIアシスタントから利用可能になります:
- `find_japan_stock_code`: 企業名や銘柄コードから証券コードを検索
- `get_japan_stock_financial_data`: 財務データ（年次・半期推移、ROIC・有利子負債含む）を取得。`half=true` でH1/H2半期推移、`years` で年数指定可能
- `search_japan_stock_filings`: EDINET文書（有報等）の検索
- `extract_japan_stock_filing_content`: 有報の特定セクションを抽出
- `get_japan_stock_watchlist`: ウォッチリストの取得
- `manage_japan_stock_watchlist`: ウォッチリストへの銘柄追加・削除
- `get_japan_stock_portfolio`: 保有銘柄ポートフォリオの取得
- `manage_japan_stock_portfolio`: 保有追加・売却・強制削除

## トラブルシューティング

### APIキーエラー
```bash
mebuki config show
```
で API キーが正しく設定されているか確認してください。

### MCP連携でツールが表示されない
1. AIアシスタントを完全に終了して再起動してください。
2. ターミナルで `mebuki mcp start` を実行し、エラーなく起動することを確認してください（確認後は Ctrl+C で終了）。

### 動作環境エラー
`ModuleNotFoundError` や `mebuki: command not found` が発生する場合、Python のインストール環境や PATH の設定を確認してください。
