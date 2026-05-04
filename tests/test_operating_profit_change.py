import pytest

from mebuki.utils.operating_profit_change import (
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
