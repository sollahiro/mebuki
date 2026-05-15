"""
有形固定資産（PPE）XBRL抽出モジュール

BalanceSheetSection（FieldSet を内包）から帳簿価額を抽出する。

抽出項目:
  建物及び構築物 / 土地 / 機械装置及び運搬具 / 工具器具及び備品 / 建設仮勘定 / 合計
  その他 = 合計 − 抽出5項目の合計

帳簿価額の取得方法（優先順）:
  1. 直接タグ（*IFRS / *Net サフィックス）
  2. 取得原価タグ − 累計減価償却・減損タグ（直接タグが存在しない場合のフォールバック）

会計基準別タグ優先順:
  IFRS  : *IFRS サフィックス付きタグ（帳簿価額）
  J-GAAP: *Net サフィックス付きタグ（帳簿価額）。土地・建設仮勘定は Net なし
  US-GAAP: 合計のみ（個別内訳はタグ不足のため None）
"""

from blue_ticker.analysis.sections import BalanceSheetSection
from blue_ticker.constants.xbrl import (
    PPE_BUILDINGS_COST_TAGS,
    PPE_BUILDINGS_DEP_TAGS,
    PPE_BUILDINGS_TAGS,
    PPE_CONSTRUCTION_COST_TAGS,
    PPE_CONSTRUCTION_DEP_TAGS,
    PPE_CONSTRUCTION_TAGS,
    PPE_LAND_COST_TAGS,
    PPE_LAND_DEP_TAGS,
    PPE_LAND_TAGS,
    PPE_MACHINERY_COST_TAGS,
    PPE_MACHINERY_DEP_TAGS,
    PPE_MACHINERY_TAGS,
    PPE_TOOLS_TAGS,
    PPE_TOTAL_COST_TAGS,
    PPE_TOTAL_DEP_TAGS,
    PPE_TOTAL_TAGS,
)
from blue_ticker.utils.xbrl_result_types import TangibleFixedAssetsResult


def _net_value(
    section: BalanceSheetSection,
    cost_tags: list[str],
    dep_tags: list[str],
) -> float | None:
    """取得原価タグと累計減価償却・減損タグから帳簿価額を計算する。"""
    cost = section.resolve(cost_tags)["current"]
    if cost is None:
        return None
    dep = section.resolve(dep_tags)["current"]
    return cost + (dep if dep is not None else 0.0)


def extract_tangible_fixed_assets(section: BalanceSheetSection) -> TangibleFixedAssetsResult:
    """貸借対照表セクションから有形固定資産の帳簿価額を抽出する。"""
    accounting_standard = section.accounting_standard

    total = section.resolve(PPE_TOTAL_TAGS)["current"]
    if total is None:
        total = _net_value(section, PPE_TOTAL_COST_TAGS, PPE_TOTAL_DEP_TAGS)
    if total is None:
        return {
            "buildings": None,
            "land": None,
            "machinery": None,
            "tools": None,
            "construction_in_progress": None,
            "others": None,
            "total": None,
            "method": "not_found",
            "accounting_standard": accounting_standard,
            "reason": "有形固定資産タグが見つからない",
        }

    buildings = section.resolve(PPE_BUILDINGS_TAGS)["current"]
    if buildings is None:
        buildings = _net_value(section, PPE_BUILDINGS_COST_TAGS, PPE_BUILDINGS_DEP_TAGS)

    land = section.resolve(PPE_LAND_TAGS)["current"]
    if land is None:
        land = _net_value(section, PPE_LAND_COST_TAGS, PPE_LAND_DEP_TAGS)

    machinery = section.resolve(PPE_MACHINERY_TAGS)["current"]
    if machinery is None:
        machinery = _net_value(section, PPE_MACHINERY_COST_TAGS, PPE_MACHINERY_DEP_TAGS)

    tools = section.resolve(PPE_TOOLS_TAGS)["current"]

    construction = section.resolve(PPE_CONSTRUCTION_TAGS)["current"]
    if construction is None:
        construction = _net_value(section, PPE_CONSTRUCTION_COST_TAGS, PPE_CONSTRUCTION_DEP_TAGS)

    known_sum = sum(v for v in (buildings, land, machinery, tools, construction) if v is not None)
    others: float | None = total - known_sum

    return {
        "buildings": buildings,
        "land": land,
        "machinery": machinery,
        "tools": tools,
        "construction_in_progress": construction,
        "others": others,
        "total": total,
        "method": "field_parser",
        "accounting_standard": accounting_standard,
    }
