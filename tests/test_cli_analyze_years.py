import asyncio
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

# プロジェクトルートを追加
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Mock missing dependencies before imports
sys.modules["keyring"] = MagicMock()
sys.modules["questionary"] = MagicMock()

from blue_ticker.app.cli import cmd_analyze


def test_cmd_analyze_multi_year():
    # Mock settings
    mock_settings = MagicMock()
    mock_settings.analysis_years = 5

    # Mock args
    class MockArgs:
        code = "7203"
        years = 3
        format = "table"
        no_cache = False

    args = MockArgs()

    # Mock data_service
    mock_result = {
        "metrics": {
            "years": [
                {
                    "fy_end": "20240331",
                    "CalculatedData": {
                        "Sales": 1000000,
                        "OP": 100000,
                        "ROE": 15.0,
                    },
                },
                {
                    "fy_end": "20230331",
                    "CalculatedData": {
                        "Sales": 900000,
                        "OP": 90000,
                        "ROE": 14.0,
                    },
                },
                {
                    "fy_end": "20220331",
                    "CalculatedData": {
                        "Sales": 800000,
                        "OP": 80000,
                        "ROE": 13.0,
                    },
                },
            ]
        }
    }

    with (
        patch("blue_ticker.services.data_service.data_service.fetch_stock_basic_info") as mock_info,
        patch("blue_ticker.services.data_service.data_service.get_raw_analysis_data") as mock_get_data,
        patch("blue_ticker.app.cli.analyze.settings_store", mock_settings),
    ):
        mock_info.return_value = {"name": "トヨタ自動車", "market_name": "プライム"}
        mock_get_data.return_value = mock_result

        asyncio.run(cmd_analyze(args))


def test_cmd_analyze_table_shows_net_profit_and_cash_equivalents(capsys):
    mock_settings = MagicMock()
    mock_settings.analysis_years = 5

    class MockArgs:
        code = "7203"
        years = 1
        format = "table"
        no_cache = False

    args = MockArgs()
    mock_result = {
        "metrics": {
            "years": [
                {
                    "fy_end": "20240331",
                    "RawData": {
                        "CurPerType": "FY",
                        "EPS": 320.5,
                        "BPS": 2_100.25,
                        "ShOutFY": 1_234_567,
                        "DivTotalAnn": 12_000_000_000,
                        "DivAnn": 80.0,
                        "Div2Q": 40.0,
                    },
                    "CalculatedData": {
                        "Sales": 45_095_325.0,
                        "OP": 5_352_934.0,
                        "NP": 4_944_933.0,
                        "CashEq": 9_412_060.0,
                        "AdjustedEPS": 160.25,
                        "AdjustedBPS": 1_050.75,
                    },
                },
            ]
        }
    }

    with (
        patch("blue_ticker.services.data_service.data_service.fetch_stock_basic_info") as mock_info,
        patch("blue_ticker.services.data_service.data_service.get_raw_analysis_data") as mock_get_data,
        patch("blue_ticker.services.data_service.data_service.close", new_callable=AsyncMock),
        patch("blue_ticker.app.cli.analyze.settings_store", mock_settings),
    ):
        mock_info.return_value = {"name": "トヨタ自動車", "market_name": "プライム"}
        mock_get_data.return_value = mock_result

        asyncio.run(cmd_analyze(args))

    captured = capsys.readouterr()
    assert "純利益 (百万)" in captured.err
    assert "現金及び現金同等物 (百万)" in captured.err
    assert "EPS (円)" in captured.err
    assert "BPS (円)" in captured.err
    assert "調整後EPS (円)" in captured.err
    assert "調整後BPS (円)" in captured.err
    assert "期末発行済株式数 (株)" in captured.err
    assert "年間配当総額 (百万)" in captured.err
    assert "年間配当 (円)" in captured.err
    assert "中間配当 (円)" in captured.err
    assert "4944933.00" in captured.err
    assert "9412060.00" in captured.err
    assert "320.50" in captured.err
    assert "2100.25" in captured.err
    assert "160.25" in captured.err
    assert "1050.75" in captured.err
    assert "1,234,567" in captured.err
    assert "12000.00" in captured.err


if __name__ == "__main__":
    test_cmd_analyze_multi_year()
