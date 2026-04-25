# MCP ツールと CLI の対応原則

`mebuki/app/mcp_server.py` の MCP ツール群は、CLI（`mebuki analyze` 等）の機能・パラメーターに揃えること。

- CLI で廃止した機能・オプションは MCP からも削除する
- CLI で追加した機能は MCP にも追加する
- CLI に存在しない MCP 専用機能は原則として追加しない

## ツール対応表

| MCP ツール | CLI コマンド |
|---|---|
| `find_japan_stock_code` | `mebuki search` |
| `get_japan_stock_financial_data` | `mebuki analyze` |
| `search_japan_stock_filings` | `mebuki filings` |
| `extract_japan_stock_filing_content` | `mebuki filing` |
| `get_japan_stock_watchlist` | `mebuki watch list` |
| `manage_japan_stock_watchlist` | `mebuki watch add/remove` |
| `get_japan_stock_portfolio` | `mebuki portfolio list` |
| `manage_japan_stock_portfolio` | `mebuki portfolio add/sell/remove` |
| `search_japan_stocks_by_sector` | `mebuki sector [業種名]` |

## パラメーター追加時のデフォルト値ルール

新しいオプションパラメーターはオプトインにする。

- bool フラグ → `False`（例: `half`）
- 値パラメーター → `None`（例: `years`、サービス層でデフォルト処理）

ただし `use_cache` は既存挙動との互換性のため `True` のまま維持する（例外）。

## `get_japan_stock_financial_data` のパラメーター対応

| MCP パラメーター | CLI オプション | 備考 |
|---|---|---|
| `years` | `--years N` | デフォルト 5（`half=true` 時は 3） |
| `half: true` | `--half` | H1/H2 半期推移 |
| `scope: "raw"` | `--scope raw` | 生データ取得時のみ指定 |
