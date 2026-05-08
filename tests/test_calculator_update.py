import sys
from pathlib import Path
from typing import Any, cast

# プロジェクトルートをパスに追加
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

from blue_ticker.analysis.calculator import calculate_metrics_flexible
from blue_ticker.utils.metrics_access import metric_view


def test_calculate_metrics_preserves_sales_label_from_xbrl_record():
    metrics = calculate_metrics_flexible(
        [
            {
                "CurFYEn": "2025-03-31",
                "CurPerType": "FY",
                "Sales": 2_922_428_000_000,
                "SalesLabel": "経常収益",
                "NP": 257_635_000_000,
                "NetAssets": 3_127_317_000_000,
            }
        ],
        analysis_years=1,
    )

    years = metrics.get("years")
    assert years is not None
    cd = cast(dict[str, Any], years[0]["CalculatedData"])
    rd = cast(dict[str, Any], years[0]["RawData"])
    assert rd["Sales"] == 2_922_428_000_000
    assert metric_view(years[0])["Sales"] == 2_922_428
    assert rd["SalesLabel"] == "経常収益"
    assert metric_view(years[0])["SalesLabel"] == "経常収益"
    assert cd["MetricSources"]["Sales"]["label"] == "経常収益"
    assert cd["MetricSources"]["Sales"]["source"] == "edinet"


def test_annual_financial_period():
    print("Testing annual financial period calculation...")
    annual_data = [
        {"CurFYEn": "20240331", "CurPerType": "FY", "Sales": 1000000000, "ShOutFY": 1000},
        {"CurFYEn": "20230331", "CurPerType": "FY", "Sales": 900000000, "ShOutFY": 1000}
    ]
    
    metrics = calculate_metrics_flexible(annual_data, analysis_years=2)
    
    years = metrics.get("years")
    assert years is not None
    assert len(years) == 2

    assert years[0]["FinancialPeriod"] == "2024年03月期"
    assert years[1]["FinancialPeriod"] == "2023年03月期"
    print("Annual test passed!")


def test_adjustment_ratio_uses_year_end_issued_shares():
    metrics = calculate_metrics_flexible(
        [
            {
                "CurFYEn": "2024-03-31",
                "CurPerType": "FY",
                "Sales": 1_000_000_000,
                "EPS": 50.0,
                "BPS": 500.0,
                "ShOutFY": 2_000,
            },
            {
                "CurFYEn": "2023-03-31",
                "CurPerType": "FY",
                "Sales": 900_000_000,
                "EPS": 100.0,
                "BPS": 800.0,
                "ShOutFY": 1_000,
            },
        ],
        analysis_years=2,
    )

    years = metrics.get("years")
    assert years is not None
    current = cast(dict[str, Any], years[0]["CalculatedData"])
    prior = cast(dict[str, Any], years[1]["CalculatedData"])
    assert current["AdjustmentRatio"] == 1.0
    assert current["AdjustedEPS"] == 50.0
    assert prior["AdjustmentRatio"] == 0.5
    assert prior["AdjustedEPS"] == 50.0
    assert prior["AdjustedBPS"] == 400.0


def test_adjustment_ratio_ignores_share_count_drift_without_split():
    metrics = calculate_metrics_flexible(
        [
            {
                "CurFYEn": "2025-03-31",
                "CurPerType": "FY",
                "Sales": 1_000_000_000,
                "EPS": 70.0,
                "BPS": 360.0,
                "ShOutFY": 502_818_808,
            },
            {
                "CurFYEn": "2024-03-31",
                "CurPerType": "FY",
                "Sales": 900_000_000,
                "EPS": 167.44,
                "BPS": 790.28,
                "ShOutFY": 521_430_854,
            },
        ],
        analysis_years=2,
    )

    years = metrics.get("years")
    assert years is not None
    prior = cast(dict[str, Any], years[1]["CalculatedData"])
    assert prior["AdjustmentRatio"] == 1.0
    assert prior["AdjustedEPS"] == 167.44
    assert prior["AdjustedBPS"] == 790.28


def test_adjustment_ratio_snaps_near_split_ratio():
    metrics = calculate_metrics_flexible(
        [
            {
                "CurFYEn": "2025-03-31",
                "CurPerType": "FY",
                "Sales": 1_000_000_000,
                "EPS": 50.0,
                "BPS": 500.0,
                "ShOutFY": 2_000,
            },
            {
                "CurFYEn": "2024-03-31",
                "CurPerType": "FY",
                "Sales": 900_000_000,
                "EPS": 100.0,
                "BPS": 800.0,
                "ShOutFY": 1_070,
            },
        ],
        analysis_years=2,
    )

    years = metrics.get("years")
    assert years is not None
    prior = cast(dict[str, Any], years[1]["CalculatedData"])
    assert prior["AdjustmentRatio"] == 0.5
    assert prior["AdjustedEPS"] == 50.0
    assert prior["AdjustedBPS"] == 400.0

if __name__ == "__main__":
    try:
        test_annual_financial_period()
        print("\nAll tests passed successfully!")
        sys.exit(0)
    except AssertionError as e:
        print(f"\nTest failed: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\nAn error occurred: {e}")
        sys.exit(1)
