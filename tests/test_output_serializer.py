from mebuki.utils.output_serializer import (
    serialize_half_year_periods,
    serialize_metrics_result,
)


def test_serialize_metrics_result_excludes_debug_fields_by_default():
    metrics = {
        "code": "7203",
        "company_name": "Toyota",
        "analysis_years": 1,
        "years": [
            {
                "fy_end": "2024-03-31",
                "RawData": {"Sales": 45_000_000},
                "CalculatedData": {
                    "Sales": 45_000.0,
                    "SalesLabel": "売上高",
                    "OP": 5_000.0,
                    "OPLabel": "営業利益",
                    "MetricSources": {"Sales": {"source": "jquants"}},
                    "IBDComponents": [{"label": "短期借入金", "current": 100.0}],
                    "GrossProfitMethod": "direct",
                    "IBDAccountingStandard": "J-GAAP",
                },
            }
        ],
    }

    serialized = serialize_metrics_result(metrics)

    assert serialized == {
        "code": "7203",
        "company_name": "Toyota",
        "analysis_years": 1,
        "years": [
            {
                "fy_end": "2024-03-31",
                "RawData": {"Sales": 45_000_000},
                "CalculatedData": {
                    "Sales": 45_000.0,
                    "SalesLabel": "売上高",
                    "OP": 5_000.0,
                    "OPLabel": "営業利益",
                },
            }
        ],
    }
    assert "MetricSources" in metrics["years"][0]["CalculatedData"]


def test_serialize_metrics_result_includes_debug_fields_when_requested():
    metrics = {
        "code": "7203",
        "years": [
            {
                "fy_end": "2024-03-31",
                "CalculatedData": {
                    "Sales": 45_000.0,
                    "MetricSources": {"Sales": {"source": "jquants"}},
                    "IBDComponents": [{"label": "社債", "current": 200.0}],
                    "GrossProfitMethod": "computed",
                    "IBDAccountingStandard": "IFRS",
                },
            }
        ],
    }

    assert serialize_metrics_result(metrics, include_debug_fields=True) == metrics


def test_serialize_metrics_result_handles_missing_years_or_calculated_data():
    metrics_without_years = {"code": "7203"}
    metrics_with_missing_calculated_data = {
        "code": "7203",
        "years": [{"fy_end": "2024-03-31", "RawData": {}}],
    }

    assert serialize_metrics_result(metrics_without_years) == metrics_without_years
    assert serialize_metrics_result(metrics_with_missing_calculated_data) == {
        "code": "7203",
        "years": [
            {
                "fy_end": "2024-03-31",
                "RawData": {},
                "CalculatedData": {},
            }
        ],
    }
    assert "CalculatedData" not in metrics_with_missing_calculated_data["years"][0]


def test_serialize_metrics_result_handles_empty_years():
    metrics = {"code": "7203", "years": []}

    assert serialize_metrics_result(metrics) == {"code": "7203", "years": []}


def test_serialize_half_year_periods_excludes_debug_fields_by_default():
    periods = [
        {
            "label": "24H1",
            "period": "H1",
            "data": {
                "Sales": 45.0,
                "CFC": 4.0,
                "FreeCF": 4.0,
                "MetricSources": {"CFC": {"method": "CFO + CFI"}},
                "IBDComponents": [{"label": "短期借入金", "current": 100.0}],
                "GrossProfitMethod": "direct",
                "IBDAccountingStandard": "J-GAAP",
            },
        }
    ]

    serialized = serialize_half_year_periods(periods)

    assert serialized == [
        {
            "label": "24H1",
            "period": "H1",
            "data": {
                "Sales": 45.0,
                "CFC": 4.0,
                "FreeCF": 4.0,
            },
        }
    ]
    assert "MetricSources" in periods[0]["data"]


def test_serialize_half_year_periods_includes_debug_fields_when_requested():
    periods = [
        {
            "label": "24H1",
            "data": {
                "Sales": 45.0,
                "MetricSources": {"Sales": {"source": "jquants"}},
                "IBDComponents": [{"label": "社債", "current": 200.0}],
                "GrossProfitMethod": "computed",
                "IBDAccountingStandard": "IFRS",
            },
        }
    ]

    assert serialize_half_year_periods(periods, include_debug_fields=True) == periods


def test_serialize_half_year_periods_handles_missing_data():
    periods = [{"label": "24H1", "period": "H1"}]

    assert serialize_half_year_periods(periods) == [
        {
            "label": "24H1",
            "period": "H1",
            "data": {},
        }
    ]
