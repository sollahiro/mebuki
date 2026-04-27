---
name: mebuki-cli-workflow
description: mebuki CLIを使って日本株の検索・財務分析・有価証券報告書抽出・ウォッチリスト/ポートフォリオ管理を行う汎用ワークフロースキル
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
mebuki search <社名またはコード> [--format table|json]
```

例：
```bash
mebuki search トヨタ
mebuki search 7203
mebuki search 7203 --format json
```

### ② 財務分析

銘柄の財務データを分析する。

```bash
mebuki analyze <code> [--years N] [--format table|json] [--half] [--no-cache] [--scope raw]
```

- `--years N`: 取得年数（デフォルト: 5、`--half` 時は 3）。**FY（通期）の件数**でカウントする
- `--half`: 上半期(H1)・下半期(H2)の半期推移を表示する（seasonalityの確認に有用）
- `--scope raw`: 生データをJSON取得したい場合のみ指定
- `--no-cache`: キャッシュを使用せず最新データを取得する

デフォルト出力に含まれる主要財務指標（横並び年次推移）:

| 項目 | 用途・ポイント |
|---|---|
| 売上高 | トップライン成長確認 |
| 売上総利益 | 粗利の絶対額 |
| **粗利率 (%)** | 製品競争力・価格支配力の指標 |
| 営業利益 | 本業の稼ぎ |
| **営業利益率 (%)** | 本業の収益性。粗利率との差 = 販管費率 |
| ROE / ROIC | 資本効率 |
| 営業CF / 投資CF / フリーCF | キャッシュフロー |
| 配当性向 | 株主還元方針 |
| 有利子負債合計 / 投下資本 | 財務健全性・ROIC計算基盤 |
| DocID | IBD・GP抽出元のEDINET書類ID（`mebuki filing --doc-id` に渡せる） |

> **分析ヒント**: 粗利率と営業利益率の差が大きい場合は販管費（人件費・広告費等）が重い構造。両者の推移を比較することで、コスト管理の効率改善・悪化を把握できる。

例：
```bash
mebuki analyze 7203
mebuki analyze 7203 --years 5
mebuki analyze 7203 --half                           # 上半期・下半期の推移を表示（デフォルト3年）
mebuki analyze 7203 --half --years 5                 # 5年分の半期推移
mebuki analyze 7203 --no-cache                       # キャッシュ無効化
```

### ③ EDINETファイリング一覧

EDINETに提出された書類の一覧を取得する。

```bash
mebuki filings <code> [--format table|json]
```

例：
```bash
mebuki filings 7203
mebuki filings 7203 --format json
```

### ④ 有価証券報告書セクション抽出

有価証券報告書から特定セクションを抽出する。

```bash
mebuki filing <code> [--doc-id DOC_ID] [--sections business_risks|mda|management_policy] [--format table|json]
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
mebuki filing 7203 --format json
```

### ⑤ ウォッチリスト管理

注目銘柄のウォッチリストを管理する。

```bash
mebuki watch add <code> [--name 備考] [--format table|json]
mebuki watch remove <code> [--format table|json]
mebuki watch list [--format table|json]
```

例：
```bash
mebuki watch add 7203 --name "トヨタ自動車"
mebuki watch list
mebuki watch list --format json
mebuki watch remove 7203
```

### ⑥ ポートフォリオ管理

保有銘柄のポートフォリオを管理する。

```bash
# 買付
mebuki portfolio add <code> <数量> <取得単価> [--broker 証券会社] [--account 特定|一般|NISA] [--date YYYY-MM-DD] [--name 銘柄名] [--format table|json]

# 売却
mebuki portfolio sell <code> <数量> [--broker 証券会社] [--account 特定|一般|NISA] [--format table|json]

# 銘柄削除
mebuki portfolio remove <code> [--broker 証券会社] [--account 特定|一般|NISA] [--format table|json]

