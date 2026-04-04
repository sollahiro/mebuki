# Mebuki — Claude Code ガイド

## 日付変換のコーディング規約

日付フォーマット変換（YYYYMMDD ↔ YYYY-MM-DD）には、必ず以下の正規関数を使用すること。
インラインでの文字列スライス変換や独自 `strptime` 呼び出しは禁止。

### 正規関数（`mebuki/utils/fiscal_year.py`）

```python
from mebuki.utils.fiscal_year import normalize_date_format, parse_date_string
```

| 関数 | 入力 | 出力 | 用途 |
|---|---|---|---|
| `normalize_date_format(date_str)` | YYYYMMDD / YYYY-MM-DD | `str \| None` | 文字列として YYYY-MM-DD が必要な場合 |
| `parse_date_string(date_str)` | YYYYMMDD / YYYY-MM-DD | `datetime \| None` | datetime オブジェクトとして扱いたい場合 |

### 年月抽出（`mebuki/utils/converters.py`）

```python
from mebuki.utils.converters import extract_year_month
```

| 関数 | 入力 | 出力 | 用途 |
|---|---|---|---|
| `extract_year_month(date_str)` | YYYYMMDD / YYYY-MM-DD | `(int, int) \| (None, None)` | 年・月を整数で取り出す場合 |

### 使用例

```python
# YYYYMMDD → YYYY-MM-DD（文字列変換）
normalize_date_format("20231231")   # => "2023-12-31"
normalize_date_format("2023-12-31") # => "2023-12-31"（冪等）
normalize_date_format(None)          # => None（安全）

# YYYYMMDD / YYYY-MM-DD → datetime
parse_date_string("20231231")        # => datetime(2023, 12, 31)
parse_date_string("2023-12-31")      # => datetime(2023, 12, 31)
parse_date_string(None)              # => None（安全）

# 年・月を整数で取り出す
extract_year_month("20231231")       # => (2023, 12)
extract_year_month("2023-12-31")     # => (2023, 12)
extract_year_month(None)             # => (None, None)（安全）
```

### やってはいけないパターン

```python
# ❌ インライン文字列スライス変換
f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}"

# ❌ 独自の dual-format strptime
if len(date_str) == 8:
    dt = datetime.strptime(date_str, "%Y%m%d")
elif len(date_str) == 10:
    dt = datetime.strptime(date_str, "%Y-%m-%d")

# ❌ マジックナンバー
if len(date_str) == 8:   # DATE_LEN_COMPACT を使うこと

# ✅ 正しい書き方
from mebuki.constants.formats import DATE_LEN_COMPACT
if len(date_str) == DATE_LEN_COMPACT:
    ...
```

### 日付長定数（`mebuki/constants/formats.py`）

```python
DATE_LEN_COMPACT    = 8   # YYYYMMDD 形式
DATE_LEN_HYPHENATED = 10  # YYYY-MM-DD 形式
```

---

## キャッシュバージョン管理

キャッシュには `_cache_version` フィールドを埋め込み、アプリバージョンの major.minor と照合することで、新機能追加時に古いキャッシュが返されるのを防ぐ。

### ルール

- キャッシュ保存時は必ず `_cache_version` を含めること
- キャッシュ読み込み時は `_cache_version` が現在の major.minor と一致する場合のみ使用する
- バージョン不一致のキャッシュはスキップし、再取得・上書きする（明示的な削除は不要）
- **新機能追加でキャッシュ構造が変わった場合は `pyproject.toml` の minor バージョンを上げること**

### 実装パターン（`mebuki/services/data_service.py`）

```python
from mebuki import __version__

_CACHE_VERSION = ".".join(__version__.split(".")[:2])  # 例: "2.3"

# 保存時
formatted = {
    "_cache_version": _CACHE_VERSION,
    ...
}

# 読み込み時
cached = self.cache_manager.get(key)
if cached and cached.get("_cache_version") == _CACHE_VERSION:
    return cached
# バージョン不一致 → フォールスルーして再取得・上書き
```

---

## アーキテクチャ依存ルール

- `services/` は `mebuki.app` をインポートしてはならない
- `infrastructure/` は `mebuki.app` および `mebuki.services` をインポートしてはならない

テストで自動検証: `tests/test_dependency_rules.py`
