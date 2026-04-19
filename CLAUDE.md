# Mebuki — Claude Code ガイド

日本株の財務データCLIツール（Python / Poetry）。

## アーキテクチャ依存ルール

- `services/` は `mebuki.app` をインポートしてはならない
- `infrastructure/` は `mebuki.app` および `mebuki.services` をインポートしてはならない

テストで自動検証: `tests/test_dependency_rules.py`

@.claude/rules/date-conversion.md
@.claude/rules/versioning.md
@.claude/rules/mcp-cli-parity.md