# 一覧表示
mebuki portfolio list [--detail] [--format table|json]
```

例：
```bash
mebuki portfolio add 7203 100 2500 --broker SBI --account 特定
mebuki portfolio add 7203 100 2500 --name "トヨタ自動車"   # 銘柄名を手動指定（省略時は自動取得）
mebuki portfolio list --detail
mebuki portfolio list --format json
mebuki portfolio sell 7203 50
mebuki portfolio remove 7203 --broker SBI --account 特定
```

## 典型ワークフロー

### 株式調査フロー

新規銘柄を調査する際の標準フロー：

1. **銘柄特定**: `mebuki search <社名>` でコードを確認
2. **財務分析**: `mebuki analyze <code> --years 5` で財務推移を確認（ROIC・有利子負債を含む）
   - 半期推移も確認したい場合: `--half` を追加
3. **書類一覧**: `mebuki filings <code>` でEDINET提出書類を確認
4. **報告書抽出**: `mebuki filing <code> --sections business_risks mda` でリスクと経営状況を確認

### 銘柄管理フロー

銘柄を追加・管理する際のフロー：

1. **ウォッチ登録**: `mebuki watch add <code> --name <備考>`
2. **買付記録**: `mebuki portfolio add <code> <数量> <単価>`
3. **保有確認**: `mebuki portfolio list --detail`

### 複数銘柄比較フロー

同セクター内の銘柄を横断比較する際の標準フロー。

```bash
# 1. 銘柄コード確認（社名で検索）
mebuki search <社名A>
mebuki search <社名B>
mebuki search <社名C>

# 2. 財務サマリー（デフォルト: ROIC・有利子負債を含む）
mebuki analyze <codeA> --years 5
mebuki analyze <codeB> --years 5
mebuki analyze <codeC> --years 5

