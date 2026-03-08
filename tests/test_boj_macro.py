import sys
import os
import unittest
from unittest.mock import MagicMock, patch

# プロジェクトルートをパスに追加
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.utils.boj_client import BOJClient
from mebuki.utils.cache import CacheManager

class TestBOJMacro(unittest.TestCase):
    
    def setUp(self):
        # CacheManagerをモック
        self.mock_cache = MagicMock(spec=CacheManager)
        self.mock_cache.enabled = True
        self.boj_client = BOJClient(cache=self.mock_cache)
        self.boj_client.interval = 0

    @patch("requests.get")
    def test_boj_client_request(self, mock_get):
        # 新API形式のモック
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "RESULTSET": [
                {
                    "SERIES_CODE": "MADR1Z@D",
                    "VALUES": {
                        "SURVEY_DATES": [20240101],
                        "VALUES": [0.3]
                    }
                }
            ],
            "NEXTPOSITION": None
        }
        mock_get.return_value = mock_response
        self.mock_cache.get.return_value = None
        
        data = self.boj_client.get_time_series("IR01", "MADR1Z@D")
        
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["value"], 0.3)
        self.assertEqual(data[0]["date"], "20240101")
        self.mock_cache.set.assert_called()

    @patch("requests.get")
    def test_boj_client_server_error(self, mock_get):
        # STATUS 400 系のエラー（M181090S）
        mock_response_error = MagicMock()
        mock_response_error.status_code = 200
        mock_response_error.json.return_value = {
            "STATUS": 400,
            "MESSAGEID": "M181090S",
            "MESSAGE": "Server Error"
        }
        
        mock_response_success = MagicMock()
        mock_response_success.status_code = 200
        mock_response_success.json.return_value = {
            "RESULTSET": [{"VALUES": {"SURVEY_DATES": [20240101], "VALUES": [0.3]}}]
        }
        
        mock_get.side_effect = [mock_response_error, mock_response_success]
        self.mock_cache.get.return_value = None
        
        data = self.boj_client.get_time_series("IR01", "MADR1Z@D")
        
        self.assertEqual(len(data), 1)
        self.assertEqual(mock_get.call_count, 2)

    @patch("requests.get")
    def test_boj_client_pagination(self, mock_get):
        # NEXTPOSITIONによるページネーション
        mock_response_1 = MagicMock()
        mock_response_1.status_code = 200
        mock_response_1.json.return_value = {
            "NEXTPOSITION": 2,
            "RESULTSET": [{"VALUES": {"SURVEY_DATES": [20240101], "VALUES": [0.1]}}]
        }
        
        mock_response_2 = MagicMock()
        mock_response_2.status_code = 200
        mock_response_2.json.return_value = {
            "NEXTPOSITION": None,
            "RESULTSET": [{"VALUES": {"SURVEY_DATES": [20240102], "VALUES": [0.2]}}]
        }
        
        mock_get.side_effect = [mock_response_1, mock_response_2]
        self.mock_cache.get.return_value = None
        
        data = self.boj_client.get_time_series("IR01", "MADR1Z@D")
        
        self.assertEqual(len(data), 2)
        self.assertEqual(data[0]["value"], 0.1)
        self.assertEqual(data[1]["value"], 0.2)

    @patch("requests.get")
    def test_date_normalization(self, mock_get):
        # YYYY形式がYYYYMMに変換されるか
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"RESULTSET": []}
        mock_get.return_value = mock_response
        self.mock_cache.get.return_value = None
        
        self.boj_client.get_time_series("IR01", "CODE", start_date="2021", end_date="2026")
        
        # 呼ばれた際の引数を確認
        args, kwargs = mock_get.call_args
        params = kwargs.get("params", {})
        self.assertEqual(params.get("startDate"), "202101")
        self.assertEqual(params.get("endDate"), "202612")

if __name__ == "__main__":
    unittest.main()
