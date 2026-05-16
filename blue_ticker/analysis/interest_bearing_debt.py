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
from blue_ticker.analysis.xbrl_utils import extract_ifrs_textblock_table, find_xbrl_files
from blue_ticker.constants.financial import MILLION_YEN
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

_IFRS_BS_TEXTBLOCK_TAG = "ConsolidatedStatementOfFinancialPositionIFRSTextBlock"

# IFRS連結財政状態計算書 TextBlock から集計する有利子負債コンポーネント定義
# (HTMLラベル, 表示ラベル) のリスト。HTMLの表示順（流動→非流動）で定義する。
_IFRS_TEXTBLOCK_IBD_LABELS: list[tuple[str, str]] = [
    ("短期借入金",               "短期借入金"),
    ("コマーシャル・ペーパー",   "コマーシャル・ペーパー"),
    ("１年内償還予定の社債",     "1年内償還予定の社債"),
    ("１年内返済予定の長期借入金", "1年内返済予定の長期借入金"),
    ("社債",                    "社債"),
    ("長期借入金",               "長期借入金"),
]


def _extract_ifrs_ibd_from_textblock(section: BalanceSheetSection) -> InterestBearingDebtResult | None:
    """IFRS連結財政状態計算書TextBlockから有利子負債を積み上げ抽出する。"""
    if section.xbrl_dir is None:
        return None
    table = extract_ifrs_textblock_table(section.xbrl_dir, _IFRS_BS_TEXTBLOCK_TAG)
    if not table:
        return None

    components: list[MetricComponent] = []
    current_total = prior_total = 0.0
    has_current = has_prior = False

    for html_label, display_label in _IFRS_TEXTBLOCK_IBD_LABELS:
        vals = table.get(html_label)
        if vals is None:
            continue
        c_m, p_m = vals
        c_yen = c_m * MILLION_YEN if c_m is not None else None
        p_yen = p_m * MILLION_YEN if p_m is not None else None
        if c_m is not None:
            current_total += c_m
            has_current = True
        if p_m is not None:
            prior_total += p_m
            has_prior = True
        components.append({
            "label": display_label,
            "tag": f"IFRS_HTML_{html_label}",
            "current": c_yen,
            "prior": p_yen,
        })

    if not has_current and not has_prior:
        return None

    return {
        "current": current_total * MILLION_YEN if has_current else None,
        "prior": prior_total * MILLION_YEN if has_prior else None,
        "method": "ifrs_textblock",
        "accounting_standard": "IFRS",
        "components": components,
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
        # IFRS Summary型XBRLでは連結借入金タグが存在しないため、TextBlockから抽出する。
        if accounting_standard == "IFRS":
            textblock_result = _extract_ifrs_ibd_from_textblock(section)
            if textblock_result is not None:
                return textblock_result
            # TextBlock失敗時は全会計基準共通のzero_debtフォールバックへ続行する
        # 全会計基準共通: XBRLファイルが大きければ無借金と判断する
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

    def _component(t: str) -> MetricComponent:
        fv = section.field_value(t)
        return {
            "label": _TAG_TO_LABEL.get(t, t),
            "tag": t,
            "current": fv["current"] if fv is not None else None,
            "prior": fv["prior"] if fv is not None else None,
        }

    components: list[MetricComponent] = [_component(t) for t in (tag.split("+") if tag else [])]

    return {
        "current": current,
        "prior": prior,
        "method": "field_parser",
        "accounting_standard": accounting_standard,
        "components": components,
    }
