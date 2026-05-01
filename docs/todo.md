# コードベース構成採点レポート

バージョン: v2.19.2  
評価日: 2026-05-01

---

## 採点サマリー

| 次元 | スコア |
|---|---|
| 保守性 | A− |
| パフォーマンス | B+ |
| テスト | B− |
| 型安全性 | B |
| CLI/MCP パリティ | A |
| DRY | A− |
| **総合** | **B+** |

---

## 保守性 — A−

### 強み

- 依存方向が明確（`app → services → api/analysis/infrastructure/utils`）で逆流なし。`tests/test_dependency_rules.py` で自動検証されている
- 平均ファイルサイズ約166行。一画面に収まるファイルが多く読むコストが低い
- 定数を `mebuki/constants/` に集約。マジックナンバーがほぼない
- `CLAUDE.md` + `.claude/rules/*.md` で規約が明文化されており、将来の変更者が迷いにくい

### 弱み

- ~~`utils/financial_data.py`（677行）が重力井戸化している可能性。データ抽出・重複排除・集計が混在しており変更時の影響範囲が読みにくい~~ → 437行に削減済（2026-04-30）
- ~~`analysis/interest_bearing_debt.py`（556行）は会計基準検出・XBRL 解析・HTML パースを1ファイルに抱えており分割候補~~ → US-GAAP HTML パースを `ibd_usgaap_html.py` に分離し 346行に削減済。Instant コンテキスト関数も `context_helpers.py` に統合済（2026-05-01）
- ~~`services/analyzer.py` が各 analysis モジュールに直接依存。新しい財務指標を追加するたびにこのファイルを触ることになる~~ → `ExtractorSpec` レジストリに統合済（2026-05-01）


---

## パフォーマンス — B+

### 強み

- API クライアントは全て async（aiohttp）。CLI からは `asyncio.run()` で呼んでおり構造は正しい
- ファイルベースキャッシュ（7日 TTL）＋メモリキャッシュ（メタデータ）の2段構成
- 429 レートリミットに 60秒 wait で対応
- タイムアウト管理が実装済（analyze: 180秒、filings: 60秒）
- EDINET の ZIP 取得はキャッシュ済みで同一 filing の再ダウンロードなし

### 弱み

- API 呼び出しが逐次実行。analyze 時に J-QUANTS + EDINET を `asyncio.gather` で並列化できれば体感速度は改善できる
- ~~XBRL のパース結果がキャッシュされていない。同一 filing を複数の分析モジュールが処理する場合、XML の parse が重複する~~ → セッションキャッシュ済（2026-05-01）
- `financial_data.py` の annual/半期データ構築ループで dedup 処理の計算量が高い可能性

---

## テスト — B−

### 強み

- XBRL 解析系のユニットテストが厚い（テストコード全体の64%）。最も複雑な `interest_bearing_debt.py` に 799行のテストがある
- 依存規則テスト（`tests/test_dependency_rules.py`）で CI 時にアーキテクチャ退行を検出できる
- MCP/CLI のコントラクトテスト（ツール名・引数が壊れていないか）が存在する

### 弱み

- ~~`services/data_service.py`（449行）と `services/portfolio_service.py`（314行）のテストが存在しない~~ → 計44件追加済（2026-04-30）
- 非同期パスのテストが少ない（`IndividualAnalyzer.fetch_analysis_data` の EDINET 並列取得パスは追加済: 2026-05-01）
- CLI の統合テストが少ない（`main()` 経由の主要 JSON パスは追加済: 2026-05-01）

### テストファイル一覧

| ファイル | 行数 | 対象 |
|---|---|---|
| `test_xbrl_interest_bearing_debt.py` | 799 | IBD 抽出（会計基準横断） |
| `test_analyzer_apply_functions.py` | 415 | Analyzer のメトリクス適用関数 |
| `test_xbrl_tax_expense.py` | 268 | 実効税率計算 |
| `test_xbrl_gross_profit.py` | 263 | 売上総利益 context マッチング |
| `test_xbrl_interest_expense.py` | 258 | 支払利息抽出 |
| `test_jquants_utils_fix.py` | 98 | J-QUANTS レスポンスパース |
| `test_dup_deduplication.py` | 93 | データ重複排除 |
| `test_xbrl_refactor_unit.py` | 83 | XBRL ユーティリティ |
| `test_cli_analyze_years.py` | 75 | CLI パラメーター |
| `test_dependency_rules.py` | 52 | アーキテクチャ依存規則 |
| `test_calculator_update.py` | 36 | メトリクス計算 |
| `test_mcp_contract.py` | 26 | MCP ツールインターフェース |
| `test_cli_contract.py` | 10 | CLI 引数コントラクト |

---

## 型安全性 — B

### 強み

- 関数シグネチャに戻り値型が揃っており `Optional` の代わりに `X | None` 構文を使用
- Python 3.11+ の組み込み型（`list[str]`、`dict[K, V]`）で統一

### 弱み

- ~~辞書が深くネストしている箇所（`calculator.py` や `analyzer.py` が返す結果辞書など）に `TypedDict` が使われていない~~ → `metrics_types.py` で主要型を定義済（2026-04-30）
- 値型が `str | float | None` 程度に絞れる場合でも `Any` で代替している箇所がある

---

## CLI/MCP パリティ — A

`.claude/rules/project/mcp-cli-parity.md` に対応表が明文化されており、9ツール中7ツールが CLI と対応。  
残り2つ（`config`、`mcp install`）はユーザー設定・インストーラー用途で MCP から除外するのは合理的。

---

## DRY — A−

