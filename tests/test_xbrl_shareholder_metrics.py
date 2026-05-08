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
