# アーキテクチャ課題と対応状況

作成日: 2026-05-02

このメモは、アーキテクチャ棚卸しで見つかった問題を「何が問題だったか」「何を直したか」「まだ何が残っているか」で追えるようにした対応台帳です。

詳細な構造図と指標カタログは `docs/architecture-review.md` を参照してください。

## 状況サマリー

| 領域 | 状況 | 一言 |
|---|---|---|
| CLI/MCP JSON出力 | 対応済み | 標準JSONからデバッグフィールドを除外し、必要時だけ明示出力する |
| 指標の出所情報 | 対応済み | `MetricSources` に集約し、内部計算では保持する |
| CLI/MCPパリティ | 対応済み | `--include-debug-fields` と MCP `include_debug_fields` を揃えた |
| キャッシュ可視化/削除 | 対応済み | stats/audit/prune を用意し、MCPは読み取りのみ |
| EDINETキャッシュ境界 | 一部対応 | `EdinetCacheStore` に分離済み。TTL/容量管理は未対応 |
| EDINET補完パイプライン | 未対応 | 年次と半期で補完経路がまだ分かれている |
| XBRL抽出結果の型 | 未対応 | 主要metrics型はあるが、抽出器戻り値はまだ緩い |
| 個別分析キャッシュ粒度 | 未対応 | 最終成果物キャッシュなのでロジック更新時に古い結果が残りうる |

## 対応済み

### 1. 標準JSONが内部デバッグ情報を出しすぎる

**問題**

`mebuki analyze --format json` と MCP `get_japan_stock_financial_data` が、内部計算用の `MetricSources` や `IBDComponents` まで返していた。MCP経由ではLLMが毎回そのメタデータを読むため、トークン消費が増える。利用者側から見ても、財務数値と検証用メタデータの境界が分かりにくかった。

**対応**

- `utils/output_serializer.py` を追加
- 標準JSONでは以下を除外
  - `MetricSources`
  - `IBDComponents`
  - `GrossProfitMethod`
  - `IBDAccountingStandard`
- `SalesLabel` / `OPLabel` は意味情報として標準JSONに残す
- `--include-debug-fields` / MCP `include_debug_fields` でデバッグフィールドを明示的に出せるようにした
- キャッシュには内部構造を保存し、返却時だけ整形する

**主なファイル**

- `mebuki/utils/output_serializer.py`
- `mebuki/services/data_service.py`
- `mebuki/services/half_year_data_service.py`
- `mebuki/app/cli/parser.py`
- `mebuki/app/mcp_server.py`

**残り**

標準JSONの公開フィールド一覧をドキュメントとテストでさらに固定する。

### 2. 半期データのEDINET失敗経路でデバッグ情報が漏れる

**問題**

半期データでEDINET補完が失敗した場合、早期returnが serializer を通らず、標準出力でも `MetricSources` が残っていた。

**対応**

- EDINET失敗時の早期returnも `serialize_half_year_periods()` を通すよう修正
- デフォルトでは除外されること、`include_debug_fields=True` では含まれることをテスト追加

**主なファイル**

- `mebuki/services/half_year_data_service.py`
- `tests/test_data_service.py`

**残り**

なし。

### 3. 指標の出所と手法が追いにくい

**問題**

J-QUANTS由来、EDINET由来、内部計算、財務省CSV由来の値が `CalculatedData` に混在していた。値がどこから来たのか、どの方法で補完されたのかを後から確認しづらかった。

**対応**

- `CalculatedData.MetricSources` に `source`, `method`, `docID`, `unit`, `label` を集約
- 年次・半期の主要指標で出所情報を付与
- 標準JSONでは出さず、デバッグ出力で確認する設計に整理

**主なファイル**

- `mebuki/analysis/calculator.py`
- `mebuki/services/analyzer.py`
- `mebuki/services/half_year_data_service.py`
- `mebuki/utils/metrics_types.py`

**残り**

抽出器ごとの戻り値型がまだ緩いため、`MetricSources` に入る前の段階は型で保証されていない。

### 4. EDINETキャッシュ処理がAPIクライアント内に寄りすぎていた

**問題**

EDINETの日別検索キャッシュとXBRL zip展開処理が `EdinetAPIClient` に直接入っており、通信責務とローカルファイル管理責務が混ざっていた。

**対応**

- `api/edinet_cache_store.py` を追加
- 日別検索キャッシュの読み書き、XBRL zip展開、安全なzip entry検証を `EdinetCacheStore` に分離
- `EdinetAPIClient` は通信とキャッシュストア呼び出しに寄せた

**主なファイル**

- `mebuki/api/edinet_cache_store.py`
- `mebuki/api/edinet_client.py`

**残り**

TTL、容量上限、LRU、キャッシュバージョン管理は未対応。

### 5. キャッシュ状態が見えず、安全に掃除しづらい

**問題**

古いキャッシュや廃止済み機能のキャッシュが残っても、ユーザーが状態を確認しづらかった。MCPから削除操作を提供すると事故リスクもある。

**対応**

- `mebuki cache stats` を追加
- `mebuki cache audit` を追加
- `mebuki cache prune` をdry-runデフォルトで追加
- MCP `get_japan_stock_cache_stats` は読み取り専用にした

**主なファイル**

- `mebuki/services/cache_pruner.py`
- `mebuki/app/cli/cache.py`
- `mebuki/app/mcp_server.py`

**残り**

EDINET検索/XBRLキャッシュの自動TTL運用は未対応。

### 6. XBRL抽出器追加時の変更箇所が多かった

**問題**

新しいEDINET抽出指標を足すたびに、`EdinetFetcher` と `IndividualAnalyzer` の複数箇所を手で増やす必要があり、漏れや重複が起きやすかった。

**対応**