XBRL の context ヘルパーが `analysis/context_helpers.py` に Duration・Instant 両系統で集約され、parse/collect/find の共通処理が `analysis/xbrl_utils.py` に分離されており重複は少ない。  
`edinet_fetcher.py` の7つのボイラープレートメソッドも `ExtractorSpec` レジストリ＋汎用 `_extract_metric_by_year` に統合済（2026-05-01）。  
残る減点は `services/edinet_fetcher.py` と `api/edinet_client.py` の責任境界が若干曖昧な点のみ。

---

## ファイルサイズ分布（上位15件）

| ファイル | 行数 | 主な懸念 |
|---|---|---|
| `analysis/interest_bearing_debt.py` | ~~556~~ 346 | ~~3会計基準 + XBRL/HTML が混在~~ HTML パース分離済 |
| `analysis/ibd_usgaap_html.py` | 225 | US-GAAP HTML 借入金ノートパース |
| `analysis/xbrl_parser.py` | 517 | - |
| `services/edinet_fetcher.py` | 512 | - |
| `services/data_service.py` | 449 | シングルトンが複数の関心を持つ |
| `api/edinet_client.py` | 427 | - |
| `utils/financial_data.py` | 437 | ~~677行→~~ デッドコード削除済 |
| `app/mcp_server.py` | 354 | - |
| `analysis/gross_profit.py` | 355 | - |
| `app/cli/analyze.py` | 345 | - |
| `analysis/tax_expense.py` | 330 | - |
| `utils/converters.py` | 321 | - |
| `services/portfolio_service.py` | 314 | - |
| `app/cli/mcp.py` | 304 | - |
| `services/analyzer.py` | 275 | ~~analysis モジュール全依存~~ レジストリ化済 |
| `analysis/interest_expense.py` | 281 | - |

---

## 優先改善候補

コスト対効果の高い順に列挙する。

### ~~1. サービス層のテスト追加~~ ✅ 完了 (2026-04-30)

`tests/test_data_service.py`（20件）と `tests/test_portfolio_service.py`（24件）を追加。  
計44件すべてパス。

### ~~2. `financial_data.py` の整理~~ ✅ 完了 (2026-04-30)

デッドコード（`extract_quarterly_data`・`_calculate_quarter_end_date`）を削除し 677行 → 437行に削減。  
株価取得関数（`get_monthly_avg_stock_price` 等）は将来実装のため残置。

### ~~3. 結果辞書への TypedDict 導入~~ ✅ 完了 (2026-04-30)

`mebuki/utils/metrics_types.py` に `IBDComponent` / `RawData` / `CalculatedData` / `YearEntry` / `MetricsResult` を定義。  
`calculator.py` と `analyzer.py` の関数シグネチャに適用。  
`.claude/rules/project/typing.md` に TypedDict 置き場所ルールと `total=False` の使い分けを追記。

### ~~4. J-QUANTS + EDINET の並列化~~ ✅ 完了 (2026-05-01)

`fetch_edinet_data_async`（書類メタデータ取得）を `predownload_and_parse`（XBRLダウンロード）と
`asyncio.gather` で並列実行するよう `analyzer.py` を変更。  
変更前: `predownload → [fetch_edinet_data + extract_all]`  
変更後: `[predownload + fetch_edinet_data] → extract_all`  
`fetch_edinet_data_async` は `financial_data` のみ必要で `pre_parsed_map` 不要なため並列化可能。  
140 件すべてパス。

### ~~5. XBRL パース結果のセッションキャッシュ~~ ✅ 完了 (2026-05-01)

`collect_all_numeric_elements`（`xbrl_utils.py`）を追加し、`EdinetFetcher.predownload_and_parse` で
全年度ドキュメントを一括ダウンロード・パース（1文書1回）。  
`pre_parsed_map` を 7 つの `extract_*_by_year` メソッドと `_process_doc`（半期）に伝搬させ、  
XML parse 呼び出しを 7N 回 → N 回 に削減（N = 対象年度数、通常 5）。  
全分析モジュール（`gross_profit`, `interest_bearing_debt`, `tax_expense`, `interest_expense`,
`employees`, `net_revenue`, `operating_profit`, `cash_flow`）に `pre_parsed` パラメータを追加。  
140 件すべてパス。

### ~~6. `analyzer.py` の analysis モジュール依存を解消~~ ✅ 完了 (2026-05-01)

`edinet_fetcher.py` に `ExtractorSpec` dataclass と `_EXTRACTOR_SPECS` レジストリを追加。  
7つのボイラープレートメソッドを汎用 `_extract_metric_by_year` ＋ 1行ラッパーに置き換え、  
新メソッド `extract_all_by_year` で全メトリクスを並列取得する口を一本化。  
`analyzer.py` の 9 変数宣言＋9 要素 gather＋8 apply 呼び出しを `_METRIC_APPLIERS` リスト＋ループに置き換え。  
新メトリクス追加時の変更箇所: `_EXTRACTOR_SPECS` に 1 行追加、`_METRIC_APPLIERS` に 1 行追加のみ。  
140 件すべてパス。

### ~~7. `interest_bearing_debt.py` の分割~~ ✅ 完了 (2026-05-01)

US-GAAP HTML パース（`_determine_column_order` / `_find_loan_section_pos` / `_parse_loan_tables` / `_extract_usgaap_from_html`）を `ibd_usgaap_html.py`（225行）に分離。  
`interest_bearing_debt.py` は 556行 → 346行に削減（XBRL解析・会計基準検出・メイン抽出ロジックのみ）。  
あわせて `employees.py` との Instant コンテキスト関数の重複を解消し、`context_helpers.py` に Duration・Instant 両系統を統合。  
`constants/xbrl.py` に `INSTANT_CONTEXT_PATTERNS` / `PRIOR_INSTANT_CONTEXT_PATTERNS` を追加。  
140 件すべてパス。
