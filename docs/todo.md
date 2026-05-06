# コードベース構成メモ

バージョン: v26.5.0
評価日: 2026-05-06

## 採点サマリー

| 次元 | スコア | メモ |
|---|---|---|
| 保守性 | A- | レイヤー境界と依存規則テストが効いている |
| パフォーマンス | A- | EDINET書類検索、XBRL展開、parse結果のキャッシュが揃っている |
| テスト | A- | XBRL、サービス、CLI/MCP契約、キャッシュ境界のテストが厚い |
| 型安全性 | A- | 主要metricsとXBRL抽出結果はTypedDict化済み。pyrightをCIで実行 |
| CLI/MCP パリティ | A | 主要機能はCLI/MCPで対応済み。削除系はCLI限定 |
| DRY | A- | 年次抽出器レジストリ、XBRL共通parse、年次/半期の書類検索共有が効いている |
| 総合 | A- | 次の伸びしろは実企業回帰テスト |

## 現状の強み

- 依存方向が明確。`app -> services -> api/analysis/infrastructure/utils` を基本とし、`tests/test_dependency_rules.py` で逆流を検出する。
- EDINET関連の責務が分かれている。通信は `api/edinet_client.py`、ファイルキャッシュは `api/edinet_cache_store.py`、書類選定と抽出 orchestration は `services/edinet_fetcher.py` が担当する。
- EDINETキャッシュは日別検索TTL、年次インデックスバージョン、XBRL展開ディレクトリの2GB上限とmtime LRU削除を持つ。
- `cache status` でEDINET年次インデックス、XBRL展開、分析結果キャッシュの状態を確認できる。
- EDINET-onlyスモークテストは、実企業の有報検索キャッシュとXBRL展開キャッシュから実行できる。
- XBRL parse結果とEDINET書類リストは `CacheManager` 経由で独立キャッシュされ、最終分析キャッシュ更新時の再取得・再parseを抑えられる。
- 標準JSONとデバッグフィールドの境界は `utils/output_serializer.py` に集約され、公開キー集合は `tests/test_output_serializer.py` で固定している。
- XBRL抽出器の戻り値は `utils/xbrl_result_types.py` に集約され、pyrightをCIで実行している。

## 注意して見る場所

| ファイル | 行数 | 見るポイント |
|---|---:|---|
| `services/edinet_fetcher.py` | 974 | 書類検索、download/parse、抽出器呼び出しが集まる中核。新しい共通化はここを大きくしすぎないよう注意 |
| `analysis/xbrl_parser.py` | 517 | 有報本文抽出の基盤。HTML/XBRL揺れに対する回帰テストを優先 |
| `services/analyzer.py` | 507 | metrics適用とWACC統合。新指標追加時は `_METRIC_APPLIERS` と型定義を揃える |
| `analysis/gross_profit.py` | 468 | 会計基準・タグ候補・US-GAAP HTML補完が絡む。タグ整理は実企業テスト後に行う |
| `app/mcp_server.py` | 380 | CLI/MCPパリティを崩しやすい。CLI側オプション追加時はMCP契約も確認 |
| `app/cli/analyze.py` | 376 | 表示・JSON出力・EDINET書類コマンドの入口。serializer経由を維持する |
| `api/edinet_client.py` | 382 | API retry、日次検索、XBRL取得。ファイル管理を増やす場合は `EdinetCacheStore` に寄せる |
| `utils/financial_data.py` | 356 | 年次/半期の基礎データ構築。日付変換と単位境界に注意 |

## テスト状況

| 領域 | 主なテスト | 状況 |
|---|---|---|
| XBRL抽出 | `test_xbrl_*.py` | 会計基準・タグ・HTML補完の単体テストが厚い |
| EDINET境界 | `test_edinet_client.py`, `test_edinet_cache_store.py`, `test_edinet_fetcher_boundary.py`, `test_edinet_discovery.py` | 通信境界、キャッシュ、書類発見を分けて検証 |
| サービス層 | `test_data_service.py`, `test_analyzer_async.py`, `test_analyzer_apply_functions.py` | キャッシュヒット、非同期経路、metrics適用を検証 |
| CLI/MCP | `test_cli_contract.py`, `test_cli_integration.py`, `test_mcp_contract.py` | 主要コマンド、JSON出力、MCPツール契約を検証 |
| 出力契約 | `test_output_serializer.py` | 公開JSONキーとデバッグフィールド除外を固定 |
| アーキテクチャ | `test_dependency_rules.py` | services/infrastructureの禁止依存を検証 |

## 優先改善候補

1. 実企業サンプルの回帰テストを増やす

   J-GAAP、IFRS、US-GAAPの代表銘柄で、年次・半期・公開JSONの形を固定する。XBRLタグ候補の大規模整理は、この土台を作ってから触る。

2. `CalculatedData` の公開キー削除やrenameは慎重に進める

   MCP/CLI利用者への互換性影響が大きい。alias期間、利用者向けの変更案内、契約テストを用意してから判断する。
