
import unittest
from mebuki.utils.financial_data import extract_annual_data

class TestDeduplication(unittest.TestCase):
    def test_merge_correction_data(self):
        # 1332のケースを模したテストデータ
        # Record 1: 完全なデータ（古い）
        # Record 2: 一部欠損した修正データ（新しい）
        raw_data = [
            {
                "CurFYEn": "2025-03-31",
                "CurPerType": "FY",
                "DiscDate": "2025-05-14",
                "Sales": 886126000000,
                "NP": 25381000000,
                "EPS": 81.66,
                "BPS": 891.31
            },
            {
                "CurFYEn": "2025-03-31",
                "CurPerType": "FY",
                "DiscDate": "2025-05-21",
                "Sales": 886126000000,
                "NP": 27213000000, # NPが訂正されている
                "EPS": None,      # EPSが欠損している
                "BPS": ""        # BPSが空文字
            }
        ]
        
        result = extract_annual_data(raw_data)
        
        self.assertEqual(len(result), 1)
        record = result[0]
        self.assertEqual(record["NP"], 27213000000) # 修正されたNPが採用されていること
        self.assertEqual(record["EPS"], 81.66)      # 古いレコードからEPSが維持されていること
        self.assertEqual(record["BPS"], 891.31)     # 古いレコードからBPSが維持されていること
        self.assertEqual(record["DiscDate"], "2025-05-21") # 日付は最新になっていること

    def test_zero_does_not_overwrite_valid_value(self):
        # 修正申告で未変更のフィールドが0だった場合、古い有効値を上書きしないこと
        raw_data = [
            {
                "CurFYEn": "2025-03-31",
                "CurPerType": "FY",
                "DiscDate": "2025-05-14",
                "Sales": 886126000000,
                "NP": 25381000000,
            },
            {
                "CurFYEn": "2025-03-31",
                "CurPerType": "FY",
                "DiscDate": "2025-05-21",
                "Sales": 886126000000,
                "NP": 0,  # 未修正フィールドが0として返ってきた場合
            }
        ]

        result = extract_annual_data(raw_data)

        self.assertEqual(len(result), 1)
        record = result[0]
        # NP=0 で古い有効値が上書きされていないこと
        self.assertEqual(record["NP"], 25381000000)

    def test_string_metadata_is_preserved(self):
        # 文字列メタデータ（CurPerType等）は正しくマージされること
        raw_data = [
            {
                "CurFYEn": "2025-03-31",
                "CurPerType": "FY",
                "DiscDate": "2025-05-14",
                "Sales": 886126000000,
            },
            {
                "CurFYEn": "2025-03-31",
                "CurPerType": "FY",
                "DiscDate": "2025-05-21",
                "Sales": 900000000000,
            }
        ]

        result = extract_annual_data(raw_data)

        self.assertEqual(len(result), 1)
        record = result[0]
        self.assertEqual(record["CurPerType"], "FY")
        self.assertEqual(record["CurFYEn"], "2025-03-31")
        self.assertEqual(record["Sales"], 900000000000)

    def test_reverse_order_keeps_latest_valid_values_and_old_missing_fields(self):
        # APIレスポンスの順序に依存せず、最新の有効値を採用し、欠損値では上書きしないこと
        raw_data = [
            {
                "CurFYEn": "2025-03-31",
                "CurPerType": "FY",
                "DiscDate": "2025-05-21",
                "Sales": 886126000000,
                "NP": 27213000000,
                "EPS": None,
                "BPS": "",
            },
            {
                "CurFYEn": "2025-03-31",
                "CurPerType": "FY",
                "DiscDate": "2025-05-14",
                "Sales": 880000000000,
                "NP": 25381000000,
                "EPS": 81.66,
                "BPS": 891.31,
            },
        ]

        result = extract_annual_data(raw_data)

        self.assertEqual(len(result), 1)
        record = result[0]
        self.assertEqual(record["Sales"], 886126000000)
        self.assertEqual(record["NP"], 27213000000)
        self.assertEqual(record["EPS"], 81.66)
        self.assertEqual(record["BPS"], 891.31)
        self.assertEqual(record["DiscDate"], "2025-05-21")

    def test_include_2q_deduplicates_fy_and_2q_separately(self):
        raw_data = [
            {
                "CurFYEn": "2025-03-31",
                "CurPerType": "FY",
                "DiscDate": "2025-05-21",
                "Sales": 1000,
                "NP": 100,
            },
            {
                "CurFYEn": "2025-03-31",
                "CurPerType": "2Q",
                "DiscDate": "2024-11-14",
                "Sales": 400,
                "NP": 40,
            },
            {
                "CurFYEn": "2025-03-31",
                "CurPerType": "2Q",
                "DiscDate": "2024-11-21",
                "Sales": 450,
                "NP": 0,
            },
        ]

        result = extract_annual_data(raw_data, include_2q=True)

        self.assertEqual(len(result), 2)
        by_type = {record["CurPerType"]: record for record in result}
        self.assertEqual(by_type["FY"]["Sales"], 1000)
        self.assertEqual(by_type["2Q"]["Sales"], 450)
        self.assertEqual(by_type["2Q"]["NP"], 40)
        self.assertEqual(by_type["2Q"]["DiscDate"], "2024-11-21")


if __name__ == "__main__":
    unittest.main()
