# プロジェクト構造と責務

このドキュメントは、`mebuki` の現行アーキテクチャを説明します。

## 現行構造

```
mebuki/
├── mebuki/
│   ├── app/               # エントリポイント層 (CLI/MCP)
│   │   ├── cli.py
│   │   └── mcp_server.py
│   ├── services/          # ユースケース層 (分析/検索/集約)
│   ├── infrastructure/    # 設定・外部APIアダプタ補助
│   ├── api/               # 外部APIクライアント (J-QUANTS/EDINET)
│   ├── analysis/          # 財務計算・XBRL解析
│   ├── constants/
│   └── utils/
└── assets/                # 銘柄マスタ等
```

## 依存方向

- `mebuki.app` -> `mebuki.services`
- `mebuki.services` -> `mebuki.analysis | mebuki.api | mebuki.infrastructure | mebuki.utils`
- `mebuki.infrastructure` は `app/services` を参照しない

## 互換性ポリシー

- CLI (`mebuki` コマンド) と MCP ツール名/入出力は維持
- 新規実装は `mebuki.*` 配下のみ追加する

## 主要フロー

1. CLI/MCP (`mebuki.app.*`) が要求を受け取る
2. `mebuki.services.data_service` が分析・検索の公開APIとして処理を統合
3. `mebuki.api` / `mebuki.analysis` / `mebuki.infrastructure` を利用して結果を返却
