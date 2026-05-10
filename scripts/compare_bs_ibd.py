"""
現行ロジック vs フィールドパーサー プロトタイプ 比較

smoke企業全社で extract_balance_sheet / extract_interest_bearing_debt の結果と
field_parser ベースの結果を並べて差異を確認する。

実行方法:
    cd /path/to/blue-ticker
    poetry run python scripts/compare_bs_ibd.py
"""

import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from blue_ticker.analysis.balance_sheet import extract_balance_sheet
from blue_ticker.analysis.field_parser import (
    FieldSet,
    parse_instant_fields,
    parse_usgaap_html_bs_fields,
    resolve_aggregate,
    resolve_item,
    derive_subtraction,
)
from blue_ticker.analysis.interest_bearing_debt import extract_interest_bearing_debt
from blue_ticker.constants.financial import MILLION_YEN
from scripts.smoke_bs import (
    ALL_STANDARD_BS_ITEMS,
    SMOKE_ENTRIES,
    _IBD_CURRENT_COMPONENTS,
    _IBD_IFRS_CL_TAGS,
    _IBD_IFRS_NCL_TAGS,
    _IBD_NON_CURRENT_COMPONENTS,
    _is_usgaap,
    resolve_ibd,
)

CACHE_DIR = Path("tmp_cache/edinet")
THRESHOLD_M = 10  # 差異を「実質一致」とみなす閾値（百万円）


def _b(val: float | None) -> str:
    if val is None:
        return "      N/A"
    return f"{val / MILLION_YEN / 1000:8.1f}B"


def _diff_str(legacy: float | None, proto: float | None) -> str:
    if legacy is None and proto is None:
        return "  both N/A"
    if legacy is None:
        return "  legacy=N/A"
    if proto is None:
        return "  proto=N/A"
    diff = proto - legacy
    diff_m = diff / MILLION_YEN
    marker = "" if abs(diff_m) <= THRESHOLD_M else " <<"
    return f"  Δ{diff_m:+.0f}M{marker}"


@dataclass
class BSRow:
    label: str
    legacy: float | None
    proto: float | None


def resolve_bs_proto(field_set: FieldSet) -> dict[str, float | None]:
    result: dict[str, float | None] = {}
    for item_def in ALL_STANDARD_BS_ITEMS:
        from blue_ticker.analysis.field_parser import ResolvedItem
        resolved = resolve_item(field_set, item_def["tags"])
        if resolved["tag"] is None and "derive" in item_def:
            d = item_def["derive"]
            resolved = derive_subtraction(field_set, d["minuend_tags"], d["subtrahend_tags"])
        result[item_def["label"]] = resolved["current"]
    return result


def _build_proto_field_set(xbrl_dir: Path) -> FieldSet:
    field_set = parse_instant_fields(xbrl_dir)
    if _is_usgaap(field_set):
        field_set.update(parse_usgaap_html_bs_fields(xbrl_dir))
    return field_set


def compare_bs(xbrl_dir: Path) -> list[BSRow]:
    legacy = extract_balance_sheet(xbrl_dir)
    proto = resolve_bs_proto(_build_proto_field_set(xbrl_dir))

    return [
        BSRow("資産合計",    legacy["total_assets"],          proto["資産合計"]),
        BSRow("流動資産",    legacy["current_assets"],         proto["流動資産"]),
        BSRow("非流動資産",  legacy["non_current_assets"],     proto["非流動資産"]),
        BSRow("流動負債",    legacy["current_liabilities"],    proto["流動負債"]),
        BSRow("非流動負債",  legacy["non_current_liabilities"],proto["非流動負債"]),
        BSRow("純資産",      legacy["net_assets"],             proto["純資産/資本合計"]),
    ]


def compare_ibd(xbrl_dir: Path) -> tuple[float | None, float | None, str, str]:
    legacy_result = extract_interest_bearing_debt(xbrl_dir)
    legacy_val = legacy_result["current"]
    legacy_method = legacy_result["method"]

    proto_result = resolve_ibd(_build_proto_field_set(xbrl_dir))
    proto_val = proto_result["current"]
    proto_tag = proto_result["tag"] or "N/A"

    return legacy_val, proto_val, legacy_method, proto_tag


def main() -> None:
    for entry in SMOKE_ENTRIES:
        xbrl_dir = CACHE_DIR / f"{entry.doc_id}_xbrl" / "XBRL" / "PublicDoc"
        if not xbrl_dir.exists():
            print(f"\n{'='*60}")
            print(f"{entry.name} ({entry.standard}) — XBRLなし")
            continue

        print(f"\n{'='*60}")
        print(f"{entry.name} ({entry.standard}, {entry.period_end})")
        print(f"{'─'*60}")

        # BS 比較
        print(f"  {'項目':<12} {'現行':>10} {'proto':>10}  {'差異'}")
        print(f"  {'─'*48}")
        bs_rows = compare_bs(xbrl_dir)
        for row in bs_rows:
            print(
                f"  {row.label:<12} {_b(row.legacy):>10} {_b(row.proto):>10}"
                f"  {_diff_str(row.legacy, row.proto)}"
            )

        # IBD 比較
        print(f"  {'─'*48}")
        legacy_ibd, proto_ibd, legacy_method, proto_tag = compare_ibd(xbrl_dir)
        print(
            f"  {'IBD合計':<12} {_b(legacy_ibd):>10} {_b(proto_ibd):>10}"
            f"  {_diff_str(legacy_ibd, proto_ibd)}"
        )
        print(f"  現行method : {legacy_method}")
        print(f"  protoタグ  : {proto_tag[:80]}")


if __name__ == "__main__":
    main()
