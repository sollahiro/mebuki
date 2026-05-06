# BLUE TICKER — Agent ガイド

日本株の財務データCLIツール（Python / Poetry）。

## アーキテクチャ依存ルール

- `services/` は `mebuki.app` をインポートしてはならない
- `infrastructure/` は `mebuki.app` および `mebuki.services` をインポートしてはならない

テストで自動検証: `tests/test_dependency_rules.py`

## ルールファイル

以下のファイルをすべて読み、内容を遵守すること。

- `.agents/rules/generic/commit-conventions.md`
- `.agents/rules/project/date-conversion.md`
- `.agents/rules/project/versioning.md`
- `.agents/rules/project/mcp-cli-parity.md`
- `.agents/rules/project/error-handling.md`
- `.agents/rules/project/xbrl-analysis.md`
- `.agents/rules/project/dependencies.md`
- `.agents/rules/project/caching.md`
- `.agents/rules/project/constants.md`
- `.agents/rules/project/typing.md`
