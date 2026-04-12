# プロジェクト構造と責務

このドキュメントは、`mebuki` の現行アーキテクチャを説明します。

## 現行構造

```
mebuki/
├── mebuki/
│   ├── __main__.py        # python -m mebuki エントリポイント
│   ├── app/               # エントリポイント層 (CLI/MCP)
│   │   ├── cli/           # CLI サブパッケージ
│   │   │   ├── main.py        # エントリポイント・ディスパッチャ
│   │   │   ├── parser.py      # argparse パーサー定義
│   │   │   ├── analyze.py     # search/analyze/price/filings/filing コマンド
│   │   │   ├── config.py      # config コマンド
│   │   │   ├── mcp.py         # mcp コマンド
│   │   │   ├── portfolio.py   # watch/portfolio コマンド
│   │   │   └── ui.py          # バナー・UI補助
│   │   └── mcp_server.py  # MCP サーバー (全9ツール)
│   ├── services/          # ユースケース層 (分析/検索/集約)
│   │   ├── data_service.py
│   │   ├── analyzer.py
│   │   ├── master_data.py
│   │   └── portfolio_service.py  # ウォッチリスト・保有銘柄管理
│   ├── infrastructure/    # 設定・外部APIアダプタ補助・永続化
│   │   ├── settings.py
│   │   ├── helpers.py
│   │   └── portfolio_store.py   # ポートフォリオ永続化 (portfolio.json)
│   ├── api/               # 外部APIクライアント (J-QUANTS/EDINET)
│   │   ├── jquants_client.py
│   │   └── edinet_client.py
│   ├── analysis/          # 財務計算・XBRL解析
│   │   ├── calculator.py
│   │   ├── xbrl_parser.py
│   │   └── interest_bearing_debt.py  # 有利子負債抽出ロジック
│   ├── llm/               # LLMプロバイダ連携
│   │   └── providers.py
│   ├── constants/
│   │   ├── api.py
│   │   ├── xbrl.py
│   │   ├── formats.py     # 出力フォーマット定数
│   │   └── financial.py   # 財務定数
│   ├── utils/
│   │   ├── cache.py
│   │   ├── converters.py
│   │   ├── errors.py
│   │   ├── financial_data.py
│   │   ├── fiscal_year.py
│   │   ├── formatters.py
│   │   ├── jquants_utils.py
│   │   ├── sectors.py
│   │   └── xbrl_compressor.py
└── assets/                # 銘柄マスタ等
```

## 依存方向

- `mebuki.app` -> `mebuki.services`
- `mebuki.services` -> `mebuki.analysis | mebuki.api | mebuki.infrastructure | mebuki.utils`
- `mebuki.infrastructure` は `app/services` を参照しない（`portfolio_service` は `data_service` を遅延インポート）
- `mebuki.llm` は `mebuki.services` / `mebuki.app` から参照

## 互換性ポリシー

- CLI (`mebuki` コマンド) と MCP ツール名/入出力は維持
- 新規実装は `mebuki.*` 配下のみ追加する

## 2Q（中間期）データの取り扱い

`extract_annual_data()` はデフォルト（`include_2q=False`）でFYのみを返す。`include_2q=True` を指定するとFYと2Qの両方を返す。

**フラグ伝達経路:**

```
CLI --include-2q
    → cmd_analyze(args.include_2q)
        → data_service.get_raw_analysis_data(include_2q)
            → analyzer.fetch_analysis_data(include_2q)
                → _fetch_financial_data(include_2q)
                    → extract_annual_data(financial_data, include_2q=include_2q)

MCP include_2q パラメータ
    → data_service.get_financial_data(include_2q)
        → analyzer.analyze_stock(include_2q) / get_metrics(include_2q)
            → _fetch_financial_data(include_2q)
```

**設計上の制約:**

- 2QのEPS/BPSは6ヶ月分のため、**PER/PBR/ROE/ROICは`None`**（誤値防止）
- `analysis_years` はFY件数でカウントする（2Qはカウント外）
- `extract_annual_data` の重複除去キーは `(CurFYEn, CurPerType)` ペアを使用（同一FY末日のFYと2Qを別エントリとして保持）
- `calculate_metrics_flexible` の重複除去も同様に `(fy_end, per_type)` ペアを使用

## 主要フロー

1. CLI/MCP (`mebuki.app.*`) が要求を受け取る
2. `mebuki.services.data_service` が財務・検索の公開APIとして処理を統合
3. `mebuki.services.portfolio_service` がウォッチリスト・ポートフォリオ操作を担当
4. `mebuki.api` / `mebuki.analysis` / `mebuki.infrastructure` を利用して結果を返却

## ポートフォリオデータモデル

永続化ファイル: `~/.config/mebuki/portfolio.json`（`settings_store.user_data_path` 配下）

一意キー: `(ticker_code, broker, account_type)`

| フィールド | 型 | 説明 |
| :--- | :--- | :--- |
| `ticker_code` | str | 証券コード |
| `status` | `"watch"` \| `"holding"` | ウォッチ or 保有 |
| `broker` | str | 証券会社名 |
| `account_type` | `"特定"` \| `"一般"` \| `"NISA"` | 口座種別 |
| `lots` | list | 購入ロット一覧 `[{quantity, cost_price, bought_at}]` |

売却処理は総平均法で計算。全ロット売却時は自動でウォッチに降格。
