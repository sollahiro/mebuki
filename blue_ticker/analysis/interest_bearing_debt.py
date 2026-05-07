"""
有利子負債（IBD）XBRL抽出モジュール

XBRLインスタンス文書から有利子負債を構成要素ごとに抽出する。

有利子負債の定義:
  短期借入金
  + コマーシャル・ペーパー
  + 1年内償還予定の社債
  + 1年内返済予定の長期借入金
  + 社債
  + 長期借入金

タグ体系:
  J-GAAP: ShortTermLoansPayable, BondsPayable, LongTermLoansPayable, ...
  IFRS連結: BorrowingsCLIFRS, BondsPayableNCLIFRS, BorrowingsNCLIFRS, ...
  US-GAAP: HTML借入金ノートから解析（ibd_usgaap_html.py）

抽出戦略:
  1. 直接法: InterestBearingDebt タグを検索
  2. 積み上げ法: 各コンポーネントを個別に取得して合算
"""

from pathlib import Path

from blue_ticker.analysis.context_helpers import (
    _is_consolidated_instant,
    _is_consolidated_prior_instant,
    _is_nonconsolidated_instant,
    _is_nonconsolidated_prior_instant,
)
from blue_ticker.analysis.ibd_usgaap_html import _extract_usgaap_from_html
from blue_ticker.analysis.xbrl_utils import collect_numeric_elements, find_xbrl_files
from blue_ticker.utils.xbrl_result_types import InterestBearingDebtResult, MetricComponent, XbrlTagElements
from blue_ticker.constants.xbrl import (
    AGGREGATE_IFRS_DEFINITIONS,
    COMPONENT_DEFINITIONS,
    IFRS_BALANCE_SHEET_MARKER_TAGS,
    INTEREST_BEARING_DEBT_TAGS,
    USGAAP_MARKER_TAGS,
)

# XBRL解析で収集対象とするローカルタグ名のセット（不要要素のスキップに使用）
_IBD_RELEVANT_TAGS: frozenset[str] = frozenset(
    INTEREST_BEARING_DEBT_TAGS
    + [tag for comp in COMPONENT_DEFINITIONS for tag in comp["tags"]]
    + [agg["tag"] for agg in AGGREGATE_IFRS_DEFINITIONS]
    + USGAAP_MARKER_TAGS
    + IFRS_BALANCE_SHEET_MARKER_TAGS
)


def _safe_sum(vals: list[float | None]) -> float | None:
    vs = [v for v in vals if v is not None]
    return sum(vs) if vs else None



def _find_consolidated_value(tag_elements: XbrlTagElements, tag: str) -> tuple[float | None, float | None]:
    """指定タグの連結当期・前期値のみを返す（個別へのフォールバックなし）。"""
    if tag not in tag_elements:
        return None, None
    current = prior = None
    for ctx, val in tag_elements[tag].items():
        if _is_consolidated_instant(ctx):
            current = val
        elif _is_consolidated_prior_instant(ctx):
            prior = val
    return current, prior


def _find_nonconsolidated_value(tag_elements: XbrlTagElements, tag: str) -> tuple[float | None, float | None]:
    """指定タグの個別当期・前期値のみを返す。"""
    if tag not in tag_elements:
        return None, None
    current = prior = None
    for ctx, val in tag_elements[tag].items():
        if _is_nonconsolidated_instant(ctx):
            current = val
        elif _is_nonconsolidated_prior_instant(ctx):
            prior = val
    return current, prior


def _detect_accounting_standard(tag_elements: XbrlTagElements) -> str:
    """会計基準を判定: 'J-GAAP' | 'IFRS' | 'US-GAAP'"""
    if _is_usgaap_xbrl(tag_elements):
        return "US-GAAP"
    if any(t in tag_elements for t in IFRS_BALANCE_SHEET_MARKER_TAGS):
        return "IFRS"
    return "J-GAAP"


