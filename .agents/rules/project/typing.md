# 型アノテーション規約

Python 3.11+ を前提とする。`from __future__ import annotations` は使わない。

## 組み込み型を使う

`Optional[X]` → `X | None`、`Dict[K,V]` → `dict[K,V]`、`List[X]` → `list[X]`、`Tuple[X,Y]` → `tuple[X,Y]`、`Union[X,Y]` → `X | Y`。

## typing / collections.abc のインポート

```python
from typing import Any, NotRequired, TypedDict   # これらのみ typing から
from collections.abc import Callable, Iterator, AsyncGenerator, Generator, Mapping, Sequence
```

`Callable` 等は `typing` の同名型が非推奨エイリアスになったため `collections.abc` へ移す。

## 戻り値型は必ず書く

```python
def validate(metrics: dict[str, Any]) -> tuple[bool, str | None]: ...
```

## 型安全化の運用

型定義を触ったら変更対象モジュールで pyright / basedpyright を実行し、新しい型エラーを残したまま完了扱いにしない。`cast` や `Any` で消すのは外部ライブラリ境界・動的 JSON 境界に限定する。

## `Any` の使用を最小限に

使ってよい箇所：

| 箇所 | 理由 |
|---|---|
| 外部 API レスポンス（EDINET / MOF 等）の `dict[str, Any]` | JSON の値型が実行時にしか判明しない |
| 任意型を受け入れる検証関数の引数（`is_nan`, `is_valid_value`） | `float`, `str`, `None` など全型を動的に処理する |
| MCP プロトコルの `arguments: dict[str, Any]` | プロトコル仕様で型が規定されていない |

値が `float | None` などに絞れる場合は `Any` を使わない（`dict[str, Any]` → `dict[str, float | None]`、`-> Any` → 具体型 など）。

### 定数ファイルの構造化 dict には TypedDict を使う

```python
class _ComponentDef(TypedDict):
    label: str
    tags: list[str]
    optional_field: NotRequired[str]  # 一部エントリにしか存在しないフィールド

COMPONENT_DEFINITIONS: list[_ComponentDef] = [...]
```

`total=False` は全フィールドをオプションにするため不適切。部分オプションは `NotRequired` を使う。

## `TypedDict` と `dataclass` の使い分け

| ケース | 使うもの |
|---|---|
| JSON / キャッシュ / レイヤー間 dict の型付け | `TypedDict` |
| ロジックを持つオブジェクト、immutable な値 | `dataclass` |
| 一時的な戻り値で型が単純（2〜3フィールド） | `tuple[X, Y]` |

複数モジュールが共有するドメイン TypedDict は `mebuki/utils/` に独立ファイルとして置く（例: `metrics_types.py`）。

## 段階的に組み立てる辞書には `total=False`

```python
class CalculatedData(TypedDict, total=False):  # _apply_* で逐次追加
    Sales: float | None
    GrossProfit: float | None

class YearEntry(TypedDict):  # 常に全フィールドが揃う
    fy_end: str | None
    RawData: RawData
    CalculatedData: CalculatedData
```

`total=False` や `NotRequired` のキーは `dict["key"]` でなく `.get("key")` で読む。

## `None` を含む値は演算前に絞る

変換関数の戻り値は型チェッカーが追跡できない場合があるため、演算する変数を直接ガードする。

```python
cfo_m = to_millions(raw_values.get("CFO"))
cfi_m = to_millions(raw_values.get("CFI"))
cfc = (cfo_m + cfi_m) if cfo_m is not None and cfi_m is not None else None
```

## 読み取り専用の引数は `Sequence` / `Mapping`

`list` は invariant なので `list[YearEntry]` を `list[dict[str, Any]]` に渡せない。読み取りだけなら `list` → `Sequence[T]`、`dict` → `Mapping[str, Any]`。これにより TypedDict をそのまま渡せる。

## 戻り値 TypedDict は変数注釈で推論を助ける

```python
metrics: MetricsResult = {"code": latest.get("Code"), "analysis_years": len(years_data)}
```

戻り値は実際の構造に合わせる（`list[StockSearchResult]` を `list[dict[str, Any]]` に広げない）。

## その他の型安全ルール

- **コールバック**: `Callable[[dict], bool]` と宣言したら必ず `bool` を返す。`dict.get()` は `Any | None` になるので `bool(...)` で明示する。
- **`asyncio.gather(return_exceptions=True)`**: 結果に `BaseException` が混ざる。`Exception` でなく `BaseException` で絞る。最後の例外を `raise` するときは `None` ガードを入れる。
- **Optional な共有クライアント**: `self.edinet_client` のような `T | None` 属性はガード後にローカル変数へ束縛する（ネスト関数や await をまたぐと型が絞られないため）。APIキー更新メソッドの引数は `str | None` にする。
- **TypedDict に未定義キーを足さない**: 未定義キーが必要なら `dict(...)` でコピーしてから追加するか、TypedDict 定義にキーを追加する。
- **外部ライブラリの属性値**: BeautifulSoup の `Tag.get()` は `str` 以外も返し得る。`int(tag.get("colspan", 1))` のように直接変換せず、`parse_html_int_attribute(cell, "colspan")` を使う。
