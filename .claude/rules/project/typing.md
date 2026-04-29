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

`Any` を使う場合は、型が本当に不定である理由がある箇所のみ。辞書の値型が `str | float | None` のように絞れる場合は `Any` を使わない。

## `TypedDict` と `dataclass` の使い分け

| ケース | 使うもの |
|---|---|
| JSON / キャッシュ dict の構造を型付けしたい | `TypedDict` |
| ロジックを持つオブジェクト、または immutable な値 | `dataclass` |
| 一時的な戻り値で型が単純（2〜3フィールド） | `tuple[X, Y]` |
