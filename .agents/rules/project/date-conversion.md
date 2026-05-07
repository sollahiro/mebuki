# 日付変換のコーディング規約

日付フォーマット変換（YYYYMMDD ↔ YYYY-MM-DD）には、必ず以下の正規関数を使用すること。
インラインでの文字列スライス変換や独自 `strptime` 呼び出しは禁止。

## 正規関数

```python
from blue_ticker.utils.fiscal_year import normalize_date_format, parse_date_string
from blue_ticker.utils.converters import extract_year_month
```

| 関数 | 入力 | 出力 | 用途 |
|---|---|---|---|
| `normalize_date_format(date_str)` | YYYYMMDD / YYYY-MM-DD | `str \| None` | 文字列として YYYY-MM-DD が必要な場合 |
| `parse_date_string(date_str)` | YYYYMMDD / YYYY-MM-DD | `datetime \| None` | datetime オブジェクトとして扱いたい場合 |
| `extract_year_month(date_str)` | YYYYMMDD / YYYY-MM-DD | `(int, int) \| (None, None)` | 年・月を整数で取り出す場合 |

## 使用例

```python
normalize_date_format("20231231")   # => "2023-12-31"
normalize_date_format("2023-12-31") # => "2023-12-31"（冪等）
normalize_date_format(None)         # => None（安全）

parse_date_string("20231231")       # => datetime(2023, 12, 31)
parse_date_string(None)             # => None（安全）

extract_year_month("20231231")      # => (2023, 12)
extract_year_month(None)            # => (None, None)（安全）
```

## やってはいけないパターン

```python
# ❌ インライン文字列スライス変換
f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}"

# ❌ 独自の dual-format strptime
if len(date_str) == 8:
    dt = datetime.strptime(date_str, "%Y%m%d")

# ❌ マジックナンバー
if len(date_str) == 8:  # DATE_LEN_COMPACT を使うこと

# ✅ 正しい書き方
from blue_ticker.constants.formats import DATE_LEN_COMPACT
if len(date_str) == DATE_LEN_COMPACT:
    ...
```

## 日付長定数（`blue_ticker/constants/formats.py`）

```python
DATE_LEN_COMPACT    = 8   # YYYYMMDD 形式
DATE_LEN_HYPHENATED = 10  # YYYY-MM-DD 形式
```
