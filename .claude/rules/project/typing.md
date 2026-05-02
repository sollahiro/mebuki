# 型アノテーション規約

Python 3.11+ を前提とする。`from __future__ import annotations` は使わない。

## 組み込み型を使う（`typing` モジュールの上位互換を避ける）

```python
# ❌ 古い書き方（typing モジュールの大文字型）
from typing import Dict, List, Optional, Tuple, Union
def foo(items: List[str]) -> Optional[Dict[str, Any]]: ...

# ✅ 新しい書き方（組み込み型 + | 構文）
def foo(items: list[str]) -> dict[str, Any] | None: ...
```

| 古い書き方 | 新しい書き方 |
|---|---|
| `Optional[X]` | `X \| None` |
| `Dict[K, V]` | `dict[K, V]` |
| `List[X]` | `list[X]` |
| `Tuple[X, Y]` | `tuple[X, Y]` |
| `Union[X, Y]` | `X \| Y` |

## `typing` から残すもの・移すもの

```python
# ✅ typing から引き続きインポートする
from typing import Any          # 組み込みに同等物がない

# ✅ collections.abc へ移す（typing の同名型は非推奨エイリアス）
from collections.abc import Callable, Iterator, AsyncGenerator, Generator, Mapping, Sequence
```

| 古い書き方 | 新しい書き方 |
|---|---|
| `from typing import Callable` | `from collections.abc import Callable` |
| `from typing import Iterator` | `from collections.abc import Iterator` |
| `from typing import AsyncGenerator` | `from collections.abc import AsyncGenerator` |
| `from typing import Generator` | `from collections.abc import Generator` |
| `from typing import Mapping` | `from collections.abc import Mapping` |
| `from typing import Sequence` | `from collections.abc import Sequence` |

## インポート行の最終形

```python
# ✅ typing から残すのは Any のみ（不要なら typing 自体を消す）
from typing import Any
from collections.abc import Callable, Mapping, Sequence  # 使う場合のみ
```

## 戻り値型は必ず書く

```python
# ❌ 戻り値型なし
def validate(metrics):
    ...

# ✅
def validate(metrics: dict[str, Any]) -> tuple[bool, str | None]:
    ...
```

## `Any` の使用を最小限に

`Any` を使う場合は、型が本当に不定である理由がある箇所のみ。

### `Any` を使ってよい箇所

| 箇所 | 理由 |
|---|---|
| 外部 API レスポンス（J-QUANTS / EDINET）の `dict[str, Any]` | JSON の値型が実行時にしか判明しない |
| 任意型を受け入れる検証関数の引数（`is_nan`, `is_valid_value`） | `float`, `str`, `None` など全型を動的に処理する |
| MCP プロトコルの `arguments: dict[str, Any]` | プロトコル仕様で型が規定されていない |

### `Any` を使ってはいけない箇所（具体例）

```python
# ❌ 値が float | None に絞れるのに Any
def calculate_wacc(...) -> dict[str, Any]: ...

# ✅
def calculate_wacc(...) -> dict[str, float | None]: ...

# ❌ XBRL パース結果の値が float に絞れるのに Any
def collect_numeric_elements(...) -> dict[str, Any]: ...

# ✅
def collect_numeric_elements(...) -> dict[str, dict[str, float]]: ...

# ❌ 変換関数の引数が str | float | int | None に絞れるのに Any
def to_float(value: Any) -> float | None: ...

# ✅
def to_float(value: str | float | int | None) -> float | None: ...

# ❌ 戻り値が dict | list のどちらかに決まるのに Any
async def get_financial_data(...) -> Any: ...

# ✅
async def get_financial_data(...) -> dict[str, Any] | list[dict[str, Any]]: ...
```

### 定数ファイルの構造化 dict には TypedDict を使う

```python
# ❌ constants/xbrl.py で Any を使う
COMPONENT_DEFINITIONS: list[dict[str, Any]] = [...]

# ✅ 内部用 TypedDict を同ファイルに定義する
class _ComponentDef(TypedDict):
    label: str
    tags: list[str]

COMPONENT_DEFINITIONS: list[_ComponentDef] = [...]
```

オプションフィールドがある場合は `NotRequired` を使う（`total=False` は全フィールドをオプションにするため不適切）。

