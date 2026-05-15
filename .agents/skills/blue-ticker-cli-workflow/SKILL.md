---
name: blue-ticker-cli-workflow
description: BLUE TICKER CLIを使って日本株の検索・財務分析・有価証券報告書抽出・ウォッチリスト/ポートフォリオ管理を行う汎用ワークフロースキル
---

# BLUE TICKER CLIワークフロー

このスキルは、BLUE TICKER CLIコマンドを直接操作して日本株の調査・分析・管理を行います。

## 使用例
- 「トヨタをBLUE TICKERで分析して」
- 「7203のポートフォリオに追加して」
- 「ウォッチリストを見せて」
- 「直近の株価を取得して」
- 「ソニーの有価証券報告書を取得して」

## 厳格なルール
- **売買推奨の禁止**: データは客観的に提示し、最終判断は必ずユーザーに委ねること。
- **データの忠実な提示**: BLUE TICKERコマンドの出力をそのまま提示し、恣意的な解釈を加えないこと。
- **ticker分析時のネット検索禁止**: `ticker analyze` や証券コード・銘柄名を指定したBLUE TICKER分析では、Web検索を使わず、BLUE TICKER CLIの出力・キャッシュ済みEDINETデータ・CLIが取得する公的データに基づいて回答すること。ユーザーが明示的に「ネット検索して」「最新ニュースも含めて」などと依頼した場合のみ、分析とは別枠で検索結果を扱う。
- **API負荷軽減のためのキャッシュ優先**: `analyze` / `filings` / `filing` などEDINETデータを使う調査コマンドの前に、必ず `ticker cache status` を実行すること。キャッシュが不足している場合は、調査コマンドへ進む前に `ticker cache prepare` または `ticker cache catchup` を実行する。

## 必須の事前チェック

実行前に設定を確認する：

```bash
ticker config show
```

未設定の場合は以下で初期化を案内する：

```bash
ticker config init
```

日本株の調査・分析依頼では、銘柄検索だけで完了する場合を除き、最初にキャッシュ状態を確認する：

```bash
ticker cache status
```

`cache status` の `next_action` が `ticker cache prepare --years N` を示す場合は、調査コマンドの前に実行する。既に準備済みの場合はすぐ終わる：

```bash
ticker cache prepare --years 5
```

`cache status` の `next_action` が `ticker cache catchup --years N` を示す場合は、不足分だけ追いつかせる：

```bash
ticker cache catchup --years 5
```

`--years` はユーザーが求める分析・ファイリング探索年数に合わせる。指定がなければ通常調査では CLI デフォルトの `5`、長期の財務分析を行う場合は分析年数に合わせて `6` を使う。

## コマンドリファレンスと実行フロー

### ① 銘柄検索

社名や証券コードで銘柄を検索する。

```bash
ticker search <社名またはコード> [--format table|json]
```

例：
```bash
ticker search トヨタ
ticker search 7203
ticker search 7203 --format json
```

### ② 財務分析

銘柄の財務データを分析する。

```bash
ticker analyze <code> [--years N] [--format table|json] [--half] [--no-cache] [--include-debug-fields]
```

- `--years N`: 取得年数（デフォルト: 6、`--half` 時は 3）。**FY（通期）の件数**でカウントする
- `--half`: 上半期(H1)・下半期(H2)の半期推移を表示する（seasonalityの確認に有用）
- `--no-cache`: キャッシュを使用せず最新データを取得する
- `--include-debug-fields`: `--format json` で `MetricSources`、`IBDComponents`、`GrossProfitMethod`、`IBDAccountingStandard` などの内部検証フィールドも出力する

> **WACCとキャッシュ**: WACCのリスクフリーレートには財務省10年国債利回りCSVを使う。金利データ自体は1日TTLでキャッシュされるが、分析結果キャッシュに保存済みのWACCは再計算されない。最新の財務省金利を反映したWACCを確認する場合は、`ticker analyze <code> --no-cache` を使う。

デフォルト出力に含まれる主要財務指標（横並び年次推移）:

| 項目 | 用途・ポイント |
|---|---|
| 売上高 | トップライン成長確認 |
| 売上総利益 | 粗利の絶対額 |
| **粗利率 (%)** | 製品競争力・価格支配力の指標 |
| 営業利益 | 本業の稼ぎ |
| **営業利益率 (%)** | 本業の収益性。粗利率との差 = 販管費率 |
| NOPAT / ROE / ROIC | 税引後営業利益と資本効率 |
| 営業CF / 投資CF / フリーCF | キャッシュフロー |
| 配当性向 | 株主還元方針 |
| 有利子負債合計 / 投下資本 | 財務健全性・ROIC計算基盤 |
| DocID | IBD・GP抽出元のEDINET書類ID（`ticker filing --doc-id` に渡せる） |

