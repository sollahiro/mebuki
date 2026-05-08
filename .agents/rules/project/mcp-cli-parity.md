# ローカルMCP廃止後のCLI公開面

CLI版のローカルMCPサーバーは廃止済み。`ticker mcp`、`blue_ticker/app/mcp_server.py`、ローカルMCP固有の契約テストは復活させない。

AIエージェントからのローカル操作は CLI + Skills で行う。将来 remote MCP を追加する場合も、ローカルCLIのサブコマンドとして stdio サーバーを再導入しない。

## 旧ローカルMCP削除対象

- `ticker mcp start`
- `ticker mcp install-*`
- `blue_ticker/app/mcp_server.py`
- `blue_ticker/app/cli/mcp.py`
- `tests/test_mcp_contract.py`

## CLIパラメーター追加時のデフォルト値ルール

新しいオプションパラメーターはオプトインにする。

- bool フラグ → `False`（例: `half`）
- 値パラメーター → `None`（例: `years`、サービス層でデフォルト処理）

ただし `use_cache` は既存挙動との互換性のため `True` のまま維持する（例外）。
