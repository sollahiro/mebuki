from pathlib import Path

from blue_ticker.analysis.shareholder_metrics import extract_shareholder_metrics


def test_extract_shareholder_metrics_from_ifrs_summary() -> None:
    result = extract_shareholder_metrics(
        Path("."),
        pre_parsed={
            "CashAndCashEquivalentsIFRS": {
                "CurrentYearInstant": 276_959_000_000.0,
            },
            "BasicEarningsLossPerShareIFRS": {
                "CurrentYearDuration": 163.44,
            },
            "EquityToAssetRatioIFRSSummaryOfBusinessResults": {
                "CurrentYearInstant": 0.42,
            },
            "EquityAttributableToOwnersOfParentPerShareIFRSSummaryOfBusinessResults": {
                "CurrentYearInstant": 2306.8,
            },
            "NumberOfIssuedSharesAsOfFiscalYearEndIssuedSharesTotalNumberOfSharesEtc": {
                "FilingDateInstant": 1_138_716_846.0,
            },
            "DividendPaidPerShareSummaryOfBusinessResults": {
                "CurrentYearDuration_NonConsolidatedMember": 50.0,
            },
            "PayoutRatioSummaryOfBusinessResults": {
                "CurrentYearDuration_NonConsolidatedMember": 0.507,
            },
            "InterimDividendPaidPerShareSummaryOfBusinessResults": {
                "CurrentYearDuration_NonConsolidatedMember": 25.0,
            },
            "TotalAmountOfDividendsDividendsOfSurplus": {
                "FilingDateInstant_Row1Member": 28_460_000_000.0,
                "FilingDateInstant_Row2Member": 28_460_000_000.0,
            },
        },
        net_profit=186_687_000_000.0,
    )

    assert result["CashEq"] == 276_959_000_000.0
    assert result["EPS"] == 163.44
    assert result["BPS"] == 2306.8
    assert result["ShOutFY"] == 1_138_716_846.0
    assert result["DivAnn"] == 50.0
    assert result["Div2Q"] == 25.0
    assert result["DivTotalAnn"] == 56_920_000_000.0
    assert result["PayoutRatioAnn"] == 0.507


def test_extract_shareholder_metrics_prefers_consolidated_per_share_values() -> None:
    result = extract_shareholder_metrics(
        Path("."),
        pre_parsed={
            "BasicEarningsLossPerShareIFRSSummaryOfBusinessResults": {
                "CurrentYearDuration": 69.77,
            },
            "BasicEarningsLossPerShareSummaryOfBusinessResults": {
                "CurrentYearDuration_NonConsolidatedMember": 89.44,
            },
            "EquityToAssetRatioIFRSSummaryOfBusinessResults": {
                "CurrentYearInstant": 751.01,
            },
            "NetAssetsPerShareSummaryOfBusinessResults": {
                "CurrentYearInstant_NonConsolidatedMember": 362.64,
            },
        },
    )

    assert result["EPS"] == 69.77
    assert result["BPS"] == 751.01


def test_extract_shareholder_metrics_prefers_consolidated_cash_equivalents() -> None:
    result = extract_shareholder_metrics(
        Path("."),
        pre_parsed={
            "CashAndCashEquivalentsIFRSSummaryOfBusinessResults": {
                "CurrentYearInstant": 100.0,
                "CurrentYearInstant_NonConsolidatedMember": 10.0,
            },
        },
    )

    assert result["CashEq"] == 100.0


def test_extract_shareholder_metrics_prefers_explicit_bps_tag_over_ratio_named_tag() -> None:
    result = extract_shareholder_metrics(
        Path("."),
        pre_parsed={
            "EquityAttributableToOwnersOfParentPerShareIFRSSummaryOfBusinessResults": {
                "CurrentYearInstant": 2306.8,
            },
            "EquityToAssetRatioIFRSSummaryOfBusinessResults": {
                "CurrentYearInstant": 751.01,
            },
        },
    )

    assert result["BPS"] == 2306.8


def test_extract_shareholder_metrics_falls_back_to_non_consolidated_when_needed() -> None:
    result = extract_shareholder_metrics(
        Path("."),
        pre_parsed={
            "BasicEarningsLossPerShareSummaryOfBusinessResults": {
                "CurrentYearDuration_NonConsolidatedMember": 89.44,
            },
            "NetAssetsPerShareSummaryOfBusinessResults": {
                "CurrentYearInstant_NonConsolidatedMember": 362.64,
            },
        },
    )

    assert result["EPS"] == 89.44
    assert result["BPS"] == 362.64


def test_extract_shareholder_metrics_ignores_ratio_like_bps_values() -> None:
    result = extract_shareholder_metrics(
        Path("."),
        pre_parsed={
            "EquityToAssetRatioIFRSSummaryOfBusinessResults": {
                "CurrentYearInstant": 0.42,
            },
            "NetAssetsPerShareSummaryOfBusinessResults": {
                "CurrentYearInstant_NonConsolidatedMember": 500.0,
            },
        },
    )

    assert result["BPS"] == 500.0


def test_extract_shareholder_metrics_derives_payout_ratio_when_direct_tag_missing() -> None:
    result = extract_shareholder_metrics(
        Path("."),
        pre_parsed={
            "BasicEarningsLossPerShareIFRS": {
                "CurrentYearDuration": 163.44,
            },
            "DividendPaidPerShareSummaryOfBusinessResults": {
                "CurrentYearDuration_NonConsolidatedMember": 50.0,
            },
        },
    )

    assert result["PayoutRatioAnn"] == 0.306


def test_extract_shareholder_metrics_calculates_eps_bps_for_verification() -> None:
    result = extract_shareholder_metrics(
        Path("."),
        pre_parsed={
            "BasicEarningsLossPerShareIFRS": {
                "CurrentYearDuration": 18.25,
            },
            "EquityAttributableToOwnersOfParentPerShareIFRSSummaryOfBusinessResults": {
                "CurrentYearInstant": 98.0,
            },
            "AverageNumberOfSharesDuringPeriodBasicEarningsLossPerShareInformation": {
                "CurrentYearDuration": 100.0,
            },
            "EquityAttributableToOwnersOfParentIFRS": {
                "CurrentYearInstant": 10_000.0,
            },
            "NumberOfIssuedSharesAsOfFiscalYearEndIssuedSharesTotalNumberOfSharesEtc": {
                "FilingDateInstant": 110.0,
            },
            "TotalNumberOfSharesHeldTreasurySharesEtc": {
                "CurrentYearInstant_Row1Member": 10.0,
            },
        },
        net_profit=2_000.0,
    )

    assert result["AverageShares"] == 100.0
    assert result["TreasuryShares"] == 10.0
    assert result["SharesForBPS"] == 100.0
    assert result["ParentEquity"] == 10_000.0
    assert result["CalculatedEPS"] == 20.0
    assert result["CalculatedBPS"] == 100.0
    assert result["EPSDirectDiff"] == -1.75
    assert result["BPSDirectDiff"] == -2.0


def test_extract_shareholder_metrics_does_not_calculate_bps_without_treasury_shares() -> None:
    result = extract_shareholder_metrics(
        Path("."),
        pre_parsed={
            "EquityAttributableToOwnersOfParentIFRS": {
                "CurrentYearInstant": 10_000.0,
            },
            "NumberOfIssuedSharesAsOfFiscalYearEndIssuedSharesTotalNumberOfSharesEtc": {
                "FilingDateInstant": 110.0,
            },
        },
    )

    assert result["TreasuryShares"] is None
    assert result["SharesForBPS"] is None
    assert result["CalculatedBPS"] is None