> **金融機関の業務粗利益**: 銀行など金融機関では、通常の `売上総利益` ではなく `業務粗利益` を使う。計算式は `連結業務粗利益 = (資金運用収益 - 資金調達費用) + 信託報酬 + (役務取引等収益 - 役務取引等費用) + (特定取引収益 - 特定取引費用) + (その他業務収益 - その他業務費用)`。営業利益前年差分解でも、`GrossProfitLabel` が `業務粗利益` の場合は粗利率差影響を `業務粗利益 ÷ 経常収益` の率差で計算する。`ticker analyze --format table` の表示名は、抽出された `CalculatedData` のラベルに合わせて変わるため、表では `売上総利益 (百万)` / `粗利率 (%)` / `粗利率差影響` ではなく `業務粗利益 (百万)` / `業務粗利益率 (%)` / `業務粗利益率差影響` と表示される。JSONでは `GrossProfit` に数値、`GrossProfitLabel` に表示名が入る。

> **分析ヒント**: 粗利率と営業利益率の差が大きい場合は販管費（人件費・広告費等）が重い構造。両者の推移を比較することで、コスト管理の効率改善・悪化を把握できる。

例：
```bash
ticker analyze 7203
ticker analyze 7203 --years 6
ticker analyze 7203 --half                           # 上半期・下半期の推移を表示（デフォルト3年）
ticker analyze 7203 --half --years 5                 # 5年分の半期推移
ticker analyze 7203 --no-cache                       # キャッシュ無効化
ticker analyze 7203 --format json --include-debug-fields
```

### ③ EDINETファイリング一覧

EDINETに提出された書類の一覧を取得する。

```bash
ticker filings <code> [--years N] [--format table|json]
```

- `--years N`: EDINET書類探索年数（デフォルト: 3）

例：
```bash
ticker filings 7203
ticker filings 7203 --years 6
ticker filings 7203 --format json
```

### ④ 有価証券報告書セクション抽出

有価証券報告書から特定セクションを抽出する。

```bash
ticker filing <code> [--doc-id DOC_ID] [--sections business_risks|mda|management_policy] [--format table|json]
```

- `--doc-id`: ③で取得したドキュメントID（省略時は最新）
- `--sections`: 抽出するセクション（複数指定可）
  - `business_risks`: 事業等のリスク
  - `mda`: 経営者による財政状態・経営成績の分析（MD&A）
  - `management_policy`: 経営方針

例：
```bash
ticker filing 7203
ticker filing 7203 --sections business_risks mda
ticker filing 7203 --doc-id S100XXXX --sections mda
ticker filing 7203 --format json
```

### ⑤ 業種検索

東証33業種で銘柄を検索する。業種名を省略すると業種一覧を表示する。

```bash
ticker sector [業種名] [--format table|json]
```

例：
```bash
ticker sector
ticker sector 輸送用機器
ticker sector 情報・通信業 --format json
```

### ⑥ ウォッチリスト管理

注目銘柄のウォッチリストを管理する。

```bash
ticker watch add <code> [--name 備考] [--format table|json]
ticker watch remove <code> [--format table|json]
ticker watch list [--format table|json]
```

例：
```bash
ticker watch add 7203 --name "トヨタ自動車"
ticker watch list
ticker watch list --format json
ticker watch remove 7203
```

### ⑦ ポートフォリオ管理

保有銘柄のポートフォリオを管理する。

```bash
# 買付
ticker portfolio add <code> <数量> <取得単価> [--broker 証券会社] [--account 特定|一般|NISA] [--date YYYY-MM-DD] [--name 銘柄名] [--format table|json]

# 売却
ticker portfolio sell <code> <数量> [--broker 証券会社] [--account 特定|一般|NISA] [--format table|json]

# 銘柄削除
ticker portfolio remove <code> [--broker 証券会社] [--account 特定|一般|NISA] [--format table|json]

# 一覧表示
ticker portfolio list [--detail] [--format table|json]

# セクター別配分
ticker portfolio sector [--format table|json]
```

例：
```bash
ticker portfolio add 7203 100 2500 --broker SBI --account 特定
ticker portfolio add 7203 100 2500 --name "トヨタ自動車"   # 銘柄名を手動指定（省略時は自動取得）
ticker portfolio list --detail
ticker portfolio list --format json
ticker portfolio sell 7203 50
ticker portfolio remove 7203 --broker SBI --account 特定
ticker portfolio sector
```

### ⑧ キャッシュ管理

EDINET年次インデックスや分析キャッシュの状態確認・準備・更新・整理を行う。

```bash
ticker cache status [--years N] [--format table|json]
ticker cache prepare [--years N] [--format table|json]
ticker cache catchup [--years N] [--format table|json]
ticker cache refresh [--years N] [--format table|json]
ticker cache clean [--execute] [--edinet-search-days N] [--edinet-xbrl-days N] [--edinet-doc-index-years N] [--format table|json]
```

