# mebuki

**「投資すべきでない銘柄」をAIと共に特定する、MCPネイティブな財務分析プラットフォーム**

mebukiは、J-QUANTS API、EDINET API、そして日本銀行 API を活用し、投資判断における「負の側面」を浮き彫りにすることに特化した、**MCP (Model Context Protocol) 対応** の財務分析 Electron アプリケーションです。

> [!CAUTION]
> **投資回避の判断をサポートするツールです**
> 本ツールは投資を推奨するものではありません。「投資すべきではない理由」を見つけるためのものです。投資は自己責任で行ってください。

---

## 🤖 AI アシスタントを「超一流の分析官」に
![Claude Desktop連携](assets/screenshots/mcp-claude-usage.png)
*Claude Desktop, Cursor, Goose などの MCP クライアントと連携し、自然言語で財務分析を実行。「日産の業績を調べてください」といった会話形式で、最大10年分の詳細な財務データにアクセスできます。*

---

## 🍃 コンセプト・哲学

多くの投資ツールは「何を買うべきか」を提示しますが、mebukiは **「何を避けるべきか」** を重視します。

- **FCF (フリーキャッシュフロー) 最重視**: 帳簿上の利益ではなく、実際に手元に残る現金を重視します。
- **利益の質の検証**: 営業利益と営業CFの乖離をチェックし、粉飾や脆弱なビジネスモデルを察知します。
- **資本効率の追求**: 簡易ROICやROEを通じて、経営陣の資本配分能力を評価します。
- **定性情報の統合**: 有価証券報告書の重要セクションを即座に解析・抽出。経営方針や事業リスクの核心を一読できます。

---

## ✨ 主要機能

### 1. Model Context Protocol (MCP) 統合
- **あらゆる AI クライアントに対応**: Claude Desktop, Goose, VS Code (Cline/Roo Code) など、お好みの環境に mebuki の分析能力を統合。
- **フルスタック MCP 機能**:
  - 🛠️ **Tools** (全15ツール): 銘柄検索、財務履歴取得、マクロ分析など
  - 📚 **Resources**: mebuki の分析手法を AI に伝授する「分析プロトコル」を提供
  - 💡 **Prompts**: 「日本株分析リポート」を一括で開始するための最適化されたテンプレート
- **ローカル完結型**: データ取得から分析指示まで、すべてユーザーのローカル環境で完結。

### 2. 高度な財務・市場分析
- **自然言語での対話的分析**: 「トヨタの直近3年の業績推移をまとめて」といった指示で、AI がデータを取得・解釈。
- **定性情報の統合**: 有価証券報告書の重要セクションを即座に解析・抽出。経営方針や事業リスクの核心を一読できます。

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
> - APIキーは **macOS Keychain (キーチェーン)** に安全に保存されます
> - APIキーが外部サーバーに送信されることはありません
> - 各APIへの通信は、お使いのPCから直接行われます

### 🔧 その他の環境・手動連携 (Cursor 等)

Cursor やその他の MCP クライアントをご利用の場合は、以下の構成を手動で設定してください。

#### 構成設定 (config.json 用)

```json
{
  "mcpServers": {
    "mebuki": {
      "command": "node",
      "args": ["/ABSOLUTE/PATH/TO/mebuki/packages/mcp/dist/index.js"],
      "env": {
        "MEBUKI_BACKEND_URL": "http://localhost:8765"
      },
      "metadata": {
        "icon": "/ABSOLUTE/PATH/TO/mebuki/packages/mcp/icon.png",
        "description": "Expert investment analyst tool for Japanese stocks."
      }
    }
  }
}
```