```python
from typing import NotRequired, TypedDict

class _AggregateIFRSDef(TypedDict):
    tag: str
    covers: list[str]
    label: NotRequired[str]  # 一部のエントリにしか存在しないフィールド
```

## `TypedDict` と `dataclass` の使い分け

| ケース | 使うもの |
|---|---|
| JSON / キャッシュ dict の構造を型付けしたい | `TypedDict` |
| レイヤー間で受け渡す複雑なドメイン辞書を型付けしたい | `TypedDict` |
| ロジックを持つオブジェクト、または immutable な値 | `dataclass` |
| 一時的な戻り値で型が単純（2〜3フィールド） | `tuple[X, Y]` |

## `TypedDict` の置き場所

複数モジュールが共有するドメイン TypedDict は **`mebuki/utils/`** に独立ファイルとして置く。

```
mebuki/utils/metrics_types.py  # 財務指標系（YearEntry, CalculatedData 等）
```

- `analysis/` と `services/` の両方からインポート可能（循環なし）
- 単一モジュール内でしか使わない TypedDict はそのファイル内に定義してよい
- `constants/` ファイル内の構造化定数を型付けする TypedDict も同ファイル内に定義してよい（`_` プレフィックスで内部用と明示）

## 段階的に組み立てる辞書には `total=False`

`_apply_*` 関数のように後からフィールドを追加する辞書は `total=False` を使う。
静的解析でキーの存在が保証できないためで、意図的な選択。

```python
# ✅ 段階的に拡充される辞書
class CalculatedData(TypedDict, total=False):
    Sales: float | None
    GrossProfit: float | None   # _apply_gross_profit で追加
    WACC: float | None          # _apply_wacc で追加

# ✅ 常に全フィールドが揃う辞書
class YearEntry(TypedDict):     # total=True（デフォルト）
    fy_end: str | None
    RawData: RawData
    CalculatedData: CalculatedData
```

### `total=False` の TypedDict は `.get()` で読む

`total=False` や `NotRequired` のキーは、静的解析上「存在しない可能性がある」。
値が `None` でよい計算では `dict["key"]` ではなく `.get("key")` を使う。

```python
# ❌ RawData は total=False なのでキー欠落の可能性がある
cfo_m = to_millions(raw_values["CFO"])

# ✅ 欠落時は None として扱う
cfo_m = to_millions(raw_values.get("CFO"))
```

## `None` を含む値は演算・比較の前に絞る

`float | None` や `int | None` は、演算子の直前で対象の変数自体を `is not None` で絞る。
入力値を絞っていても、変換関数の戻り値までは型チェッカーが追跡できない場合がある。

```python
cfo_m = to_millions(raw_values.get("CFO"))
cfi_m = to_millions(raw_values.get("CFI"))

# ❌ cfo_m / cfi_m は float | None
cfc = cfo_m + cfi_m

# ✅ 演算する変数を直接ガードする
cfc = (cfo_m + cfi_m) if cfo_m is not None and cfi_m is not None else None
```

日付変換も同様に、`extract_year_month()` の戻り値は `int | None` として扱う。

```python
year, month = extract_year_month(fy_end)
if year is not None and month is not None and year == today.year and month > today.month:
    ...
```

## 可変コレクションを読取専用で受ける場合は `Sequence`

`list` は不変（invariant）なので、`list[YearEntry]` は `list[dict[str, Any]]` に渡せない。
関数が要素の読み取りだけを行うなら、引数は `Sequence[T]` にする。

```python
from collections.abc import Sequence

# ❌ 読み取りだけなのに list 型を広く受けようとしている
def summarize(years: list[dict[str, Any]]) -> None: ...

# ✅ 呼び出し側の list[YearEntry] をそのまま受けられる
def summarize(years: Sequence[YearEntry]) -> None: ...
```

辞書も読み取り専用なら `dict[str, Any]` ではなく `Mapping[str, Any]` を使う。
これにより `TypedDict` を通常の辞書として読める。

```python
from collections.abc import Mapping

# ❌ TypedDict を渡しにくい
def validate(metrics: dict[str, Any]) -> bool: ...

# ✅ MetricsResult などの TypedDict を受けられる
def validate(metrics: Mapping[str, Any]) -> bool: ...
```

