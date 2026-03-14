
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


if __name__ == "__main__":
    unittest.main()