> [!NOTE]
> `/ABSOLUTE/PATH/TO/mebuki` は、実際のインストール環境の絶対パスに書き換えてください。

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
├── backend/           # FastAPI バックエンドサーバー
│   ├── routers/       # MCP・API エンドポイント定義
│   ├── services/      # 業務ロジック・データ処理
│   └── utils/         # 共通ユーティリティ
├── mebuki/            # Python コアロジック
│   ├── analysis/     # 財務分析・XBRL解析エンジン
│   ├── api/          # 外部 API クライアント (J-QUANTS, EDINET, BOJ)
│   └── utils/        # 低レイヤーヘルパー
├── assets/            # アプリアイコン等の静的リソース
├── scripts/           # ビルド・ユーティリティスクリプト
```

---

## 🛠️ MCP ツール リファレンス

### 📈 株式分析ツール

#### `find_japan_stock_code_by_name` — 銘柄コード検索

会社名や部分的な銘柄コードから4〜5桁の証券コードを特定します。分析の **最初のステップ** として使用してください。

| 項目 | 内容 |
|------|------|
| 入力 | `query` — 会社名（例: `Toyota`）またはコードの一部 |
| データソース | J-QUANTS API |
| 次のステップ | コードを確認後に `get_japan_stock_official_overview` へ |

---

#### `get_japan_stock_official_overview` — 財務サマリー取得

現在の財務健全性スナップショット（ROE・営業利益率・PBR 等）を取得します。**最初のデータ取得ステップ**です。

| 項目 | 内容 |
|------|------|
| 入力 | `code` — 4〜5桁の証券コード |
| データソース | J-QUANTS API |
| 次のステップ | 概況提示後、ユーザーに確認して `get_japan_stock_10year_financial_history` へ |

---

#### `get_japan_stock_10year_financial_history` — 最大10年財務履歴

売上・純利益・FCF・ROE などの主要財務指標を最大10年分の時系列で取得します。

| 項目 | 内容 |
|------|------|
| 入力 | `code` — 4〜5桁の証券コード |
| データソース | J-QUANTS API |
| 次のステップ | `mebuki_japan_stock_expert_analysis` で構造分析へ |

---

#### `analyze_japan_stock_securities_report` — 有価証券報告書解析

最新の有価証券報告書から MD&A・リスクなどの定性情報を抽出します。

| 項目 | 内容 |
|------|------|
| 入力 | `code` — 4〜5桁の証券コード |
| データソース | EDINET API (XBRL) |
| 次のステップ | 概況取得後に実行。定性・定量の両面から評価 |

---

#### `get_japan_stock_financial_metrics` — 財務指標取得

ROE など計算済み財務指標を公式データから取得します。`get_japan_stock_official_overview` で不足する指標がある場合に補完用途で使用します。

| 項目 | 内容 |
|------|------|
| 入力 | `code` — 4〜5桁の証券コード |
| データソース | J-QUANTS API |

---

#### `get_japan_stock_price_history` — 株価履歴

指定日数分の日次株価データを取得します。財務分析と市場トレンドの相関確認に使用します。

| 項目 | 内容 |
|------|------|
| 入力 | `code` — 証券コード, `days` — 取得日数（デフォルト: 365） |
| データソース | J-QUANTS API |

---

#### `get_japan_stock_statutory_filings_list` — EDINET 書類一覧

直近のEDINET提出書類の一覧を取得します。`extract_japan_stock_filings_content` で使う `doc_id` を得るために必要です。

| 項目 | 内容 |
|------|------|
| 入力 | `code` — 4〜5桁の証券コード |
| データソース | EDINET API |
| 次のステップ | ユーザーに書類を確認後、`extract_japan_stock_filings_content` へ |

---

#### `extract_japan_stock_filings_content` — EDINET 書類内容抽出

EDINET XBRL書類の特定セクションを抽出します。`doc_id` は `get_japan_stock_statutory_filings_list` から取得してください。

| 項目 | 内容 |
|------|------|
| 入力 | `doc_id` — 書類ID |
| データソース | EDINET API (XBRL) |

---

#### `mebuki_japan_stock_expert_analysis` — エキスパート財務分析

mebukiのガイドラインに基づく構造的財務分析を実行します。財務健全性・資本効率を総合評価します。

| 項目 | 内容 |
|------|------|
| 入力 | `code` — 4〜5桁の証券コード |
| データソース | J-QUANTS API |
| 推奨タイミング | `get_japan_stock_10year_financial_history` 取得後の深掘り分析時 |

---

#### `show_mebuki_financial_visualizer` — インタラクティブ可視化

財務テーブルと業績グラフを統合したインタラクティブUIを表示します。**AI コンテキストへのデータ提供は行いません**（表示専用）。

| 項目 | 内容 |
|------|------|
| 入力 | `code` — 4〜5桁の証券コード |
| 出力 | MCP App UI（タブ切り替えで表・グラフをインライン表示） |

---

#### `get_japan_stock_raw_jquants_data` — J-QUANTS 生データ

J-QUANTS APIから他ツールで取得できない特定の財務項目を直接取得します。

| 項目 | 内容 |
|------|------|
| 入力 | `code` — 4〜5桁の証券コード |
| データソース | J-QUANTS API |
| 推奨 | まず `get_japan_stock_official_overview` を使用し、不足時のみ本ツールを使用 |

---

#### `get_mebuki_investment_analysis_criteria` — 分析基準取得

mebuki の投資分析における専門家基準を取得します。最終レポートの構成策定に使用します。

| 項目 | 内容 |
|------|------|
| 入力 | なし |
| 出力 | 専門家評価基準（マークダウン） |

---

### 🌐 マクロ分析ツール（日本銀行 時系列統計データ検索サイト API）

mebuki には、日本銀行が提供する**時系列統計データ検索サイト API** を活用した以下の3つのマクロ分析MCPツールが含まれています。

#### `get_monetary_policy_status` — 金融政策モニター

日銀の金融政策に関する時系列データを取得します。

| 指標 | データベース | 系列コード | 内容 |
|------|------------|-----------|------|
| 政策金利（基準貸付利率） | IR01 | `MADR1Z@D` | 日銀の基準割引率・基準貸付利率（日次） |
| マネタリーベース | MD01 | `MABS1AN11` | 日銀当座預金＋日本銀行券の平均残高 |
| マネーストックM3 | MD02 | `MAM1YAM3M3MO` | M3の前年比（月次） |

| 項目 | 内容 |
|------|------|
| 入力 | `start_date`, `end_date` (任意, YYYYMM形式推奨) |
| 用途 | マクロ流動性環境の把握、株式・債券の割引率評価などに活用。 |

---

#### `get_fx_environment` — 為替環境

為替相場の時系列データを取得します。

| 指標 | データベース | 系列コード | 内容 |
|------|------------|-----------|------|
| ドル円スポット（17時） | FM08 | `FXERD04` | 東京市場 ドル・円 スポット17時時点 |
| 実質実効為替レート | FM09 | `FX180110002` | 通貨の国際競争力を示す実質実効為替レート指数 |

| 項目 | 内容 |
|------|------|
| 入力 | `start_date`, `end_date` (任意, YYYYMM形式推奨) |
| 用途 | 輸出企業の為替感応度分析、ファンダメンタルズとの比較に活用。 |

---

#### `get_cost_environment` — 業種別コストプッシュ圧力分析

指定した業種のコストプッシュ圧力を多角的に取得します。販価と中間コストのスプレッドを「統合テーブル」形式で返却します。

#### 対応業種

**製造業 (PR01: 国内企業物価指数)**
`foods`, `textiles`, `lumber`, `pulp_paper`, `chemicals`, `petroleum_coal`, `plastics`, `ceramics`, `steel`, `nonferrous_metals`, `metal_products`, `general_machinery`, `production_machinery`, `business_machinery`, `electronic_components`, `electrical_machinery`, `ict_equipment`, `transportation_equipment`

**非製造業 (PR02: 企業向けサービス価格指数)**
`finance_insurance`, `real_estate`, `transportation_postal`, `information_communication`, `leasing_rental`, `advertising`, `other_services`

#### 返却カラム

| カラム | 内容 | データソース |
|--------|------|--------------|
| 販価 | 業種別の販売価格指数 | PR01 / PR02 |
| 中間(財) | 中間需要：財（ステージ2） | PR04 `PRFI20_1I2G00000` |
| 中間(ｻ) | 中間需要：サービス | PR04 `PRFI20_1I2SD0000` |
| スプレッド | 販価 - 主要中間コスト | 算出値 |
| エネルギー | 中間需要：エネルギー | PR04 `PRFI20_1I2G00200` |
| 人件費 | 高人件費率サービス（人件費Proxy） | PR02 `PRCS20_42S0000002` |
| 輸入(円) | 輸入物価指数（円ベース） | PR01 `PRCG20_2600000000` |
| 輸入(契) | 輸入物価指数（契約通貨ベース） | PR01 `PRCG20_2500000000` |

> [!NOTE]
> 全指標は原指数（2020年＝100）で返却されます。スプレッドは製造業では「販価−中間(財)」、非製造業では「販価−中間(サービス)」を使用します。

**用途**: 原材料費・人件費・輸入コストの複合的なコスト圧力分析に活用。

---

## ⚖️ 免責事項

本ソフトウェアおよび提供される情報は、投資判断の参考として提供されるものであり、投資の勧誘を目的としたものではありません。株価の変動や企業の倒産、財務状況の悪化等により、投資した資本を失う可能性があります。最終的な投資判断は、必ず利用者ご自身の責任において行ってください。

---

## 📝 クレジット

このサービスは、日本銀行時系列統計データ検索サイトの API 機能を使用しています。サービスの内容は日本銀行によって保証されたものではありません。

---
Developed with ❤️ by [sollahiro](https://github.com/sollahiro)
