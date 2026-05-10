"""
単体のみ企業と連結企業の非連結フォールバック制御テスト。

単体のみ企業（_NonConsolidatedMember コンテキストを持たない）:
  → plain context の値を返す（従来通り）

連結企業（_NonConsolidatedMember コンテキストを持つ）:
  → 連結タグが見つからなくても単体へフォールバックしない（None を返す）
"""

import tempfile
from pathlib import Path

import pytest

from blue_ticker.analysis.balance_sheet import extract_balance_sheet
from blue_ticker.analysis.cash_flow import extract_cash_flow
from blue_ticker.analysis.income_statement import extract_income_statement
from blue_ticker.analysis.sections import (
    BalanceSheetSection,
    CashFlowSection,
    IncomeStatementSection,
    detect_accounting_standard,
)


def _is_from_pp(pre_parsed: dict) -> IncomeStatementSection:
    return IncomeStatementSection.from_pre_parsed(pre_parsed, detect_accounting_standard(pre_parsed))


def _cf_from_pp(pre_parsed: dict) -> CashFlowSection:
    return CashFlowSection.from_pre_parsed(pre_parsed, detect_accounting_standard(pre_parsed))


def _bs_from_pp(pre_parsed: dict, xbrl_dir: Path = Path(".")) -> BalanceSheetSection:
    return BalanceSheetSection.from_pre_parsed(pre_parsed, detect_accounting_standard(pre_parsed), xbrl_dir)


# ──────────────────────────────────────────────────────────────────────────────
# 単体のみ企業: plain context（_NonConsolidatedMember なし）を使う
# ──────────────────────────────────────────────────────────────────────────────

def test_income_statement_single_entity_uses_plain_context() -> None:
    """単体のみ企業は plain context のデータを返す。"""
    result = extract_income_statement(_is_from_pp({
        "NetSalesSummaryOfBusinessResults": {
            "CurrentYearDuration": 4_547_599_000.0,
        },
        "OperatingIncomeLoss": {
            "CurrentYearDuration": -120_634_000.0,
        },
        "NetIncomeLossSummaryOfBusinessResults": {
            "CurrentYearDuration": 17_478_000.0,
        },
    }))

    assert result["sales"] == pytest.approx(4_547_599_000.0)
    assert result["operating_profit"] == pytest.approx(-120_634_000.0)
    assert result["net_profit"] == pytest.approx(17_478_000.0)


def test_cash_flow_single_entity_uses_plain_context() -> None:
    """単体のみ企業は plain context のCF値を返す。"""
    result = extract_cash_flow(_cf_from_pp({
        "NetCashProvidedByUsedInOperatingActivities": {
            "CurrentYearDuration": -482_098_000.0,
        },
        "NetCashProvidedByUsedInInvestmentActivities": {
            "CurrentYearDuration": -306_697_000.0,
        },
    }))

    assert result["cfo"]["current"] == pytest.approx(-482_098_000.0)
    assert result["cfi"]["current"] == pytest.approx(-306_697_000.0)


def test_balance_sheet_single_entity_uses_plain_context() -> None:
    """単体のみ企業は plain context のBS値を返す。"""
    result = extract_balance_sheet(_bs_from_pp({
        "NetAssets": {
            "CurrentYearInstant": 4_521_695_000.0,
        },
        "TotalAssetsSummaryOfBusinessResults": {
            "CurrentYearInstant": 6_705_070_000.0,
        },
    }))

    assert result["total_assets"] == pytest.approx(6_705_070_000.0)
    assert result["net_assets"] == pytest.approx(4_521_695_000.0)


# ──────────────────────────────────────────────────────────────────────────────
# 連結企業: 連結タグが見つからなくても単体へフォールバックしない
# ──────────────────────────────────────────────────────────────────────────────

def _consolidated_company_base() -> dict:
    """連結グループあり企業の最小限 pre_parsed ベース。

    実際の連結有報では同一財務タグに「純粋な連結コンテキスト」と
    「_NonConsolidatedMember コンテキスト」の両方が存在する。
    ここでは ProfitLossAttributableToOwnersOfParent を使う。
    income_statement / balance_sheet / cash_flow のどのテストとも干渉しない
    （income_statement が net_profit を見つけるが、各テストは sales / cfo / assets を検証）。
    """
    return {
        "ProfitLossAttributableToOwnersOfParent": {
            "CurrentYearDuration": 800_000_000.0,                       # 連結純利益（シグナル）
            "CurrentYearDuration_NonConsolidatedMember": 600_000_000.0, # 個別純利益
        },
    }


def test_income_statement_consolidated_company_blocks_nonconsolidated_fallback() -> None:
    """連結企業で連結値がなければ None を返す（単体値を混入しない）。"""
    pre_parsed = _consolidated_company_base()
    pre_parsed["NetSalesSummaryOfBusinessResults"] = {
        "CurrentYearDuration_NonConsolidatedMember": 4_547_599_000.0,
    }
    result = extract_income_statement(_is_from_pp(pre_parsed))

    assert result["sales"] is None


def test_cash_flow_consolidated_company_blocks_nonconsolidated_fallback() -> None:
    """連結企業でCF連結値がなければ None を返す（単体値を混入しない）。"""
    pre_parsed = _consolidated_company_base()
    pre_parsed["NetCashProvidedByUsedInOperatingActivities"] = {
        "CurrentYearDuration_NonConsolidatedMember": -482_098_000.0,
    }
    result = extract_cash_flow(_cf_from_pp(pre_parsed))

    assert result["cfo"]["current"] is None
    assert result["cfi"]["current"] is None


def test_balance_sheet_consolidated_company_blocks_nonconsolidated_fallback() -> None:
    """連結企業でBS連結値がなければ None を返す（単体値を混入しない）。"""
    pre_parsed = _consolidated_company_base()
    pre_parsed["NetAssets"] = {
        "CurrentYearInstant_NonConsolidatedMember": 4_521_695_000.0,
    }
    pre_parsed["TotalAssets"] = {
        "CurrentYearInstant_NonConsolidatedMember": 6_705_070_000.0,
    }
    # 空ディレクトリを渡すことで HTML フォールバックが実ファイルを走査しないようにする
    with tempfile.TemporaryDirectory() as tmp:
        result = extract_balance_sheet(_bs_from_pp(pre_parsed, Path(tmp)))

    assert result["net_assets"] is None
    assert result["total_assets"] is None
