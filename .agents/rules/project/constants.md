# 定数の置き場所

マジックナンバー・文字列リテラルは `mebuki/constants/` 配下に置く。コードに直書きしない。

## ファイル分類

| ファイル | 置くもの |
|---|---|
| `formats.py` | 日付・文字列フォーマットに関する定数（桁数など） |
| `financial.py` | 財務計算の単位・乗数（円換算、パーセント変換など） |
| `xbrl.py` | XBRLタグ名・セクション定義 |
| `api.py` | 外部APIのベースURL |

## 使用例

```python
from mebuki.constants.formats import DATE_LEN_COMPACT, DATE_LEN_HYPHENATED
from mebuki.constants.financial import MILLION_YEN, PERCENT
from mebuki.constants.xbrl import GROSS_PROFIT_DIRECT_TAGS, CF_OPERATING_TAGS
from mebuki.constants.api import EDINET_API_BASE_URL
```

## やってはいけないパターン

```python
# ❌ マジックナンバーの直書き
value / 1_000_000
ratio * 100
if len(date_str) == 8:

# ❌ タグ名のハードコード
allowed_tags = ["GrossProfit", "GrossProfitIFRS"]

# ✅ 定数を使う
from mebuki.constants.financial import MILLION_YEN, PERCENT
from mebuki.constants.formats import DATE_LEN_COMPACT
from mebuki.constants.xbrl import GROSS_PROFIT_DIRECT_TAGS

value / MILLION_YEN
ratio * PERCENT
if len(date_str) == DATE_LEN_COMPACT:
allowed_tags = GROSS_PROFIT_DIRECT_TAGS
```

## 新しい定数を追加するとき

既存のファイル分類に合うものはそのファイルへ追加する。どれにも当てはまらない場合は、新ファイルを作る前にユーザーへ確認する。
