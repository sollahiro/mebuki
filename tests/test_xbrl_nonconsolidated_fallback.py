from pathlib import Path

import pytest

from blue_ticker.analysis.balance_sheet import extract_balance_sheet
from blue_ticker.analysis.cash_flow import extract_cash_flow
from blue_ticker.analysis.income_statement import extract_income_statement


def test_income_statement_falls_back_to_pure_nonconsolidated_summary_context() -> None:
    result = extract_income_statement(
        Path("."),
        pre_parsed={
            "NetSalesSummaryOfBusinessResults": {
                "CurrentYearDuration_NonConsolidatedMember": 4_547_599_000.0,
            },
            "OperatingIncomeLoss": {
                "CurrentYearDuration_NonConsolidatedMember": -120_634_000.0,
            },
            "NetIncomeLossSummaryOfBusinessResults": {
                "CurrentYearDuration_NonConsolidatedMember": 17_478_000.0,
            },
        },
    )

    assert result["sales"] == pytest.approx(4_547_599_000.0)
    assert result["operating_profit"] == pytest.approx(-120_634_000.0)
    assert result["net_profit"] == pytest.approx(17_478_000.0)


def test_cash_flow_falls_back_to_nonconsolidated_contexts() -> None:
    result = extract_cash_flow(
        Path("."),
        pre_parsed={
            "NetCashProvidedByUsedInOperatingActivities": {
                "CurrentYearDuration_NonConsolidatedMember": -482_098_000.0,
            },
            "NetCashProvidedByUsedInInvestmentActivities": {
                "CurrentYearDuration_NonConsolidatedMember": -306_697_000.0,
            },
        },
    )

    assert result["cfo"]["current"] == pytest.approx(-482_098_000.0)
    assert result["cfi"]["current"] == pytest.approx(-306_697_000.0)


def test_balance_sheet_prefers_pure_nonconsolidated_net_assets_context() -> None:
    result = extract_balance_sheet(
        Path("."),
        pre_parsed={
            "NetAssets": {
                "CurrentYearInstant_NonConsolidatedMember": 4_521_695_000.0,
                "CurrentYearInstant_NonConsolidatedMember_ShareholdersEquityMember": 4_407_039_000.0,
                "CurrentYearInstant_NonConsolidatedMember_ValuationAndTranslationAdjustmentsMember": 114_656_000.0,
            },
            "TotalAssetsSummaryOfBusinessResults": {
                "CurrentYearInstant_NonConsolidatedMember": 6_705_070_000.0,
            },
        },
    )

    assert result["total_assets"] == pytest.approx(6_705_070_000.0)
    assert result["net_assets"] == pytest.approx(4_521_695_000.0)
