"""
プロトタイプ: XBRL → フィールドパース → 項目パース（IFRS 連結財政状態計算書）

対象: 味の素（2802）有価証券報告書 2025-03-31 期 (docID: S100VXJA)

実行方法:
    cd /path/to/blue-ticker
    poetry run python scripts/proto_ifrs_bs.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from blue_ticker.analysis.field_parser import (
    FieldSet,
    ResolvedItem,
    derive_subtraction,
    parse_instant_fields,
    resolve_item,
)
from blue_ticker.constants.financial import MILLION_YEN
from blue_ticker.constants.xbrl import IFRS_BS_ITEM_DEFINITIONS

XBRL_DIR = Path("tmp_cache/edinet/S100VXJA_xbrl/XBRL/PublicDoc")


def _fmt(value: float | None) -> str:
    if value is None:
        return "  N/A"
    return f"{value / MILLION_YEN / 1000:8.1f}十億円"


def resolve_bs_items(field_set: FieldSet) -> list[tuple[str, ResolvedItem]]:
    results: list[tuple[str, ResolvedItem]] = []
    for item_def in IFRS_BS_ITEM_DEFINITIONS:
        resolved = resolve_item(field_set, item_def["tags"])
        if resolved["tag"] is None and "derive" in item_def:
            derive_def = item_def["derive"]
            resolved = derive_subtraction(
                field_set,
                derive_def["minuend_tags"],
                derive_def["subtrahend_tags"],
            )
        results.append((item_def["label"], resolved))
    return results


def main() -> None:
    print("=== Stage 1: フィールドパース ===")
    field_set = parse_instant_fields(XBRL_DIR)
    print(f"収集タグ数: {len(field_set)}")

    ifrs_bs_tags = [
        t for t in field_set
        if any(k in t for k in ("Assets", "Liabilities", "Equity"))
        and "IFRS" in t
    ]
    print(f"IFRS BS 関連タグ: {len(ifrs_bs_tags)}")
    for tag in sorted(ifrs_bs_tags):
        fv = field_set[tag]
        print(f"  {tag:60s} 当期={_fmt(fv['current'])}  前期={_fmt(fv['prior'])}")

    print()
    print("=== Stage 2: 項目パース ===")
    print(f"{'項目':<16} {'当期末':>14} {'前期末':>14}  使用タグ")
    print("-" * 70)

    items = resolve_bs_items(field_set)
    for label, resolved in items:
        tag_str = resolved["tag"] or "(見つからず)"
        print(f"{label:<16} {_fmt(resolved['current']):>14} {_fmt(resolved['prior']):>14}  {tag_str}")

    print()
    print("=== 検証: 資産合計 ≒ 負債合計 + 資本合計 ===")
    item_map = {label: r for label, r in items}
    assets = item_map["資産合計"]["current"]
    liab = item_map["負債合計"]["current"]
    equity = item_map["資本合計"]["current"]
    if assets and liab and equity:
        diff = assets - (liab + equity)
        print(f"  資産合計 - (負債合計 + 資本合計) = {diff / MILLION_YEN:.0f}百万円")
    else:
        print("  値が不足しているため検証不可")


if __name__ == "__main__":
    main()
