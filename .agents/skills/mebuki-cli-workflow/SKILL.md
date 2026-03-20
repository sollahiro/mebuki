---
name: mebuki-cli-workflow
description: mebuki CLIを使って日本株の検索・財務分析・有価証券報告書抽出・マクロ分析・ウォッチリスト/ポートフォリオ管理を行う汎用ワークフロースキル
---

# mebuki CLIワークフロー

このスキルは、mebuki CLIコマンドを直接操作して日本株の調査・分析・管理を行います。

## 使用例
- 「トヨタをmebukiで分析して」
- 「7203のポートフォリオに追加して」
- 「ウォッチリストを見せて」
- 「直近の株価を取得して」
- 「ソニーの有価証券報告書を取得して」

## 厳格なルール
- **売買推奨の禁止**: データは客観的に提示し、最終判断は必ずユーザーに委ねること。
- **データの忠実な提示**: mebukiコマンドの出力をそのまま提示し、恣意的な解釈を加えないこと。

## 前提条件チェック

実行前に設定を確認する：

```bash
mebuki config show
```

未設定の場合は以下で初期化を案内する：

```bash
mebuki config init
```

## コマンドリファレンスと実行フロー

### ① 銘柄検索

社名や証券コードで銘柄を検索する。

```bash
mebuki search <社名またはコード>
```

例：
```bash
mebuki search トヨタ
mebuki search 7203
```

### ② 財務分析

銘柄の財務データを分析する。

```bash
mebuki analyze <code> [--scope overview|history|metrics|raw] [--years N] [--format table|json] [--include-2q]
```

- `--scope overview`: 財務サマリー（デフォルト）
- `--scope history`: 複数年の財務推移
- `--scope metrics`: 財務指標（ROE/ROICなど）
- `--scope raw`: 生データ
- `--years N`: 取得年数（デフォルト: 5）。**FY（通期）の件数**でカウントする
- `--include-2q`: 2Q（中間期）データも含めて表示する（opt-in）。2Qの ROE/ROIC/PER/PBR は表示しない（6ヶ月分の値のため）

例：
```bash
mebuki analyze 7203
mebuki analyze 7203 --scope history --years 10
mebuki analyze 7203 --scope metrics --format json
mebuki analyze 7203 --years 5 --include-2q          # 通期5年 + 中間期を合わせて表示
```

### ③ 株価取得

直近の株価データを取得する。

```bash
mebuki price <code> [--days N] [--format table|json]
```

例：
```bash
mebuki price 7203
mebuki price 7203 --days 30
```

### ④ EDINETファイリング一覧

EDINETに提出された書類の一覧を取得する。

```bash
mebuki filings <code> [--format table|json]
```

例：
```bash
mebuki filings 7203
```

### ⑤ 有価証券報告書セクション抽出

有価証券報告書から特定セクションを抽出する。

```bash
mebuki filing <code> [--doc-id DOC_ID] [--sections business_risks|mda|management_policy]
```

- `--doc-id`: ④で取得したドキュメントID（省略時は最新）
- `--sections`: 抽出するセクション（複数指定可）
  - `business_risks`: 事業等のリスク
  - `mda`: 経営者による財政状態・経営成績の分析（MD&A）
  - `management_policy`: 経営方針

例：
```bash
mebuki filing 7203
mebuki filing 7203 --sections business_risks mda
mebuki filing 7203 --doc-id S100XXXX --sections mda
```

### ⑥ マクロ経済データ

為替・金融政策などのマクロ経済データを取得する。

```bash
mebuki macro <fx|monetary> [--start YYYYMM] [--end YYYYMM]
```

- `fx`: 為替レート（日銀統計）
- `monetary`: 金融政策・金利データ

例：
```bash
mebuki macro fx
mebuki macro monetary --start 202001 --end 202512
```

### ⑦ ウォッチリスト管理

注目銘柄のウォッチリストを管理する。

```bash
mebuki watch add <code> [--name 備考]
mebuki watch remove <code>
mebuki watch list
```

例：
```bash
mebuki watch add 7203 --name "トヨタ自動車"
mebuki watch list
mebuki watch remove 7203
```

### ⑧ ポートフォリオ管理

保有銘柄のポートフォリオを管理する。

```bash
# 買付
mebuki portfolio add <code> <数量> <取得単価> [--broker 証券会社] [--account 特定|一般|NISA] [--date YYYY-MM-DD]

# 売却
mebuki portfolio sell <code> <数量> [--broker 証券会社] [--account 特定|一般|NISA]

# 銘柄削除
mebuki portfolio remove <code>

# 一覧表示
mebuki portfolio list [--detail]
```

例：
```bash
mebuki portfolio add 7203 100 2500 --broker SBI --account 特定
mebuki portfolio list --detail
mebuki portfolio sell 7203 50
```

## 典型ワークフロー

### 株式調査フロー

新規銘柄を調査する際の標準フロー：

1. **銘柄特定**: `mebuki search <社名>` でコードを確認
2. **財務分析**: `mebuki analyze <code> --scope history --years 5` で財務推移を確認
   - 中間期も確認したい場合: `--include-2q` を追加
3. **書類一覧**: `mebuki filings <code>` でEDINET提出書類を確認
4. **報告書抽出**: `mebuki filing <code> --sections business_risks mda` でリスクと経営状況を確認
5. **マクロ確認**: `mebuki macro fx` / `mebuki macro monetary` で外部環境を把握

### 銘柄管理フロー

銘柄を追加・管理する際のフロー：

1. **ウォッチ登録**: `mebuki watch add <code> --name <備考>`
2. **買付記録**: `mebuki portfolio add <code> <数量> <単価>`
3. **保有確認**: `mebuki portfolio list --detail`
