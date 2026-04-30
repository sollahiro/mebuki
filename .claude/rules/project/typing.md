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
from collections.abc import Callable, Iterator, AsyncGenerator, Generator
```

| 古い書き方 | 新しい書き方 |
|---|---|
| `from typing import Callable` | `from collections.abc import Callable` |
| `from typing import Iterator` | `from collections.abc import Iterator` |
| `from typing import AsyncGenerator` | `from collections.abc import AsyncGenerator` |
| `from typing import Generator` | `from collections.abc import Generator` |

## インポート行の最終形

```python
# ✅ typing から残すのは Any のみ（不要なら typing 自体を消す）
from typing import Any
from collections.abc import Callable  # Callable を使う場合のみ
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
