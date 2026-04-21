"""
XBRL解析共通ユーティリティ

gross_profit / cash_flow / interest_bearing_debt 各モジュールで共有する
低レベルのXML解析ヘルパー。コンテキスト判定・会計基準判定など
モジュール固有のロジックはここに置かない。
"""

import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Dict, Optional


def parse_xbrl_value(text: Optional[str]) -> Optional[float]:
    """XBRL数値テキストを float に変換。nil・空文字は None を返す。"""
    if not text or text.strip() in ("", "nil"):
        return None
    try:
        return float(text.strip())
    except (ValueError, TypeError):
        return None


def collect_numeric_elements(
    xml_file: Path,
    allowed_tags: frozenset[str] | None = None,
) -> Dict[str, Any]:
    """XMLファイルから {local_tag: {contextRef: value}} の辞書を返す。

    allowed_tags を指定すると、そのセット外のタグをスキップして高速化できる。
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
