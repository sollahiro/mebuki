"""
smoke企業全社での連結財政状態計算書プロトタイプ実行

実行方法:
    cd /path/to/blue-ticker
    poetry run python scripts/smoke_bs.py
"""

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import NotRequired, TypedDict

sys.path.insert(0, str(Path(__file__).parent.parent))

from blue_ticker.analysis.field_parser import (
    FieldSet,
    ResolvedItem,
    derive_subtraction,
    parse_instant_fields,
    parse_usgaap_html_bs_fields,
    resolve_aggregate,
    resolve_item,
)
from blue_ticker.constants.financial import MILLION_YEN

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


class _BSItemDef(TypedDict):
    label: str
    tags: list[str]
    derive: NotRequired[dict[str, list[str]]]


# J-GAAP / IFRS / US-GAAP 共通の項目定義（優先順: J-GAAP → IFRS → US-GAAP → HTML仮想タグ）
ALL_STANDARD_BS_ITEMS: list[_BSItemDef] = [
    {
        "label": "資産合計",
        "tags": [
            "TotalAssets", "Assets",                                   # J-GAAP
            "TotalAssetsIFRS", "AssetsIFRS",                           # IFRS
            "TotalAssetsUSGAAP",                                        # US-GAAP
            "TotalAssetsSummaryOfBusinessResults",
            "TotalAssetsUSGAAPSummaryOfBusinessResults",
        ],
    },
    {
        "label": "流動資産",
        "tags": [
            "CurrentAssets",              # J-GAAP
            "CurrentAssetsIFRS",          # IFRS
            "CurrentAssetsUSGAAP",        # US-GAAP
            "USGAAP_HTML_CurrentAssets",  # US-GAAP HTML
        ],
    },
    {
        "label": "非流動資産",
        "tags": [
            "NoncurrentAssets", "NonCurrentAssets",  # J-GAAP
            "NonCurrentAssetsIFRS",                   # IFRS
            "NonCurrentAssetsUSGAAP",                 # US-GAAP
        ],
        "derive": {
            "minuend_tags": [
                "TotalAssets", "Assets", "TotalAssetsIFRS", "AssetsIFRS", "TotalAssetsUSGAAP",
                "TotalAssetsUSGAAPSummaryOfBusinessResults",
            ],
            "subtrahend_tags": [
                "CurrentAssets", "CurrentAssetsIFRS", "CurrentAssetsUSGAAP",
                "USGAAP_HTML_CurrentAssets",
            ],
        },
    },
    {
        "label": "流動負債",
        "tags": [
            "CurrentLiabilities",                                        # J-GAAP
            "TotalCurrentLiabilitiesIFRS", "CurrentLiabilitiesIFRS",    # IFRS
            "CurrentLiabilitiesUSGAAP",                                  # US-GAAP
            "USGAAP_HTML_CurrentLiabilities",                            # US-GAAP HTML
        ],
    },
    {
        "label": "非流動負債",
        "tags": [
            "NoncurrentLiabilities", "NonCurrentLiabilities",           # J-GAAP
            "NonCurrentLiabilitiesIFRS",                                 # IFRS
            "LongTermLiabilitiesUSGAAP", "NonCurrentLiabilitiesUSGAAP", # US-GAAP
            "USGAAP_HTML_NonCurrentLiabilities",                         # US-GAAP HTML
        ],
        "derive": {
            "minuend_tags": [
                "Liabilities", "LiabilitiesIFRS", "TotalLiabilitiesUSGAAP",
                "USGAAP_HTML_TotalLiabilities",
            ],
            "subtrahend_tags": [
                "CurrentLiabilities",
                "TotalCurrentLiabilitiesIFRS", "CurrentLiabilitiesIFRS",
                "CurrentLiabilitiesUSGAAP",
                "USGAAP_HTML_CurrentLiabilities",
            ],
        },
    },
    {
        "label": "純資産/資本合計",
        "tags": [
            "NetAssets",                                               # J-GAAP（直接BS）
            "EquityIFRS", "TotalEquityIFRS",                          # IFRS（合計）
            "EquityIncludingPortionAttributableToNonControllingInterestIFRSSummaryOfBusinessResults",
            "NetAssetsUSGAAP", "TotalEquityUSGAAP",                   # US-GAAP（合計）
            "EquityIncludingPortionAttributableToNonControllingInterestUSGAAPSummaryOfBusinessResults",
            "USGAAP_HTML_NetAssets",                                   # US-GAAP HTML
            # サマリータグは直接BSタグが取れない場合のフォールバック
            "NetAssetsSummaryOfBusinessResults",
            "EquityAttributableToOwnersOfParentIFRS",
            "EquityAttributableToOwnersOfParentUSGAAP",
            "EquityAttributableToOwnersOfParentUSGAAPSummaryOfBusinessResults",
        ],
    },
]

