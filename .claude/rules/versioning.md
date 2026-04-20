# バージョン管理

## 番号の付け方

| 変更内容 | 上げる桁 | 理由 |
|---|---|---|
| 新機能追加・キャッシュ構造の変化 | **minor** | キャッシュの自動無効化が必要なため |
| バグ修正・依存ライブラリの変更 | **patch** | キャッシュ構造に影響しないため |

「キャッシュ構造の変化」とは、キャッシュ dict のフィールド追加・削除・リネーム、型変更、ネスト構造変更を指す。既存フィールドの計算バグ修正（同じキー名・同じ型）はキャッシュ構造変化に該当しない。

## リリース手順

0. **バンプは機能コミットとは分離し、後続の独立コミットとして行う**
1. `mebuki/__init__.py` と `pyproject.toml` の両方を更新する
2. `poetry lock` を実行してコミットに含める
3. **既存タグの付け直しは禁止**。必ず新しいバージョンに上げて新タグを切ること
   - タグを付け直すと GitHub が tarball を再生成して SHA256 が変わり、Homebrew formula との checksum 不一致が発生する

## キャッシュバージョンの埋め込み（`mebuki/services/data_service.py`）

キャッシュには `_cache_version` フィールドを埋め込み、major.minor と照合することで古いキャッシュの混入を防ぐ。

```python
from mebuki import __version__

_CACHE_VERSION = ".".join(__version__.split(".")[:2])  # 例: "2.4"

# 保存時
formatted = {"_cache_version": _CACHE_VERSION, ...}

# 読み込み時
cached = self.cache_manager.get(key)
if cached and cached.get("_cache_version") == _CACHE_VERSION:
    return cached
# バージョン不一致 → フォールスルーして再取得・上書き
```