def _is_usgaap_xbrl(tag_elements: XbrlTagElements) -> bool:
    """XBRLインスタンスのタグ群がUS-GAAP企業かどうかを判定。"""
    has_usgaap = any(t in tag_elements for t in USGAAP_MARKER_TAGS)
    if not has_usgaap:
        return False

    # IFRSマーカータグが存在する場合は、*USGAAPSummaryOfBusinessResults タグが
    # 旧期間比較データとして残存しているだけ（IFRS移行後の企業）と判断する
    if any(t in tag_elements for t in IFRS_BALANCE_SHEET_MARKER_TAGS):
        return False

    debt_tags = [
        "ShortTermLoansPayable", "BorrowingsCLIFRS",
        "BondsPayable", "LongTermLoansPayable",
    ]
    for tag in debt_tags:
        c, _ = _find_consolidated_value(tag_elements, tag)
        if c is not None:
            return False
    return True


def extract_interest_bearing_debt(
    xbrl_dir: Path,
    *,
    pre_parsed: XbrlTagElements | None = None,
) -> InterestBearingDebtResult:
    """
    XBRLディレクトリから有利子負債を構成要素ごとに抽出する。

    Returns:
        {
            "current": float | None,      # 合計 当期末（円）
            "prior":   float | None,      # 合計 前期末（円）
            "method":  str,               # "direct" | "computed" | "usgaap_html" | "not_found"
            "reason":  str | None,        # not_found 時のみ失敗理由を格納、それ以外は None
            "accounting_standard": str,   # "J-GAAP" | "IFRS" | "US-GAAP"
            "components": [               # 各コンポーネント
                {
                    "label": str,
                    "tag":   str | None,
                    "current": float | None,
                    "prior":   float | None,
                }
            ]
        }
    """
    if pre_parsed is not None:
        tag_elements: XbrlTagElements = {tag: ctx for tag, ctx in pre_parsed.items() if tag in _IBD_RELEVANT_TAGS}
    else:
        tag_elements = {}
        for f in find_xbrl_files(xbrl_dir):
            for tag, ctx_map in collect_numeric_elements(f, allowed_tags=_IBD_RELEVANT_TAGS, nil_as_zero=True).items():
                if tag not in tag_elements:
                    tag_elements[tag] = {}
                tag_elements[tag].update(ctx_map)

    accounting_standard = _detect_accounting_standard(tag_elements)

    # US-GAAP 企業: HTML解析にフォールバック
    if accounting_standard == "US-GAAP":
        htm_files = list(xbrl_dir.rglob("*.htm")) + list(xbrl_dir.rglob("*.html"))
        for htm_file in htm_files:
            result = _extract_usgaap_from_html(htm_file)
            if result is not None:
                return result
        for htm_file in htm_files:
            content = htm_file.read_text(encoding="utf-8", errors="ignore")
            if "借入金等明細表" in content and "該当事項はありません" in content:
                usgaap_zero_comps: list[MetricComponent] = [{"label": d["label"], "tag": None, "current": 0.0, "prior": 0.0}
                                                           for d in COMPONENT_DEFINITIONS]
                return {"current": 0.0, "prior": 0.0, "method": "usgaap_zero", "accounting_standard": "US-GAAP", "components": usgaap_zero_comps}
        return {"current": None, "prior": None, "method": "not_found", "accounting_standard": "US-GAAP", "components": [],
                "reason": "US-GAAP 連結財務諸表注記 HTML (0105020) で借入金を取得できない"}

    # 直接法
    for ibd_tag in INTEREST_BEARING_DEBT_TAGS:
        current, prior = _find_consolidated_value(tag_elements, ibd_tag)
        if current is None and prior is None:
            current, prior = _find_nonconsolidated_value(tag_elements, ibd_tag)
        if current is not None or prior is not None:
            return {
                "current": current,
                "prior": prior,
                "method": "direct",
                "accounting_standard": accounting_standard,
                "components": [{"label": "有利子負債合計", "tag": ibd_tag,
                                "current": current, "prior": prior}],
            }

    # 積み上げ法（コンポーネント別）
    # Pass 1: 連結値のみ収集
    components: list[MetricComponent] = []
    for comp_def in COMPONENT_DEFINITIONS:
        found_tag = None
        current = prior = None
        for tag in comp_def["tags"]:
            # IFRS企業ではJ-GAAPタグ（IFRS識別子を含まないタグ）をスキップ
            if accounting_standard == "IFRS" and "IFRS" not in tag:
                continue
            c, p = _find_consolidated_value(tag_elements, tag)
            if c is not None or p is not None:
                found_tag = tag
                current, prior = c, p
                break
        components.append({
            "label": comp_def["label"],
            "tag": found_tag,
            "current": current,
            "prior": prior,
        })

    # 連結財務諸表が存在するか判定。
    # 1つでも連結値があれば連結財務諸表のみを使用し、単体値との混入を防ぐ。
    has_consolidated = any(c["current"] is not None or c["prior"] is not None for c in components)

    # IFRS企業では集約タグが連結財務諸表の存在を示すため、Pass 2への落下を防ぐ
    if not has_consolidated and accounting_standard == "IFRS":
        for agg_def in AGGREGATE_IFRS_DEFINITIONS:
            agg_c, agg_p = _find_consolidated_value(tag_elements, agg_def["tag"])
            if agg_c is not None or agg_p is not None:
                has_consolidated = True
                break

    # Pass 2: 連結値が全くない場合のみ単体にフォールバック（単体のみ企業への対応）
    if not has_consolidated:
        components: list[MetricComponent] = []
        for comp_def in COMPONENT_DEFINITIONS:
            found_tag = None
            current = prior = None
            for tag in comp_def["tags"]:
                c, p = _find_nonconsolidated_value(tag_elements, tag)
                if c is not None or p is not None:
                    found_tag = tag
                    current, prior = c, p
                    break
            components.append({
                "label": comp_def["label"],
                "tag": found_tag,
                "current": current,
                "prior": prior,
            })

    # 集約IFRSタグによる後処理
    for agg_def in AGGREGATE_IFRS_DEFINITIONS:
        agg_c, agg_p = _find_consolidated_value(tag_elements, agg_def["tag"])
        if agg_c is None and agg_p is None:
            continue
        covered = [c for c in components if c["label"] in agg_def["covers"]]
        needs_override = [
            c for c in covered
            if c["tag"] is None
            or _find_consolidated_value(tag_elements, c["tag"]) == (None, None)
        ]
        if not needs_override:
            continue
        for c in covered:
            c["current"] = None
            c["prior"] = None
            c["tag"] = None
        first = next(c for c in components if c["label"] == agg_def["covers"][0])
        first["tag"] = agg_def["tag"]
        first["current"] = agg_c
        first["prior"] = agg_p
        agg_label = agg_def.get("label") or (agg_def["covers"][0] + "＋" + agg_def["covers"][1] + "（集約）")
        first["label"] = agg_label

    found = [c for c in components if c["current"] is not None or c["prior"] is not None]
    if not found:
        xbrl_files = find_xbrl_files(xbrl_dir)
        if any(f.stat().st_size > 100_000 for f in xbrl_files):
            zero_comps: list[MetricComponent] = [{"label": comp["label"], "tag": None, "current": 0.0, "prior": 0.0} for comp in COMPONENT_DEFINITIONS]
            return {"current": 0.0, "prior": 0.0, "method": "zero_debt", "accounting_standard": accounting_standard, "components": zero_comps}
        return {"current": None, "prior": None, "method": "not_found", "accounting_standard": accounting_standard, "components": components,
                "reason": "有利子負債タグが見つからない"}

    total_current = _safe_sum([c["current"] for c in components])
    total_prior = _safe_sum([c["prior"] for c in components])

    return {
        "current": total_current,
        "prior": total_prior,
        "method": "computed",
        "accounting_standard": accounting_standard,
        "components": components,
    }
