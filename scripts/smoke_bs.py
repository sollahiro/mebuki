"""
smoke企業全社での連結財政状態計算書プロトタイプ実行

実行方法:
    cd /path/to/blue-ticker
    poetry run python scripts/smoke_bs.py
"""

import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from blue_ticker.analysis.field_parser import (
    FieldSet,
    ResolvedItem,
)
from blue_ticker.analysis.interest_bearing_debt import resolve_ibd
from blue_ticker.analysis.sections import BalanceSheetSection
from blue_ticker.constants.financial import MILLION_YEN
from blue_ticker.constants.xbrl import (
    ALL_STANDARD_BS_ITEMS,
    IBD_CURRENT_COMPONENTS as _IBD_CURRENT_COMPONENTS,
    IBD_IFRS_CL_TAGS as _IBD_IFRS_CL_TAGS,
    IBD_IFRS_NCL_TAGS as _IBD_IFRS_NCL_TAGS,
    IBD_NON_CURRENT_COMPONENTS as _IBD_NON_CURRENT_COMPONENTS,
    USGAAP_HTML_NCA_COMPONENTS as _USGAAP_HTML_NCA_COMPONENTS,
)

CACHE_DIR = Path("tmp_cache/edinet")


@dataclass
class SmokeEntry:
    code: str
    name: str
    standard: str
    doc_id: str
    period_end: str


SMOKE_ENTRIES: list[SmokeEntry] = [
    SmokeEntry("3490", "アズ企画設計",  "J-GAAP nonconsolidated", "S100VU4O", "2025-02-28"),
    SmokeEntry("2802", "味の素",        "IFRS",                   "S100VXJA", "2025-03-31"),
    SmokeEntry("6103", "オークマ",      "J-GAAP",                 "S100W043", "2025-03-31"),
    SmokeEntry("8316", "三井住友FG",    "J-GAAP financial",       "S100W0S7", "2025-03-31"),
    SmokeEntry("8306", "三菱UFJFG",    "J-GAAP financial",       "S100W4FB", "2025-03-31"),
    SmokeEntry("4901", "富士フイルム",  "US-GAAP",                "S100W3XJ", "2025-03-31"),
    SmokeEntry("7269", "スズキ",        "IFRS",                   "S100W4MT", "2025-03-31"),
    SmokeEntry("6326", "クボタ",        "IFRS",                   "S100XR0M", "2025-12-31"),
    SmokeEntry("7422", "東邦レマック",  "J-GAAP nonconsolidated", "S100XRD8", "2025-12-20"),
    SmokeEntry("7751", "キヤノン",      "US-GAAP/IFRS",           "S100XTLJ", "2025-12-31"),
]


def resolve_bs(section: BalanceSheetSection) -> list[tuple[str, ResolvedItem]]:
    results: list[tuple[str, ResolvedItem]] = []
    for item_def in ALL_STANDARD_BS_ITEMS:
        resolved = section.resolve(item_def["tags"])
        if resolved["tag"] is None and "derive" in item_def:
            d = item_def["derive"]
            resolved = section.derive_subtraction(d["minuend_tags"], d["subtrahend_tags"])
        if item_def["field"] == "NonCurrentAssets" and resolved["current"] is None:
            resolved = section.resolve_aggregate(_USGAAP_HTML_NCA_COMPONENTS)
        results.append((item_def["label"], resolved))
    return results


def _is_usgaap(field_set: FieldSet) -> bool:
    return any("USGAAP" in tag for tag in field_set)


def _fmt(value: float | None) -> str:
    if value is None:
        return "    N/A "
    return f"{value / MILLION_YEN / 1000:7.1f}B"


def _check(items: list[tuple[str, ResolvedItem]]) -> str:
    m = {label: r for label, r in items}
    assets = m["資産合計"]["current"]
    liab_c = m["流動負債"]["current"]
    liab_nc = m["非流動負債"]["current"]
    equity = m["純資産/資本合計"]["current"]
    if assets is None or liab_c is None or liab_nc is None or equity is None:
        return "検証不可"
    diff = abs(assets - (liab_c + liab_nc + equity))
    ratio = diff / assets if assets else 0
    return f"OK (差{diff/MILLION_YEN:.0f}M)" if ratio < 0.01 else f"NG (差{diff/MILLION_YEN:.0f}M)"


def main() -> None:
    header = (
        f"{'社名':<14} {'会計基準':<24}"
        f" {'資産合計':>9} {'流動資産':>9} {'非流動':>9}"
        f" {'流動負債':>9} {'非流動負債':>10} {'純資産':>9}"
        f"  {'IBD合計':>9}  {'バランス'}"
    )
    print(header)
    print("-" * len(header))

    for entry in SMOKE_ENTRIES:
        xbrl_dir = CACHE_DIR / f"{entry.doc_id}_xbrl" / "XBRL" / "PublicDoc"
        if not xbrl_dir.exists():
            print(f"{entry.name:<14} {entry.standard:<24} [XBRLディレクトリなし]")
            continue

        section = BalanceSheetSection.from_xbrl(xbrl_dir)
        items = resolve_bs(section)
        m = {label: r for label, r in items}
        ibd = resolve_ibd(section)

        print(
            f"{entry.name:<14} {entry.standard:<24}"
            f" {_fmt(m['資産合計']['current'])}"
            f" {_fmt(m['流動資産']['current'])}"
            f" {_fmt(m['非流動資産']['current'])}"
            f" {_fmt(m['流動負債']['current'])}"
            f" {_fmt(m['非流動負債']['current'])}"
            f" {_fmt(m['純資産/資本合計']['current'])}"
            f"  {_fmt(ibd['current'])}"
            f"  {_check(items)}"
        )
        if ibd["tag"]:
            print(f"  {'':14}   IBD: {ibd['tag']}")

        missing = [label for label, r in items if r["current"] is None]
        if missing:
            print(f"  {'':14} -> 取得不可: {', '.join(missing)}")


if __name__ == "__main__":
    main()
