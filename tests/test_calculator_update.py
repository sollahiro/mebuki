import sys
from pathlib import Path

# プロジェクトルートをパスに追加
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

from mebuki.analysis.calculator import calculate_metrics_flexible, calculate_quarterly_metrics

def test_annual_financial_period():
    print("Testing annual financial period calculation...")
    annual_data = [
        {"CurFYEn": "20240331", "CurPerType": "FY", "Sales": 1000000000, "AvgSh": 1000},
        {"CurFYEn": "20230331", "CurPerType": "FY", "Sales": 900000000, "AvgSh": 1000}
    ]
    
    metrics = calculate_metrics_flexible(annual_data, analysis_years=2)
    
    assert "years" in metrics
    assert len(metrics["years"]) == 2
    
    assert metrics["years"][0]["FinancialPeriod"] == "2024年03月期"
    assert metrics["years"][1]["FinancialPeriod"] == "2023年03月期"
    print("Annual test passed!")

def test_quarterly_financial_period():
    print("\nTesting quarterly financial period calculation...")
    quarterly_data = [
        {"CurFYEn": "2024-12-31", "CurPerType": "3Q", "Sales": 500000000},
        {"CurFYEn": "2024-09-30", "CurPerType": "2Q", "Sales": 300000000}
    ]
    
    metrics = calculate_quarterly_metrics(quarterly_data, quarters=2)
    
    assert "quarters_data" in metrics
    assert len(metrics["quarters_data"]) == 2
    
    assert metrics["quarters_data"][0]["FinancialPeriod"] == "2024年12月期"
    assert metrics["quarters_data"][1]["FinancialPeriod"] == "2024年09月期"
    print("Quarterly test passed!")

if __name__ == "__main__":
    try:
        test_annual_financial_period()
        test_quarterly_financial_period()
        print("\nAll tests passed successfully!")
        sys.exit(0)
    except AssertionError as e:
        print(f"\nTest failed: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\nAn error occurred: {e}")
        sys.exit(1)