- `status`: キャッシュ状態と次の推奨アクションを表示する
- `prepare`: EDINET年次インデックスを事前準備する
- `catchup`: 不足分のEDINET年次インデックスを取得する
- `refresh`: EDINET年次インデックスを更新する
- `clean`: 不要なキャッシュを削除する。`--execute` 未指定時は dry-run

例：
```bash
ticker cache status
ticker cache prepare --years 5
ticker cache catchup --years 5
ticker cache refresh --years 5
ticker cache clean --edinet-search-days 30
ticker cache clean --execute --edinet-xbrl-days 30
```

## 典型ワークフロー

### 株式調査フロー

新規銘柄を調査する際の標準フロー：

1. **キャッシュ確認**: `ticker cache status` を実行し、必要なら表示された `next action`（例: `ticker cache prepare --years 5` / `ticker cache catchup --years 5`）を実行
2. **銘柄特定**: `ticker search <社名>` でコードを確認
3. **財務分析**: `ticker analyze <code> --years 6` で財務推移を確認（ROIC・有利子負債を含む）
   - 半期推移も確認したい場合: `--half` を追加
4. **書類一覧**: `ticker filings <code>` でEDINET提出書類を確認
5. **報告書抽出**: `ticker filing <code> --sections business_risks mda` でリスクと経営状況を確認

### 銘柄管理フロー

銘柄を追加・管理する際のフロー：

1. **ウォッチ登録**: `ticker watch add <code> --name <備考>`
2. **買付記録**: `ticker portfolio add <code> <数量> <単価>`
3. **保有確認**: `ticker portfolio list --detail`

### 複数銘柄比較フロー

同セクター内の銘柄を横断比較する際の標準フロー。

```bash
# 1. キャッシュ確認と不足分の準備
ticker cache status
ticker cache catchup --years 5  # statusが不足を示した場合のみ

# 2. 銘柄コード確認（社名で検索）
ticker search <社名A>
ticker search <社名B>
ticker search <社名C>

# 3. 財務サマリー（デフォルト: ROIC・有利子負債を含む）
ticker analyze <codeA> --years 6
ticker analyze <codeB> --years 6
ticker analyze <codeC> --years 6

# 4. 有価証券報告書でリスクと経営方針を確認
ticker filing <codeA> --sections business_risks mda management_policy
ticker filing <codeB> --sections business_risks mda management_policy
ticker filing <codeC> --sections business_risks mda management_policy
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
ROIC (%) = NOPAT ÷ 投下資本 × 100
投下資本  = 自己資本 + 有利子負債合計
NOPAT    = 営業利益 × (1 - 実効税率)
```

実効税率が未取得または異常値の場合は、35%のフォールバック税率で NOPAT を計算する。ROIC は当期純利益（NP）ではなく NOPAT を使うため、財務収益・特別損益の影響を除いた本業ベースの投下資本収益率として見る。

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

`ticker analyze <code> --include-debug-fields --format json` で確認できる詳細データの構造:

| フィールド | 内容 |
|---|---|
| `InterestBearingDebt` | 有利子負債合計（百万円） |
| `IBDComponents` | 各コンポーネントの当期・前期値（百万円） |
| `IBDAccountingStandard` | 会計基準: `J-GAAP` / `IFRS` / `US-GAAP` |
| `DocID` | 指標抽出元のEDINET書類ID |

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
| **E** | `NetAssets`（純資産、百万円） | EDINET XBRL から取得 |
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

- **E は帳簿純資産**。時価総額ではないため D/(D+E) 比率に影響する。将来的には外部株価データで時価ベースに移行予定。
- **β=1.0 は暫定値**。実測βは株価時系列と市場インデックスの共分散から計算するが、EDINET/XBRLには記載がないため現時点では固定。
- **ROIC との違い**: ROIC は NOPAT/(NetAssets+IBD) × 100。WACC は資本コストの加重平均であり、ROICと比較することで経済的付加価値（EVA）の判断ができる（ROIC > WACC なら価値創造）。

---

## バランスシート構造分析（積み上げ棒グラフ）

### 概要

`ticker analyze` で取得した貸借対照表データを2本の積み上げ棒グラフとして可視化し、資産構成と資本調達構造の変化を年次で比較する。

- **左棒（資産サイド）**: 流動資産（上）＋ 固定資産（下）
- **右棒（負債・純資産サイド）**: 流動負債（上）＋ 固定負債（中）＋ 純資産（下）

左右の合計（総資産）は一致する。両棒を並べることで調達と運用の対応関係が一目で分かる。

### 使用フィールド（CalculatedData）

