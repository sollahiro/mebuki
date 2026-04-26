# キャッシュ設計規約

キャッシュの読み書きは `CacheManager`（`mebuki/utils/cache.py`）を使う。直接ファイルI/Oは行わない。

## バージョン埋め込み

キャッシュには必ず `_cache_version` フィールドを埋め込み、読み込み時に照合する。

```python
from mebuki import __version__

_CACHE_VERSION = ".".join(__version__.split(".")[:2])  # 例: "2.15"

# 保存
self.cache_manager.set(cache_key, {
    "_cache_version": _CACHE_VERSION,
    "data": ...,
})

# 読み込み
cached = self.cache_manager.get(cache_key)
if cached and cached.get("_cache_version") == _CACHE_VERSION:
    return cached["data"]
# バージョン不一致 → フォールスルーして再取得
```

バージョン管理の詳細は `versioning.md` を参照。

## キャッシュキーの命名規則

`{機能}_{識別子}_{パラメーター}` の形式で命名する。

```python
# ✅ 良い例
f"individual_analysis_{code}"
f"half_year_periods_{code}_{years}"
"earnings_calendar_store"

# ❌ 避ける（衝突リスク）
f"{code}"
"data"
```

## バージョン照合で一致したときの返し方

`_cache_version` フィールドは呼び出し元に露出させない。

```python
# ✅ _cache_version を除いて返す
return {k: v for k, v in cached.items() if k != "_cache_version"}

# ❌ そのまま返す（呼び出し元に _cache_version が漏れる）
return cached
```

## やってはいけないパターン

```python
# ❌ _cache_version なしで保存（古いキャッシュを検知できない）
self.cache_manager.set(key, {"data": ...})

# ❌ バージョン照合なしで読み込む
cached = self.cache_manager.get(key)
if cached:
    return cached
```
