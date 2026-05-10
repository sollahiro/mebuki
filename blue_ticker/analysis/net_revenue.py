"""
IFRS純収益・事業利益 XBRL抽出モジュール

IFRS適用の金融会社（クレディセゾン等）で売上高・営業利益タグが
空になる場合に、XBRL から純収益（NetRevenueIFRS）と事業利益
（BusinessProfitIFRSSummaryOfBusinessResults）を抽出してフォールバックに使う。
"""

from blue_ticker.analysis.sections import IncomeStatementSection
from blue_ticker.utils.xbrl_result_types import NetRevenueResult


def extract_net_revenue(section: IncomeStatementSection) -> NetRevenueResult:
    """
    損益計算書セクションから IFRS 純収益と事業利益を抽出する。

    Returns:
        {
            "net_revenue":           float | None,  # 純収益・当期（円）
            "net_revenue_prior":     float | None,  # 純収益・前期（円）
            "business_profit":       float | None,  # 事業利益・当期（円）
            "business_profit_prior": float | None,  # 事業利益・前期（円）
            "found": bool,
        }
    """
    nr_item = section.resolve(["NetRevenueIFRS"])
    bp_item = section.resolve(["BusinessProfitIFRSSummaryOfBusinessResults"])

    return {
        "net_revenue": nr_item["current"],
        "net_revenue_prior": nr_item["prior"],
        "business_profit": bp_item["current"],
        "business_profit_prior": bp_item["prior"],
        "found": nr_item["current"] is not None or bp_item["current"] is not None,
    }
