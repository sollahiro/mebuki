import asyncio
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

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


if __name__ == "__main__":
    test_cmd_analyze_multi_year()
