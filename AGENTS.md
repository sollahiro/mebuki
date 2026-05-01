# Mebuki — Codex ガイド

日本株の財務データCLIツール（Python / Poetry）。

## アーキテクチャ依存ルール

- `services/` は `mebuki.app` をインポートしてはならない
- `infrastructure/` は `mebuki.app` および `mebuki.services` をインポートしてはならない

テストで自動検証: `tests/test_dependency_rules.py`

@.Codex/rules/generic/commit-conventions.md
@.Codex/rules/project/date-conversion.md
@.Codex/rules/project/versioning.md
@.Codex/rules/project/mcp-cli-parity.md
@.Codex/rules/project/error-handling.md
@.Codex/rules/project/xbrl-analysis.md
@.Codex/rules/project/dependencies.md
@.Codex/rules/project/caching.md
@.Codex/rules/project/constants.md
@.Codex/rules/project/typing.md