# 3. 有価証券報告書でリスクと経営方針を確認
mebuki filing <codeA> --sections business_risks mda management_policy
mebuki filing <codeB> --sections business_risks mda management_policy
mebuki filing <codeC> --sections business_risks mda management_policy
```

**比較ポイント**:

| 指標 | 着眼点 |
|---|---|
| 粗利率 (%) | 製品競争力・価格支配力。業界内で高いほど優位性がある |
| 営業利益率 (%) | 本業の収益性。粗利率との差（販管費率）も業界横断で比較できる |
| ROE | 自己資本に対する収益性。同業他社との比較で経営効率を判断 |
| ROIC | 投下資本全体に対するリターン。資本効率の本質的な指標 |
| 配当性向 | 株主還元方針の違いを比較 |
| 営業CF | 稼ぐ力の実態。利益と乖離する場合は収益の質を疑う |

> **業界特性による読み替え**: 銀行・保険はROICの定義が事業会社と異なるためROEを主軸に。製造業は粗利率と営業利益率の差（販管費の重さ）が競争力の差に直結。SaaSなどのストック型ビジネスは営業CFの安定性・成長率を重視する。

---

## 指標の定義と計算式

### ROIC

```
ROIC (%) = 当期純利益 ÷ 投下資本 × 100
投下資本  = 自己資本 + 有利子負債合計
```

> **注意**: 一般的な教科書定義（NOPAT ÷ 投下資本）とは異なり、mebuki では **当期純利益（NP）** を使って計算している。税引後営業利益ではないため、財務収益・特別損益・税率の影響を含む。同業他社との比較は同じ計算式のもの同士で行うこと。

### ROE

```
ROE (%) = 当期純利益 ÷ 自己資本 × 100
```

---

## 有利子負債（IBD）の定義と抽出ロジック

### 定義（構成要素）

| # | 項目 | J-GAAP XBRLタグ | IFRS XBRLタグ |
|---|---|---|---|
| 1 | 短期借入金 | ShortTermLoansPayable | BorrowingsCLIFRS |
| 2 | コマーシャル・ペーパー | CommercialPapersLiabilities | CommercialPapersCLIFRS |
| 3 | 短期社債 | ShortTermBondsPayable | —（J-GAAP専用） |
| 4 | 1年内償還予定の社債 | CurrentPortionOfBonds | CurrentPortionOfBondsCLIFRS |
| 5 | 1年内返済予定の長期借入金 | CurrentPortionOfLongTermLoansPayable | CurrentPortionOfLongTermBorrowingsCLIFRS |
| 6 | 社債 | BondsPayable | BondsPayableNCLIFRS |
| 7 | 長期借入金 | LongTermLoansPayable | BorrowingsNCLIFRS |

> **IFRS集約タグ**: 粒度別タグが存在しない場合、以下の集約タグで #4+#5 または #6+#7 をまとめて取得する。
> - `CurrentPortionOfLongTermDebtCLIFRS` → #4+#5
> - `BondsAndBorrowingsCLIFRS` → #4+#5（代替）
> - `LongTermDebtNCLIFRS` → #6+#7
> - `BondsAndBorrowingsNCLIFRS` → #6+#7（代替）

### 抽出戦略（優先順位）

1. **直接法**: `InterestBearingDebt` / `InterestBearingLiabilities` タグが存在すればそれを使用
2. **積み上げ法**: 上記7コンポーネントを個別取得して合算（J-GAAP / IFRS）
3. **US-GAAP**: XBRLに対応タグがないため、有価証券報告書HTML内の借入金ノートセクションをパースして抽出

### 出力フィールド

`mebuki analyze <code> --scope raw` で確認できる生データの構造:

| フィールド | 内容 |
|---|---|
| `InterestBearingDebt` | 有利子負債合計（百万円） |
| `IBDComponents` | 各コンポーネントの当期・前期値（百万円） |
| `IBDAccountingStandard` | 会計基準: `J-GAAP` / `IFRS` / `US-GAAP` |
| `IBDDocID` | IBD抽出元のEDINET書類ID（表示ラベル: `DocID`） |

---

## WACC（加重平均資本コスト）

### 計算式

```
Re   = Rf + β × MRP          # 株主資本コスト（CAPM）
Rd   = 支払利息 ÷ 有利子負債  # 負債コスト（税引前）
E    = 自己資本（帳簿純資産）
D    = 有利子負債合計
V    = E + D
WACC = (E/V) × Re + (D/V) × Rd × (1 − Tc)
```

### パラメータ

| パラメータ | 値・取得方法 | 備考 |
|---|---|---|
| **Rf** | 財務省公表 10年国債流通利回り（FY終了日時点） | 毎営業日更新 CSV から取得・1日キャッシュ |
| **β** | 1.0（固定） | 暫定値（市場平均） |
| **MRP** | 5.5%（固定） | 日本株 市場リスクプレミアム標準値 |
| **E** | `Eq`（帳簿純資産、百万円） | J-Quants から取得 |
| **D** | `InterestBearingDebt`（百万円） | EDINET XBRL 貸借対照表から抽出 |
| **Rd** | `InterestExpense` ÷ `InterestBearingDebt` | EDINET XBRL 損益計算書から抽出 |
| **Tc** | `EffectiveTaxRate`（%） | EDINET XBRL 損益計算書から算出 |

### FY別Rfの取得ロジック

各FYの **fy_end 日付** に対応する10年国債利回りを使用する。

- データソース1: `jgbcm_all.csv`（前月末まで）
- データソース2: `jgbcm.csv`（当月分）
- FY終了日当日の値がない場合（休日等）は最大14日遡って直前営業日の値を使用
- どちらも取得できない場合のフォールバック: 1.0%

これにより、ゼロ金利期（2021年 Rf≈0.1%）と金利上昇後（2025年 Rf≈1.5%）のRe・WACCの変化を年次ごとに正確に反映する。

### 出力フィールド（CalculatedData）

| フィールド | 内容 | 単位 |
|---|---|---|
| `CostOfEquity` | 株主資本コスト = Rf + β×MRP | % |
| `CostOfDebt` | 負債コスト = IE/IBD × 100（IBD=0 の場合は None） | % |
| `WACC` | 加重平均資本コスト（IE・Tc が None の場合は None） | % |

### 特殊ケース

| 条件 | 挙動 |
|---|---|
| IBD = 0（無借金企業） | CostOfDebt = None、WACC = Re |
| IE または Tc が取得できない | CostOfDebt/WACC = None、CostOfEquity のみ表示 |
| `--half` モード | 半期データには IE・Tc が含まれないため WACC 非表示 |

### 留意点

- **E は帳簿純資産**。時価総額ではないため D/(D+E) 比率に影響する。将来的には J-Quants の株価データで時価ベースに移行予定。
- **β=1.0 は暫定値**。実測βは株価時系列と市場インデックスの共分散から計算するが、EDINET/XBRLには記載がないため現時点では固定。
- **ROIC との違い**: ROIC は NP/(Eq+IBD) × 100。WACC は資本コストの加重平均であり、ROICと比較することで経済的付加価値（EVA）の判断ができる（ROIC > WACC なら価値創造）。
