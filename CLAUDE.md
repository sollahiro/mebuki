# BLUE TICKER — Claude Code ガイド

日本株の財務データCLIツール（Python / Poetry）。

## アーキテクチャ依存ルール

- `services/` は `blue_ticker.app` をインポートしてはならない
- `infrastructure/` は `blue_ticker.app` および `blue_ticker.services` をインポートしてはならない

テストで自動検証: `tests/test_dependency_rules.py`

@.agents/rules/generic/commit-conventions.md
@.agents/rules/project/date-conversion.md
@.agents/rules/project/versioning.md
@.agents/rules/project/mcp-cli-parity.md
@.agents/rules/project/error-handling.md
@.agents/rules/project/xbrl-analysis.md
@.agents/rules/project/dependencies.md
@.agents/rules/project/caching.md
@.agents/rules/project/constants.md
@.agents/rules/project/typing.md