# US-GAAP 非流動資産コンポーネント（HTML 仮想タグ）
_USGAAP_HTML_NCA_COMPONENTS: list[list[str]] = [
    ["USGAAP_HTML_PPENet"],
    ["USGAAP_HTML_InvestmentsLTReceivables"],
    ["USGAAP_HTML_OtherNCA"],
]


# 有利子負債（IBD）コンポーネント定義
# 各要素は「1コンポーネントの候補タグリスト（優先順）」
_IBD_CURRENT_COMPONENTS: list[list[str]] = [
    ["ShortTermLoansPayable", "BorrowingsCLIFRS"],                                              # 短期借入金
    ["CommercialPapersLiabilities", "CommercialPapersCLIFRS"],                                 # CP
    ["ShortTermBondsPayable"],                                                                  # 短期社債
    ["CurrentPortionOfBonds", "RedeemableBondsWithinOneYear", "CurrentPortionOfBondsCLIFRS"],  # 1年内社債
    ["CurrentPortionOfLongTermLoansPayable", "CurrentPortionOfLongTermBorrowingsCLIFRS"],       # 1年内長期借入金
]
_IBD_NON_CURRENT_COMPONENTS: list[list[str]] = [
    ["BondsPayable", "BondsPayableNCLIFRS"],       # 社債
    ["LongTermLoansPayable", "BorrowingsNCLIFRS"],  # 長期借入金
]
# IFRS 集約タグ（流動・非流動それぞれ1タグで全コンポーネントを集約）
_IBD_IFRS_CL_TAGS = ["InterestBearingLiabilitiesCLIFRS", "BondsAndBorrowingsCLIFRS"]
_IBD_IFRS_NCL_TAGS = ["InterestBearingLiabilitiesNCLIFRS", "BondsAndBorrowingsNCLIFRS"]


def resolve_ibd(field_set: FieldSet) -> ResolvedItem:
    """有利子負債合計を解決する: 直接法 → IFRS集約 → コンポーネント積み上げ → HTML仮想タグ"""
    # 1. 直接法
    direct = resolve_item(field_set, ["InterestBearingDebt", "InterestBearingLiabilities"])
    if direct["tag"]:
        return direct
    # 2. IFRS 集約タグ（流動 + 非流動）
    ifrs_agg = resolve_aggregate(field_set, [_IBD_IFRS_CL_TAGS, _IBD_IFRS_NCL_TAGS])
    if ifrs_agg["tag"]:
        return ifrs_agg
    # 3. コンポーネント積み上げ
    comp = resolve_aggregate(field_set, _IBD_CURRENT_COMPONENTS + _IBD_NON_CURRENT_COMPONENTS)
    if comp["tag"]:
        return comp
    # 4. US-GAAP HTML 仮想タグ（流動 + 非流動）
    return resolve_aggregate(field_set, [["USGAAP_HTML_IBDCurrent"], ["USGAAP_HTML_IBDNonCurrent"]])


def resolve_bs(field_set: FieldSet) -> list[tuple[str, ResolvedItem]]:
    results: list[tuple[str, ResolvedItem]] = []
    for item_def in ALL_STANDARD_BS_ITEMS:
        resolved = resolve_item(field_set, item_def["tags"])
        if resolved["tag"] is None and "derive" in item_def:
            d = item_def["derive"]
            resolved = derive_subtraction(field_set, d["minuend_tags"], d["subtrahend_tags"])
        # 非流動資産: 直接・差引きが両方 None → US-GAAP HTML コンポーネント積み上げ
        if item_def["label"] == "非流動資産" and resolved["current"] is None:
            resolved = resolve_aggregate(field_set, _USGAAP_HTML_NCA_COMPONENTS)
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

        field_set = parse_instant_fields(xbrl_dir)
        if _is_usgaap(field_set):
            field_set.update(parse_usgaap_html_bs_fields(xbrl_dir))
        items = resolve_bs(field_set)
        m = {label: r for label, r in items}
        ibd = resolve_ibd(field_set)

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
