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

## バージョン管理

### 番号の付け方

| 変更内容 | 上げる桁 | 理由 |
|---|---|---|
| 新機能追加・キャッシュ構造の変化 | **minor** | キャッシュの自動無効化が必要なため |
| バグ修正・依存ライブラリの変更 | **patch** | キャッシュ構造に影響しないため |

### リリース手順

1. `mebuki/__init__.py` と `pyproject.toml` の両方を更新する
2. `poetry lock` を実行してコミットに含める
3. **既存タグの付け直しは禁止**。必ず新しいバージョンに上げて新タグを切ること
   - タグを付け直すと GitHub が tarball を再生成して SHA256 が変わり、Homebrew formula との checksum 不一致が発生する

### キャッシュバージョンの埋め込み（`mebuki/services/data_service.py`）

キャッシュには `_cache_version` フィールドを埋め込み、major.minor と照合することで古いキャッシュの混入を防ぐ。

```python
from mebuki import __version__

_CACHE_VERSION = ".".join(__version__.split(".")[:2])  # 例: "2.4"

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

## MCP ツールと CLI の対応原則

`mebuki/app/mcp_server.py` の MCP ツール群は、CLI（`mebuki analyze` 等）の機能・パラメーターに揃えること。

- CLI で廃止した機能・オプションは MCP からも削除する
- CLI で追加した機能は MCP にも追加する
- CLI に存在しない MCP 専用機能は原則として追加しない

### 現在の対応表

| MCP ツール | CLI コマンド |
|---|---|
| `find_japan_stock_code` | `mebuki search` |
| `get_japan_stock_financial_data` | `mebuki analyze` |
| `search_japan_stock_filings` | `mebuki filings` |
| `extract_japan_stock_filing_content` | `mebuki filing` |
| `get_japan_stock_watchlist` | `mebuki watch list` |
| `manage_japan_stock_watchlist` | `mebuki watch add/remove` |
| `get_japan_stock_portfolio` | `mebuki portfolio list` |
| `manage_japan_stock_portfolio` | `mebuki portfolio add/sell/remove` |

### `get_japan_stock_financial_data` のパラメーター対応

| MCP パラメーター | CLI オプション | 備考 |
|---|---|---|
| `years` | `--years N` | デフォルト 5（`half=true` 時は 3） |
| `half: true` | `--half` | H1/H2 半期推移 |
| `scope: "raw"` | `--scope raw` | 生データ取得時のみ指定 |

---

## アーキテクチャ依存ルール

- `services/` は `mebuki.app` をインポートしてはならない
- `infrastructure/` は `mebuki.app` および `mebuki.services` をインポートしてはならない

テストで自動検証: `tests/test_dependency_rules.py`
