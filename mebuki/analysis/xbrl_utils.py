"""
XBRL解析共通ユーティリティ

gross_profit / cash_flow / interest_bearing_debt 各モジュールで共有する
低レベルのXML解析ヘルパー。コンテキスト判定・会計基準判定など
モジュール固有のロジックはここに置かない。
"""

import re
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any


def parse_html_number(text: str) -> float | None:
    """HTML表セルの数値テキストを float に変換（百万円単位のまま）。
    "22,548" → 22548.0, "22,548百万円" → 22548.0, "△8,752" → -8752.0, "－" → None
    """
    if not text:
        return None
    text = text.strip()
    text = re.sub(r'(百万円|十万円|億円|兆円|千円|百円|万円|円)$', '', text).strip()
    text = text.replace(",", "").replace("，", "")
    # △ は日本の会計慣行で負数を示す（例: △8,752 → -8752）
    if text.startswith("△"):
        text = "-" + text[1:]
    if text in ("－", "-", "―", "—", ""):
        return None
    try:
        return float(text)
    except ValueError:
        return None


def parse_xbrl_value(text: str | None) -> float | None:
    """XBRL数値テキストを float に変換。nil・空文字は None を返す。"""
    if not text or text.strip() in ("", "nil"):
        return None
    try:
        return float(text.strip())
    except (ValueError, TypeError):
        return None


_XSI_NIL = "{http://www.w3.org/2001/XMLSchema-instance}nil"


def collect_numeric_elements(
    xml_file: Path,
    allowed_tags: frozenset[str] | None = None,
    nil_as_zero: bool = False,
) -> dict[str, Any]:
    """XMLファイルから {local_tag: {contextRef: value}} の辞書を返す。

    allowed_tags を指定すると、そのセット外のタグをスキップして高速化できる。
    nil_as_zero=True のとき xsi:nil="true" の要素を 0.0 として記録する。
    """
    results: dict = {}
    try:
        tree = ET.parse(xml_file)
        root = tree.getroot()
        for elem in root.iter():
            tag = elem.tag
            local_tag = tag.split("}")[1] if "}" in tag else tag
            if allowed_tags is not None and local_tag not in allowed_tags:
                continue
            ctx = elem.attrib.get("contextRef", "")
            value = parse_xbrl_value(elem.text)
            if value is None and nil_as_zero and elem.attrib.get(_XSI_NIL, "").lower() == "true":
                value = 0.0
            if value is not None and ctx:
                if local_tag not in results:
                    results[local_tag] = {}
                results[local_tag][ctx] = value
    except ET.ParseError:
        pass
    return results


def find_xbrl_files(xbrl_dir: Path) -> list[Path]:
    """XBRLディレクトリからインスタンス文書（.xml / .xbrl）を返す。

    ラベル・プレゼンテーション・計算・定義リンクベースは除外する。
    """
    xml_files = [
        f for f in xbrl_dir.rglob("*.xml")
        if not any(s in f.name for s in ["_lab", "_pre", "_cal", "_def"])
    ]
    xml_files += list(xbrl_dir.rglob("*.xbrl"))
    return xml_files
