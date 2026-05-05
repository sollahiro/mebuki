import pytest

from mebuki.utils.operating_profit_change import (
    apply_operating_profit_change_from_xbrl,
    apply_operating_profit_change_to_periods,
    apply_operating_profit_change_to_years,
)


def _year(fy_end: str, sales: float, gross_profit: float, op: float) -> dict:
    return {
        "fy_end": fy_end,
        "FinancialPeriod": fy_end,
        "RawData": {},
        "CalculatedData": {
            "Sales": sales,
            "GrossProfit": gross_profit,
            "OP": op,
        },
    }


def _period(label: str, half: str, fy_end: str, sales: float, gross_profit: float, op: float) -> dict:
    return {
        "label": label,
        "half": half,
        "fy_end": fy_end,
        "data": {
            "Sales": sales,
            "GrossProfit": gross_profit,
            "OP": op,
        },
    }


def test_apply_operating_profit_change_to_years_decomposes_op_change() -> None:
    years = [
        _year("2024-03-31", 1_200.0, 480.0, 150.0),
        _year("2023-03-31", 1_000.0, 350.0, 100.0),
    ]

    apply_operating_profit_change_to_years(years)

    current = years[0]["CalculatedData"]
    assert current["SellingGeneralAdministrativeExpenses"] == pytest.approx(330.0)
    assert current["OperatingProfitChange"] == pytest.approx(50.0)
    assert current["SalesChangeImpact"] == pytest.approx(70.0)
    assert current["GrossMarginChangeImpact"] == pytest.approx(60.0)
    assert current["SGAChangeImpact"] == pytest.approx(-80.0)
    assert current["OperatingProfitChangeReconciliationDiff"] == pytest.approx(0.0)
    assert current["MetricSources"]["SalesChangeImpact"]["source"] == "derived"


def test_apply_operating_profit_change_to_years_skips_change_without_prior() -> None:
    years = [_year("2024-03-31", 1_200.0, 480.0, 150.0)]

    apply_operating_profit_change_to_years(years)

    current = years[0]["CalculatedData"]
    assert current["SellingGeneralAdministrativeExpenses"] == pytest.approx(330.0)
    assert "OperatingProfitChange" not in current


def test_apply_operating_profit_change_to_periods_compares_same_half() -> None:
    periods = [
        _period("23H1", "H1", "2023-03-31", 400.0, 140.0, 40.0),
        _period("23H2", "H2", "2023-03-31", 600.0, 210.0, 60.0),
        _period("24H1", "H1", "2024-03-31", 500.0, 200.0, 70.0),
        _period("24H2", "H2", "2024-03-31", 700.0, 280.0, 80.0),
    ]

    apply_operating_profit_change_to_periods(periods)

    h1 = periods[2]["data"]
    h2 = periods[3]["data"]
    assert h1["OperatingProfitChange"] == pytest.approx(30.0)
    assert h1["SalesChangeImpact"] == pytest.approx(35.0)
    assert h1["GrossMarginChangeImpact"] == pytest.approx(25.0)
    assert h1["SGAChangeImpact"] == pytest.approx(-30.0)
    assert h1["OperatingProfitChangeReconciliationDiff"] == pytest.approx(0.0)
    assert h2["OperatingProfitChange"] == pytest.approx(20.0)
    assert h2["SalesChangeImpact"] == pytest.approx(35.0)


_M = 1_000_000  # MILLION_YEN


def _gp_entry(
    current: float,
    prior: float,
    current_sales: float,
    prior_sales: float,
) -> dict:
    return {
        "current": current * _M,
        "prior": prior * _M,
        "method": "computed",
        "accounting_standard": "J-GAAP",
        "components": [],
        "current_sales": current_sales * _M,
        "prior_sales": prior_sales * _M,
    }


def _op_entry(current: float, prior: float) -> dict:
    return {"current": current * _M, "prior": prior * _M, "method": "direct", "label": "営業利益", "accounting_standard": "J-GAAP"}


def test_apply_operating_profit_change_from_xbrl_uses_filing_prior_values() -> None:
    """有報の前期値（XBRL）から全年度の前年差を計算できる。"""
    years = [
        {
            "fy_end": "2022-03-31",
            "FinancialPeriod": "2022年03月期",
            "RawData": {},
            "CalculatedData": {},
        },
        {
            "fy_end": "2023-03-31",
            "FinancialPeriod": "2023年03月期",
            "RawData": {},
            "CalculatedData": {},
        },
    ]
    # 2022年度の有報に「当期(2022)」と「前期(2021)」の数値が入っている
    gp_by_year = {
        "20220331": _gp_entry(current=480.0, prior=350.0, current_sales=1_200.0, prior_sales=1_000.0),
        "20230331": _gp_entry(current=600.0, prior=480.0, current_sales=1_500.0, prior_sales=1_200.0),
    }
    op_by_year = {
        "20220331": _op_entry(current=150.0, prior=100.0),
        "20230331": _op_entry(current=200.0, prior=150.0),
    }

    apply_operating_profit_change_from_xbrl(years, gp_by_year, op_by_year)

    cd_2022 = years[0]["CalculatedData"]
    assert cd_2022["OperatingProfitChange"] == pytest.approx(50.0)
    assert cd_2022["SalesChangeImpact"] == pytest.approx(70.0)
    assert cd_2022["GrossMarginChangeImpact"] == pytest.approx(60.0)
    assert cd_2022["SGAChangeImpact"] == pytest.approx(-80.0)
    assert cd_2022["OperatingProfitChangeReconciliationDiff"] == pytest.approx(0.0)

    cd_2023 = years[1]["CalculatedData"]
    assert cd_2023["OperatingProfitChange"] == pytest.approx(50.0)


def test_apply_operating_profit_change_from_xbrl_skips_when_xbrl_missing() -> None:
    """XBRLデータがない年度はスキップされる。"""
    years = [
        {
            "fy_end": "2022-03-31",
            "FinancialPeriod": "2022年03月期",
            "RawData": {},
            "CalculatedData": {},
        },
    ]
    apply_operating_profit_change_from_xbrl(years, {}, {})
    assert "OperatingProfitChange" not in years[0]["CalculatedData"]


def test_apply_operating_profit_change_from_xbrl_sga_without_prior() -> None:
    """当期GP/OPはあるが前期値が欠ける場合、販管費は付与されるが前年差分解は出ない。"""
    years = [
        {
            "fy_end": "2022-03-31",
            "FinancialPeriod": "2022年03月期",
            "RawData": {},
            "CalculatedData": {},
        },
    ]
    gp_by_year = {
        "20220331": {
            "current": 480.0 * _M,
            "prior": None,
            "method": "computed",
            "accounting_standard": "J-GAAP",
            "components": [],
            "current_sales": 1_200.0 * _M,
            "prior_sales": None,
        }
    }
    op_by_year = {
        "20220331": {"current": 150.0 * _M, "prior": None, "method": "direct", "label": "営業利益", "accounting_standard": "J-GAAP"},
    }

    apply_operating_profit_change_from_xbrl(years, gp_by_year, op_by_year)

    cd = years[0]["CalculatedData"]
    assert cd["SellingGeneralAdministrativeExpenses"] == pytest.approx(330.0)
    assert "OperatingProfitChange" not in cd