| フィールド | 表示ラベル | 単位 |
|---|---|---|
| `CurrentAssets` | 流動資産 | 百万円 |
| `NonCurrentAssets` | 固定資産 | 百万円 |
| `CurrentLiabilities` | 流動負債 | 百万円 |
| `NonCurrentLiabilities` | 固定負債 | 百万円 |
| `NetAssets` | 純資産 | 百万円 |

> これらはEDINET有価証券報告書のXBRLから抽出した値。J-GAAP/IFRS/US-GAAPすべてに対応。

### データ取得

```bash
ticker analyze <code> --years 6
```

または `--format json` で取得してプロットに利用する。

### グラフ仕様

- **横軸**: 年度（FY終了年月 または FY終了年）
- **縦軸**: 百万円（必要に応じてスケール調整）
- **凡例**: 流動資産・固定資産・流動負債・固定負債・純資産の5色
- **年次並べ方**: 各年で左棒（資産）・右棒（負債＋純資産）を隣接配置

### 読み方・着眼点

| 観点 | チェックポイント |
|---|---|
| **流動比率** | 流動資産 ÷ 流動負債 ≥ 1.5 が目安。短期の支払能力 |
| **固定長期適合率** | 固定資産 ÷ (固定負債＋純資産) ≤ 1 が健全。固定資産を長期資本で賄えているか |
| **自己資本比率** | 純資産 ÷ 総資産。製造業 40%以上、サービス業 30%以上が目安 |
| **資産規模の推移** | 総資産の拡大・縮小トレンドと収益性の関係 |
| **負債構成の変化** | 固定負債増（設備投資）vs 流動負債増（運転資本圧迫）の識別 |

---

## 営業利益増減分析

### 概要

営業利益の前年差を「売上高（数量の影響）」「粗利率（採算の影響）」「販管費（コストの影響）」の3要素に分解する。交互作用を排除した設計により、3要素の合計が営業利益の前年差額と完全に一致する。

### 計算式

```
売上差影響    = (当期売上高 - 前期売上高) × 前期粗利率
粗利率差影響  = 当期売上高 × (当期粗利率 - 前期粗利率)
販管費増影響  = -(当期販管費 - 前期販管費)

検証: 売上差影響 + 粗利率差影響 + 販管費増影響 = 営業利益の前期差額
```

- **売上差影響**: 売上の増減が「前期並みの採算」で推移したと仮定した場合の利益インパクト（数量効果）
- **粗利率差影響**: 採算性の変化（原価改善・価格転嫁等）が当期売上に与えた利益インパクト（採算効果）
- **販管費増影響**: 販管費の純増減。費用が増えた場合はマイナス（コスト効果）

### 使用フィールド（CalculatedData）

| フィールド | 表示ラベル | 単位 | 備考 |
|---|---|---|---|
| `OperatingProfitChange` | 営業利益前年差 | 百万円 | 当期OP - 前期OP |
| `SalesChangeImpact` | 売上差影響 | 百万円 | 数量効果 |
| `GrossMarginChangeImpact` | 粗利率差影響 | 百万円 | 採算効果 |
| `SGAChangeImpact` | 販管費増影響 | 百万円 | コスト効果（増加はマイナス） |
| `OperatingProfitChangeReconciliationDiff` | 検証差分 | 百万円 | 3要素合計との誤差。デバッグ用（通常は0） |

> これらは `ticker analyze` の通常出力に含まれる。

### データ取得

```bash
ticker analyze <code> --years 6
```

年次テーブルの「営業利益前年差」「売上差影響」「粗利率差影響」「販管費増影響」行に値が表示される。

### 可視化（ウォーターフォールチャートまたは積み上げ棒グラフ）

年次ごとに以下の値を可視化する：

```
OperatingProfitChange = SalesChangeImpact + GrossMarginChangeImpact + SGAChangeImpact
```

**推奨チャート**: ウォーターフォールチャート（各要素の正負を橋渡し表示）または年次比較の積み上げ棒グラフ。

### 読み方・着眼点

| パターン | 意味 |
|---|---|
| 売上差↑ / 粗利率差±0 / 販管費↑ | 増収だが費用増で増益が限定的。スケールアップ投資期 |
| 売上差±0 / 粗利率差↑ | 売上横ばいでも採算改善（価格転嫁・コスト削減成功） |
| 売上差↑ / 粗利率差↓ | 増収だが採算悪化。値引き・原材料高の影響を疑う |
| 3要素がすべてマイナス | トップライン・採算・コストの三重苦。構造的な問題の可能性 |
| 販管費増影響が大きくマイナス | 積極的な先行投資か、コスト管理の問題かを定性情報で確認 |

> **データ欠損時**: 売上総利益または販管費がXBRLから取得できない年は `None` となりすべての分解値が非表示になる。その場合は `ticker filing` で有報のMD&Aセクションを参照する。
