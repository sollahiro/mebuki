# 依存関係の管理方針

外部パッケージの追加は最小限に抑える。理由は以下の2点：

- **セキュリティ**: 依存パッケージはサプライチェーン攻撃の攻撃面になる。パッケージが増えるほど脆弱性混入リスクが上がる。
- **容量**: インストールサイズ・`poetry.lock` の肥大化を防ぐ。

標準ライブラリで賄えるものは外部パッケージを追加しない。

## 現在の依存関係（v2.15.2）

| パッケージ | 採用理由 |
|---|---|
| `aiohttp` | 非同期HTTP通信（`asyncio` + `urllib` では代替不可） |
| `beautifulsoup4` | HTML/XML の柔軟なパース（標準 `xml` では壊れた HTML を扱えない） |
| `mcp` | MCPサーバープロトコル実装（外部仕様） |

## 新規パッケージ追加の判断基準

以下をすべて満たす場合のみ追加を検討する。

1. **標準ライブラリで実現不可能**である
2. **既存の依存パッケージでも実現不可能**である
3. メンテナンスが継続されている実績あるパッケージである

## 追加が必要な場合は必ず事前に確認する

上記基準を満たすと判断した場合でも、`pyproject.toml` を変更する前にユーザーへ確認を取ること。

確認時に伝える内容：
- 追加しようとするパッケージ名とバージョン
- なぜ標準ライブラリ・既存依存で代替できないか
- そのパッケージを使う箇所

## やってはいけないパターン

```python
# ❌ 標準ライブラリで書けるものに外部パッケージを使う
import arrow          # → datetime で足りる
import click          # → argparse で足りる
import pydantic       # → dataclass / TypedDict で足りる
import requests       # → aiohttp（既存）または urllib で足りる
import python-dotenv  # → os.environ で足りる
```

## やるべきこと

```python
# ✅ 標準ライブラリを使う
import datetime
import argparse
import json
import pathlib
import xml.etree.ElementTree as ET
```