## 戻り値 TypedDict は変数注釈で推論を助ける

段階的に組み立てる戻り値や、後からキーを追加する辞書は、変数定義時に TypedDict 型を付ける。
注釈がないと `dict[str, Unknown]` や広すぎる union に推論されることがある。

```python
# ❌ 戻り値型 MetricsResult へ割り当てられないことがある
metrics = {
    "code": latest.get("Code"),
    "analysis_years": len(years_data),
}

# ✅
metrics: MetricsResult = {
    "code": latest.get("Code"),
    "analysis_years": len(years_data),
}
```

一時的に `None` から始める複数値は、返却前に `tuple[...] | None` としてまとめて絞る。

```python
found: tuple[str, str] | None = None
...
if found is None:
    return None
label, method = found  # ここでは str
```

戻り値は実際の構造に合わせる。`list[StockSearchResult]` のような TypedDict リストを返す関数は、
`list[dict[str, Any]]` に広げず、その TypedDict を戻り値型にする。

```python
# ❌ list は invariant なので list[StockSearchResult] を返せない
def search_companies(query: str) -> list[dict[str, Any]]: ...

# ✅
def search_companies(query: str) -> list[StockSearchResult]: ...
```

## コールバックは宣言どおりの型を返す

`Callable[[dict], bool]` と宣言したコールバックは必ず `bool` を返す。
`dict.get()` の戻り値は `Any | None` になりやすいので、`bool(...)` で明示する。

```python
# ❌ Unknown | None
ExtractorSpec("nr", "NR", extract_net_revenue, result_check=lambda r: r.get("found"))

# ✅ bool
ExtractorSpec("nr", "NR", extract_net_revenue, result_check=lambda r: bool(r.get("found")))
```

## `asyncio.gather(return_exceptions=True)` は `BaseException` を扱う

`return_exceptions=True` の結果には `BaseException` が混ざる。
`Exception` ではなく `BaseException` で絞り、成功側の型だけを後続処理へ渡す。

```python
results = await asyncio.gather(*tasks, return_exceptions=True)
for result in results:
    if isinstance(result, BaseException):
        continue
    # ここでは成功結果
```

最後に保持した例外を `raise` する場合は、`None` ガードを必ず入れる。

```python
last_exception: BaseException | None = None
...
if last_exception is not None:
    raise last_exception
raise aiohttp.ClientError("retry limit exceeded")
```

## Optional な共有クライアントはローカル変数へ束縛する

`self.edinet_client` のような `T | None` の属性は、ネスト関数や await をまたぐと型が絞られない。
ガード後にローカル変数へ束縛して使う。

```python
if not self.edinet_client or not self.edinet_client.api_key:
    return {}
client = self.edinet_client

async def worker(doc: dict[str, Any]) -> None:
    await client.download_document(doc["docID"], 1)
```

APIキー更新メソッドは設定値由来の `None` を受けるため、引数を `str | None` にする。

```python
def update_api_key(self, api_key: str | None) -> None:
    self.api_key = api_key.strip() if api_key else ""
```

## TypedDict に未定義キーを足さない

`GrossProfitResult` などの厳密な TypedDict に `docID` のような未定義キーを直接追加しない。
追加フィールドを返したい場合は通常の `dict` にコピーしてから追加するか、TypedDict 定義にキーを追加する。

```python
# ❌ GrossProfitResult に docID はない
gp = extract_gross_profit(...)
gp["docID"] = doc_id

# ✅ 返却用の通常 dict にする
gp_result = dict(extract_gross_profit(...))
gp_result["docID"] = doc_id
```

## 外部ライブラリの属性値は型を絞ってから変換する

BeautifulSoup の `Tag.get()` は型定義上 `str` 以外（list / None など）も返し得る。
`int(tag.get("colspan", 1))` のように直接変換せず、helper で `isinstance` による型絞りを行う。

```python
# ❌ Tag.get() の戻り値を int() に直接渡す
span = int(cell.get("colspan", 1))

# ✅ mebuki.analysis.xbrl_utils の helper を使う
span = parse_html_int_attribute(cell, "colspan")
```
