"""
キャッシュフロー XBRL抽出モジュール

XBRLインスタンス文書から連結キャッシュフロー計算書の
営業CF・投資CFを抽出する。

タグ体系:
  J-GAAP:   NetCashProvidedByUsedInOperatingActivities / NetCashProvidedByUsedInInvestingActivities
  IFRS連結:  CashFlowsFromUsedInOperationsIFRS / CashFlowsUsedInInvestingActivitiesIFRS

コンテキスト:
  CF計算書はフロー項目なので Duration コンテキストを使用する。
"""

from blue_ticker.analysis.sections import CashFlowSection
from blue_ticker.constants.xbrl import (
    CF_INVESTING_TAGS,
    CF_OPERATING_TAGS,
)
from blue_ticker.utils.xbrl_result_types import CashFlowResult


def extract_cash_flow(section: CashFlowSection) -> CashFlowResult:
    """
    CF計算書セクションから営業CF・投資CFを抽出する。

    年次報告書では当期 = FY の値、2Q 報告書では当期 = H1（上半期累計）の値。

    Returns:
        {
            "cfo": {"current": float | None, "prior": float | None},
            "cfi": {"current": float | None, "prior": float | None},
            "accounting_standard": str,   # "J-GAAP" | "IFRS" | "US-GAAP"
        }
    """
    cfo_item = section.resolve(CF_OPERATING_TAGS)
    cfi_item = section.resolve(CF_INVESTING_TAGS)

    return {
        "cfo": {"current": cfo_item["current"], "prior": cfo_item["prior"]},
        "cfi": {"current": cfi_item["current"], "prior": cfi_item["prior"]},
        "accounting_standard": section.accounting_standard,
    }
