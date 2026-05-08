BLUE TICKER は、EDINET APIを最大限に活用した日本株分析 Python CLI ツールです。

---

## ✨ 主要機能

### 高度な財務・市場分析 (CLI)
- **対話型モード**: `ticker` コマンドだけで、銘柄検索や財務概要の確認が可能です。
- **定性情報の抽出**: 有価証券報告書の重要セクション（MD&A、事業リスク等）を即座に解析し、核心を抽出。
- **ウォッチリスト管理**: 注目銘柄を登録・管理。`ticker watch` コマンドで操作可能。
- **ポートフォリオ管理**: 保有銘柄のロット・口座別管理、総平均法による損益計算。`ticker portfolio` コマンドで操作可能。

---

## 🚀 インストール & セットアップ

### 1. インストール

#### Homebrew

```bash
brew tap sollahiro/blue-ticker
brew install blue-ticker
```

### 2. API キーの設定
CLI の初期設定コマンドを実行し、EDINET APIキャッシュを準備します：

```bash
ticker config init
ticker cache prepare --years 3
```
以下のキーが必要です：
- **EDINET APIキー**: [公式サイト](https://disclosure2.edinet-fsa.go.jp/)で取得

## 📂 使い方 (CLI)

代表的なコマンドは以下です。短縮 alias として `blt` も利用できます。

```bash
# 銘柄検索
ticker search トヨタ

# 財務分析
ticker analyze 7203
ticker analyze 7203 --years 6

# キャッシュ確認
ticker cache status
ticker cache prepare --years 3
ticker cache catchup --years 3
ticker cache refresh --years 3
ticker cache clean

# ウォッチリスト
ticker watch add 7203
ticker watch list
ticker watch remove 7203

# ポートフォリオ
ticker portfolio add 7203 100 2500 --broker SBI --account NISA
ticker portfolio list
ticker portfolio sell 7203 50

# 短縮 alias
blt analyze 7203
```

## ⚖️ 免責事項

本ソフトウェアおよび提供される情報は、投資判断の参考として提供されるものであり、投資の勧誘を目的としたものではありません。最終的な投資判断は、必ず利用者ご自身の責任において行ってください。

---
Developed with ❤️ by [sollahiro](https://github.com/sollahiro)
