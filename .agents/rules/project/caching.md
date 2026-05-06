# キャッシュ設計規約

mebuki 生成キャッシュの読み書きは `CacheManager`（`mebuki/utils/cache.py`）を使う。直接ファイルI/Oは行わない。

EDINET API 由来キャッシュ（日別書類一覧、年次書類インデックス、XBRL 展開ディレクトリ）は `EdinetCacheStore`（`mebuki/api/edinet_cache_store.py`）を使う。

## 責務別ディレクトリ

キャッシュは取得物と生成物で分ける。

```text
analysis_cache/
  external/
    edinet/
      documents_by_date/
      document_indexes/
      xbrl/
  derived/
    document_discovery/
    xbrl_numeric_index/
    analysis/
    half_year/
    mof/
```

- `external/`: 外部API・外部資料から取得した生データまたは取得物
- `derived/`: mebuki が探索・パース・計算して作った中間結果または分析結果

## バージョン埋め込み

derived キャッシュには必ず `_cache_version` フィールドを埋め込み、読み込み時に `__version__` 全体と照合する。

external キャッシュは原則としてグローバルバージョンに連動させない。TTL、取得日、または外部API用の個別バージョンで管理する。

```python
from mebuki import __version__

_CACHE_VERSION = __version__  # 例: "26.5.0"

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
f"edinet_docs_{code}_{years}"
f"xbrl_parsed_{doc_id}"
"mof_rf_rates"

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
