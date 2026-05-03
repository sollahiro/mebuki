# Mebuki — Claude Code ガイド

日本株の財務データCLIツール（Python / Poetry）。

## アーキテクチャ依存ルール

- `services/` は `mebuki.app` をインポートしてはならない
- `infrastructure/` は `mebuki.app` および `mebuki.services` をインポートしてはならない

テストで自動検証: `tests/test_dependency_rules.py`

## Claude × Codex 開発フロー

実装作業は Claude（計画・レビュー担当）と Codex（実装担当）の役割分担で進める。

```
Claude: 計画立案
    ↓
Codex: 計画レビュー（実装せず、疑問・懸念・代替案を出す）
    ↓
Claude: フィードバックを検討・計画修正 or 承認
    ↓
Codex: 実装（承認後）
    ↓
Claude: レビュー・再指示（問題があれば）
    ↓
Codex: 反論または再実装
    ↓
Claude: 再レビュー（必要に応じて繰り返す）
```

### Codex への指示原則

- **計画フェーズと実装フェーズを分ける。** 最初のメッセージでは「実装前に疑問・懸念・代替案があれば出してください。問題なければその旨だけ返してください。実装はまだしないでください。」と明示する。承認後に `mcp__codex__codex-reply` で「では実装してください」と続ける
- Codex は Claude の判断を鵜呑みにしない。指示に疑問・矛盾・より良いアプローチがあれば実装前に提案してよい
- Claude は Codex の実装結果を必ずファイルを直接読んで検証する（報告だけを信用しない）
- MCP ツール `mcp__codex__codex`（新規セッション）/ `mcp__codex__codex-reply`（継続）で指示を送る

### レビュー後の報告

Claude はレビュー完了後、必ず以下のいずれかを明示する。

- **追加指示なし**: 問題なし・差し戻し不要と判断した場合
- **差し戻し**: 問題点と差し戻し理由を添えて Codex に再指示した場合

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
