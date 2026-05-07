# XBRL解析モジュールの規約

## 共通ユーティリティの使用

XBRL解析モジュール（`blue_ticker/analysis/` 配下）では、以下の共通関数を必ず `xbrl_utils.py` からインポートして使うこと。各モジュールに同じ実装を書き直してはならない。

```python
from blue_ticker.analysis.xbrl_utils import parse_xbrl_value, collect_numeric_elements, find_xbrl_files
```

| 関数 | 用途 |
|---|---|
| `parse_xbrl_value(text)` | XBRL数値テキスト → `float \| None`（nil・空文字は None） |
| `collect_numeric_elements(xml_file, allowed_tags)` | XMLファイル → `{local_tag: {contextRef: value}}` |
| `find_xbrl_files(xbrl_dir)` | XBRLディレクトリ → インスタンス文書リスト（ラベル等を除外） |

## モジュール固有のロジック（共通化しない）

以下はモジュールごとに財務諸表の性質が異なるため、`xbrl_utils.py` には置かない。

| ロジック | 理由 |
|---|---|
| コンテキスト判定（`_is_consolidated_duration` 等） | Duration（損益計算書・CF）と Instant（貸借対照表）は別概念 |
| 会計基準判定（`_detect_accounting_standard`） | IBD は IFRS/US-GAAP 混在判別など高度なロジックが必要 |

## 現行モジュール構成

| モジュール | コンテキスト種別 | 抽出対象 |
|---|---|---|
| `gross_profit.py` | Duration | 損益計算書（売上総利益） |
| `cash_flow.py` | Duration | CF計算書（営業CF・投資CF） |
| `interest_bearing_debt.py` | Instant | 貸借対照表（有利子負債） |
| `employees.py` | Instant | 従業員数（連結優先・個別フォールバック） |
| `net_revenue.py` | Duration | IFRS金融会社向け純収益・事業利益 |

## 詳細リファレンス

タグ体系・コンテキスト命名規則・会計基準判定ロジック・US-GAAP HTMLパースの仕様は `docs/xbrl-parsing.md` を参照してください。