- `ExtractorSpec` レジストリを導入
- 年次抽出器を `_EXTRACTOR_SPECS` に集約
- `extract_all_by_year` と `_METRIC_APPLIERS` で呼び出しを整理

**主なファイル**

- `mebuki/services/edinet_fetcher.py`
- `mebuki/services/analyzer.py`

**残り**

半期補完はまだ別経路なので、年次/半期で完全には統一されていない。

### 7. XBRL parse が指標ごとに重複していた

**問題**

同じXBRL文書を、売上総利益、有利子負債、税金、従業員数などの抽出器がそれぞれ parse すると、対象年度数に比例して無駄が増える。

**対応**

- `predownload_and_parse()` で文書ごとに一度だけ parse
- `pre_parsed` を各抽出器に渡す
- XML parse を複数指標で共有

**主なファイル**

- `mebuki/services/edinet_fetcher.py`
- `mebuki/analysis/xbrl_utils.py`
- `mebuki/analysis/*.py`

**残り**

`pre_parsed` の責務と型をさらに整理する余地がある。

## 一部対応

### 8. EDINETキャッシュを正式なキャッシュ層にする

**問題**

`CacheManager` 管理のJSONキャッシュと、EDINET配下のファイルキャッシュがまだ別系統。検索キャッシュとXBRL展開ディレクトリには、TTL、容量上限、バージョン管理がない。

**対応済み**

- `EdinetCacheStore` でAPI通信からファイル管理を分離
- cache stats/audit/prune で容量と古いEDINETキャッシュを見られるようにした

**未対応**

- 検索キャッシュのTTL
- XBRL展開ディレクトリの容量上限
- LRUまたは日数ベースの自動整理
- キャッシュ形式のバージョン管理
- `CacheManager` とEDINETキャッシュの統一的な統計/削除ポリシー

**次にやるなら**

まずTTLだけ入れる。空結果は短め、ヒットありは長めにする。

### 9. 型安全性

**問題**

主要な `CalculatedData` / `YearEntry` は型定義されたが、EDINET抽出器の戻り値はまだ `dict[str, Any]` が多い。抽出器ごとの `current`, `prior`, `method`, `docID`, `components` などが型で固定されていない。

**対応済み**

- `utils/metrics_types.py` に主要metrics系 `TypedDict` を追加
- Pyright は dev依存に追加済み
- 変更対象モジュール単位で型を見る方針をルール化

**未対応**

- XBRL抽出器戻り値の `TypedDict` 化
- `pre_parsed` の型境界整理
- 全体pyrightをCIで常時必須にするかの判断

**次にやるなら**

抽出器を一気に型付けせず、`interest_bearing_debt` や `gross_profit` など変更頻度の高いものから順に進める。

## 未着手

### 10. 年次/半期のEDINET補完パイプライン統合

**問題**

年次分析と半期分析で、EDINET書類検索、XBRL取得、GP/IBD/CF補完の呼び方が別経路になっている。似た処理がある一方で、半期固有のFY-H1計算もあり、単純には共通化しづらい。

**まだやっていないこと**

- 年次/半期で共通のEDINET doc mapを使う
- 共通のdownload/parse結果を使う
- GP/IBD/CFなどの補完結果を共通フォーマットにする

**次にやるなら**

まず「書類検索とpre_parseの共有」だけを切り出す。半期固有のH2計算は最後まで残してよい。

### 11. 個別分析キャッシュの粒度見直し

**問題**

`individual_analysis_{code}` は最終成果物を丸ごとキャッシュする。便利だが、XBRL抽出ロジック、WACCロジック、公開JSON整形を改善しても、キャッシュヒット時は古い分析結果が残りうる。

**まだやっていないこと**

- J-QUANTS raw
- EDINET doc map
- XBRL parse result
- 最終metrics

これらを別々にキャッシュする設計。

**次にやるなら**

先にキャッシュキーとバージョン設計を決める。いきなり分割するとキャッシュ互換性の影響が大きい。

### 12. 公開JSONスキーマの固定

**問題**

serializerで標準JSONは軽くなったが、「標準JSONに必ず出るキー」「欠損しうるキー」「デバッグ専用キー」の一覧はまだ契約として固定しきれていない。

**まだやっていないこと**

- 年次標準JSONのゴールデンテスト
- 半期標準JSONのゴールデンテスト
- `include_debug_fields=True` のゴールデンテスト
- 公開キー一覧のドキュメント化

**次にやるなら**

実データではなく小さなfixtureで、serializer単体テストを厚くする。

## 当面触らない

### 13. XBRLタグ候補の大規模整理

**理由**

企業別・会計基準別の知見が詰まっている。タグ候補をきれいに並べ替えるだけでも抽出精度に影響する可能性がある。

**触る条件**

実企業サンプルと会計基準別ゴールデンケースを先に用意する。

### 14. EDINET検索ウィンドウの短縮

**理由**

97日 + 127日フォールバックは遅く見えるが、提出遅延や半期/四半期差異を拾うための安全側の設計。速度だけで短縮すると取りこぼしが出る可能性がある。

**触る条件**

実データで検索日数とヒット率を測ってから判断する。

### 15. `CalculatedData` の公開キー削除

**理由**

MCP/CLI利用者への互換性影響が大きい。今回のように標準JSONからデバッグフィールドを落とす場合も、内部構造と明示デバッグ出力には残している。

**触る条件**

alias期間、移行ガイド、契約テストを用意する。

## 次のおすすめ順

1. serializer単体テストと公開JSON契約テストを追加する
2. EDINET検索キャッシュにTTLを入れる
3. XBRL抽出器戻り値を主要モジュールからTypedDict化する
4. 年次/半期でEDINET書類検索とpre_parse共有を切り出す
5. 個別分析キャッシュの粒度設計をする
