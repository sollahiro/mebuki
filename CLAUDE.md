# Mebuki — Claude Code ガイド

日本株の財務データCLIツール（Python / Poetry）。

## アーキテクチャ依存ルール

- `services/` は `mebuki.app` をインポートしてはならない
- `infrastructure/` は `mebuki.app` および `mebuki.services` をインポートしてはならない

テストで自動検証: `tests/test_dependency_rules.py`

@.claude/rules/generic/commit-conventions.md
@.claude/rules/project/date-conversion.md
@.claude/rules/project/versioning.md
@.claude/rules/project/mcp-cli-parity.md
@.claude/rules/project/error-handling.md
@.claude/rules/project/xbrl-analysis.md
@.claude/rules/project/dependencies.md
@.claude/rules/project/caching.md
@.claude/rules/project/constants.md
@.claude/rules/project/typing.md
