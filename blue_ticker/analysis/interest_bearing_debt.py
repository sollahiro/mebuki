"""
有利子負債（IBD）XBRL抽出モジュール

field_parser ベースの3ステージパイプライン:
  Stage 1: XBRL XML → FieldSet  (parse_instant_fields / field_set_from_pre_parsed)
  Stage 2: HTML 補完            (parse_usgaap_html_bs_fields — US-GAAP 企業のみ)
  Stage 3: FieldSet → IBD値     (resolve_ibd: 直接法 → IFRS集約 → コンポーネント積み上げ → HTML仮想タグ)

有利子負債の定義:
  短期借入金 + CP + 短期社債 + 1年内社債 + 1年内長期借入金 + 社債 + 長期借入金
"""

from pathlib import Path

from blue_ticker.analysis.field_parser import (
    FieldSet,
    ResolvedItem,
    field_set_from_pre_parsed,
    parse_instant_fields,
    parse_usgaap_html_bs_fields,
    resolve_aggregate,
    resolve_item,
)
from blue_ticker.analysis.xbrl_utils import find_xbrl_files
from blue_ticker.constants.xbrl import (
    COMPONENT_DEFINITIONS,
    IBD_CURRENT_COMPONENTS,
    IBD_IFRS_CL_TAGS,
    IBD_IFRS_NCL_TAGS,
    IBD_NON_CURRENT_COMPONENTS,
)

# XBRL タグ名 → 人間可読ラベル（コンポーネント表示・テスト互換性のため）
_TAG_TO_LABEL: dict[str, str] = {
    tag: comp["label"]
    for comp in COMPONENT_DEFINITIONS
    for tag in comp["tags"]
}
from blue_ticker.utils.xbrl_result_types import InterestBearingDebtResult, MetricComponent, XbrlTagElements


def _detect_accounting_standard(field_set: FieldSet) -> str:
    has_usgaap = any("USGAAP" in tag for tag in field_set)
    has_ifrs = any("IFRS" in tag for tag in field_set)
    if has_usgaap and not has_ifrs:
        return "US-GAAP"
    if has_ifrs:
        return "IFRS"
    return "J-GAAP"


def _build_field_set(xbrl_dir: Path, pre_parsed: XbrlTagElements | None) -> FieldSet:
    field_set = (
        field_set_from_pre_parsed(pre_parsed)
        if pre_parsed is not None
        else parse_instant_fields(xbrl_dir)
    )
    if any("USGAAP" in tag for tag in field_set):
        field_set.update(parse_usgaap_html_bs_fields(xbrl_dir))
    return field_set


def resolve_ibd(field_set: FieldSet) -> ResolvedItem:
    """FieldSet から有利子負債を解決する。

    解決順: 直接法 → IFRS集約タグ → コンポーネント積み上げ → US-GAAP HTML仮想タグ。
    scripts から直接呼び出すことを想定して公開関数とする。
    """
    direct = resolve_item(field_set, ["InterestBearingDebt", "InterestBearingLiabilities"])
    if direct["tag"]:
        return direct

    ifrs_agg = resolve_aggregate(field_set, [IBD_IFRS_CL_TAGS, IBD_IFRS_NCL_TAGS])
    if ifrs_agg["tag"]:
        return ifrs_agg

    comp = resolve_aggregate(field_set, IBD_CURRENT_COMPONENTS + IBD_NON_CURRENT_COMPONENTS)
    if comp["tag"]:
        return comp

    return resolve_aggregate(field_set, [["USGAAP_HTML_IBDCurrent"], ["USGAAP_HTML_IBDNonCurrent"]])


def extract_interest_bearing_debt(
    xbrl_dir: Path,
    *,
    pre_parsed: XbrlTagElements | None = None,
) -> InterestBearingDebtResult:
    """XBRLディレクトリから有利子負債を構成要素ごとに抽出する。"""
    field_set = _build_field_set(xbrl_dir, pre_parsed)
    accounting_standard = _detect_accounting_standard(field_set)

    resolved = resolve_ibd(field_set)
    tag, current, prior = resolved["tag"], resolved["current"], resolved["prior"]

    if tag is None:
        xbrl_files = find_xbrl_files(xbrl_dir)
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
            "current": field_set[t]["current"] if t in field_set else None,
            "prior": field_set[t]["prior"] if t in field_set else None,
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
