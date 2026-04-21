# エラーハンドリング規約

分析・サービス層のエラー処理は**戻り値パターン**で統一する。例外クラスを新設して raise する設計は採用しない。

## 正規パターン

```python
# ✅ 戻り値でエラー状態を返す
def validate_metrics_for_analysis(metrics, required_years=2) -> tuple[bool, str | None]:
    if available_years < required_years:
        return False, "データが不足しています"
    return True, None

is_valid, message = validate_metrics_for_analysis(metrics)
if not is_valid:
    print(message)
    return
```

## やってはいけないパターン

```python
# ❌ 例外クラスを新設して raise する
class InsufficientDataError(Exception): ...
raise InsufficientDataError(required_years=5, available_years=2)
```

## 既存ユーティリティ（`mebuki/utils/errors.py`）

| 関数・クラス | 用途 |
|---|---|
| `DataAvailability` | データ充足状態の Enum（SUFFICIENT / INSUFFICIENT / NO_DATA / PARTIAL） |
| `check_data_availability(metrics, required_years)` | Enum を返す充足チェック |
| `get_data_availability_message(metrics, required_years)` | ユーザー向けメッセージ文字列を返す |
| `validate_metrics_for_analysis(metrics, required_years)` | `(bool, message \| None)` を返す総合検証 |
