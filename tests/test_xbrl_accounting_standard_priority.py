from pathlib import Path

from blue_ticker.analysis.cash_flow import extract_cash_flow
from blue_ticker.analysis.income_statement import extract_income_statement
from blue_ticker.analysis.sections import CashFlowSection, IncomeStatementSection, detect_accounting_standard


def _is_from_pp(pre_parsed: dict) -> IncomeStatementSection:
    return IncomeStatementSection.from_pre_parsed(pre_parsed, detect_accounting_standard(pre_parsed))


def _cf_from_pp(pre_parsed: dict) -> CashFlowSection:
    return CashFlowSection.from_pre_parsed(pre_parsed, detect_accounting_standard(pre_parsed))


def test_income_statement_prefers_ifrs_summary_over_jgaap_summary() -> None:
    result = extract_income_statement(_is_from_pp({
        "OperatingRevenuesIFRSKeyFinancialData": {
            "CurrentYearDuration": 5_825_161_000_000.0,
        },
        "NetSalesSummaryOfBusinessResults": {
            "CurrentYearDuration": 5_843_087_000_000.0,
        },
        "ProfitLossAttributableToOwnersOfParentIFRSSummaryOfBusinessResults": {
            "CurrentYearDuration": 416_050_000_000.0,
        },
        "NetIncomeLossSummaryOfBusinessResults": {
            "CurrentYearDuration": 422_818_000_000.0,
        },
    }))

    assert result["accounting_standard"] == "IFRS"
    assert result["sales"] == 5_825_161_000_000.0
    assert result["net_profit"] == 416_050_000_000.0


def test_income_statement_prefers_consolidated_revenue_ifrs_over_nonconsolidated_revenue() -> None:
    result = extract_income_statement(_is_from_pp({
        "RevenueIFRS": {
            "CurrentYearDuration": 9_783_370_000_000.0,
            "Prior1YearDuration": 9_728_716_000_000.0,
        },
        "Revenue": {
            "CurrentYearDuration_NonConsolidatedMember": 1_774_233_000_000.0,
            "Prior1YearDuration_NonConsolidatedMember": 1_756_937_000_000.0,
        },
    }))

    assert result["accounting_standard"] == "IFRS"
    assert result["sales"] == 9_783_370_000_000.0
    assert result["sales_prior"] == 9_728_716_000_000.0
    assert result.get("sales_label") == "売上収益"


def test_income_statement_reads_ifrs_revenue_summary_values() -> None:
    result = extract_income_statement(_is_from_pp({
        "RevenueIFRSSummaryOfBusinessResults": {
            "Prior1YearDuration": 1_091_195_000_000.0,
            "CurrentYearDuration": 1_150_209_000_000.0,
        },
        "BusinessProfitIFRSSummaryOfBusinessResults": {
            "CurrentYearDuration": 97_322_000_000.0,
        },
        "ProfitLossAttributableToOwnersOfParentIFRSSummaryOfBusinessResults": {
            "CurrentYearDuration": 60_741_000_000.0,
        },
    }))

    assert result["accounting_standard"] == "IFRS"
    assert result["sales"] == 1_150_209_000_000.0
    assert result["sales_prior"] == 1_091_195_000_000.0
    assert result.get("sales_label") == "売上収益"


def test_cash_flow_prefers_ifrs_summary_over_jgaap_summary() -> None:
    result = extract_cash_flow(_cf_from_pp({
        "CashFlowsFromUsedInOperatingActivitiesIFRSSummaryOfBusinessResults": {
            "CurrentYearDuration": 669_784_000_000.0,
        },
        "NetCashProvidedByUsedInOperatingActivitiesSummaryOfBusinessResults": {
            "CurrentYearDuration": 596_949_000_000.0,
        },
        "CashFlowsFromUsedInInvestingActivitiesIFRSSummaryOfBusinessResults": {
            "CurrentYearDuration": -475_605_000_000.0,
        },
        "NetCashProvidedByUsedInInvestingActivitiesSummaryOfBusinessResults": {
            "CurrentYearDuration": -419_630_000_000.0,
        },
    }))

    assert result["accounting_standard"] == "IFRS"
    assert result["cfo"]["current"] == 669_784_000_000.0
    assert result["cfi"]["current"] == -475_605_000_000.0


def test_income_statement_reads_usgaap_summary_values() -> None:
    result = extract_income_statement(_is_from_pp({
        "RevenuesUSGAAPSummaryOfBusinessResults": {
            "CurrentYearDuration": 3_195_828_000_000.0,
        },
        "NetIncomeLossAttributableToOwnersOfParentUSGAAPSummaryOfBusinessResults": {
            "CurrentYearDuration": 260_951_000_000.0,
        },
    }))

    assert result["accounting_standard"] == "US-GAAP"
    assert result["sales"] == 3_195_828_000_000.0
    assert result["net_profit"] == 260_951_000_000.0


def test_income_statement_reads_jgaap_operating_revenue_summary() -> None:
    result = extract_income_statement(_is_from_pp({
        "OperatingRevenue1SummaryOfBusinessResults": {
            "Prior1YearDuration": 26_512_000_000.0,
            "CurrentYearDuration": 27_840_000_000.0,
        },
        "OperatingIncome": {
            "CurrentYearDuration": 2_189_902_000.0,
        },
        "NetIncomeLossSummaryOfBusinessResults": {
            "CurrentYearDuration": 1_588_000_000.0,
        },
    }))

    assert result["accounting_standard"] == "J-GAAP"
    assert result["sales"] == 27_840_000_000.0
    assert result["sales_prior"] == 26_512_000_000.0
    assert result.get("sales_label") == "営業収益"
    assert result["operating_profit"] == 2_189_902_000.0
    assert result["net_profit"] == 1_588_000_000.0


def test_cash_flow_reads_usgaap_summary_values() -> None:
    result = extract_cash_flow(_cf_from_pp({
        "CashFlowsFromUsedInOperatingActivitiesUSGAAPSummaryOfBusinessResults": {
            "CurrentYearDuration": 428_162_000_000.0,
        },
        "CashFlowsFromUsedInInvestingActivitiesUSGAAPSummaryOfBusinessResults": {
            "CurrentYearDuration": -541_953_000_000.0,
        },
    }))

    assert result["accounting_standard"] == "US-GAAP"
    assert result["cfo"]["current"] == 428_162_000_000.0
    assert result["cfi"]["current"] == -541_953_000_000.0
