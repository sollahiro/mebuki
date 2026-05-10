"""
有利子負債（IBD）XBRL抽出モジュール

BalanceSheetSection（FieldSet を内包）からの3ステージ抽出:
  Stage 1: XBRL XML → FieldSet  (Section 構築時に実施)
  Stage 2: HTML 補完            (Section 構築時に US-GAAP 企業のみ実施)
  Stage 3: FieldSet → IBD値     (resolve_ibd: 直接法 → IFRS集約 → コンポーネント積み上げ → HTML仮想タグ)

有利子負債の定義:
  短期借入金 + CP + 短期社債 + 1年内社債 + 1年内長期借入金 + 社債 + 長期借入金
"""

from blue_ticker.analysis.field_parser import ResolvedItem
from blue_ticker.analysis.sections import BalanceSheetSection
from blue_ticker.analysis.xbrl_utils import find_xbrl_files
from blue_ticker.constants.xbrl import (
    COMPONENT_DEFINITIONS,
    IBD_CURRENT_COMPONENTS,
    IBD_IFRS_CL_TAGS,
    IBD_IFRS_NCL_TAGS,
    IBD_NON_CURRENT_COMPONENTS,
)
from blue_ticker.utils.xbrl_result_types import InterestBearingDebtResult, MetricComponent

# XBRL タグ名 → 人間可読ラベル（コンポーネント表示・テスト互換性のため）
_TAG_TO_LABEL: dict[str, str] = {
    tag: comp["label"]
    for comp in COMPONENT_DEFINITIONS
    for tag in comp["tags"]
}


def resolve_ibd(section: BalanceSheetSection) -> ResolvedItem:
    """貸借対照表セクションから有利子負債を解決する。

    解決順: 直接法 → IFRS集約タグ → コンポーネント積み上げ → US-GAAP HTML仮想タグ。
    scripts から直接呼び出すことを想定して公開関数とする。
    """
    direct = section.resolve(["InterestBearingDebt", "InterestBearingLiabilities"])
    if direct["tag"]:
        return direct

    ifrs_agg = section.resolve_aggregate([IBD_IFRS_CL_TAGS, IBD_IFRS_NCL_TAGS])
    if ifrs_agg["tag"]:
        return ifrs_agg

    comp = section.resolve_aggregate(IBD_CURRENT_COMPONENTS + IBD_NON_CURRENT_COMPONENTS)
    if comp["tag"]:
        return comp

    return section.resolve_aggregate([["USGAAP_HTML_IBDCurrent"], ["USGAAP_HTML_IBDNonCurrent"]])


def extract_interest_bearing_debt(section: BalanceSheetSection) -> InterestBearingDebtResult:
    """貸借対照表セクションから有利子負債を構成要素ごとに抽出する。"""
    accounting_standard = section.accounting_standard

    resolved = resolve_ibd(section)
    tag, current, prior = resolved["tag"], resolved["current"], resolved["prior"]

    if tag is None:
        if section.xbrl_dir is not None:
            xbrl_files = find_xbrl_files(section.xbrl_dir)
            if any(f.stat().st_size > 100_000 for f in xbrl_files):
                return {
                    "current": 0.0,
                    "prior": 0.0,
                    "method": "zero_debt",
                    "accounting_standard": accounting_standard,
                    "components": [],
                }
        return {
            "current": None,
            "prior": None,
            "method": "not_found",
            "accounting_standard": accounting_standard,
            "components": [],
            "reason": "有利子負債タグが見つからない",
        }

    components: list[MetricComponent] = [
        {
            "label": _TAG_TO_LABEL.get(t, t),
            "tag": t,
            "current": section.field_value(t)["current"] if section.field_value(t) is not None else None,
            "prior": section.field_value(t)["prior"] if section.field_value(t) is not None else None,
        }
        for t in (tag.split("+") if tag else [])
    ]

    return {
        "current": current,
        "prior": prior,
        "method": "field_parser",
        "accounting_standard": accounting_standard,
        "components": components,
    }
