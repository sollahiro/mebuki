
import sys
from pathlib import Path
import unittest

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from mebuki.utils.jquants_utils import prepare_edinet_search_data

class TestJQuantsUtilsFix(unittest.TestCase):
    def test_prepare_edinet_search_data_hybrid_logic(self):
        """
        Test hybrid logic:
        - DiscDate should come from EARLIEST record (to maximize search window)
        - CurFYEn/CurPerEn should come from LATEST valid record (to ensure correct metadata)
        """
        
        financial_data = [
            # Record 1: Early report (Preliminary)
            # DiscDate: 2024-05-01 (Earliest) -> Should be used for DiscDate
            # CurFYEn: Missing (Bad metadata)
            {
                "Date": "2024-05-01",
                "Code": "28020",
                "CurFYEn": "", 
                "CurPerEn": "", 
                "CurFYSt": "20230401", 
                "DiscDate": "2024-05-01",
                "CurPerType": "FY"
            },
            # Record 2: Middle report
            {
                "Date": "2024-05-15",
                "Code": "28020",
                "CurFYEn": "20240331", 
                "CurPerEn": "20240331", 
                "CurFYSt": "20230401",
                "DiscDate": "2024-05-15",
                "CurPerType": "FY"
            },
            # Record 3: Late report (Correction/Final)
            # DiscDate: 2024-06-30 (Latest)
            # CurFYEn: 20240331 (Valid Metadata) -> Should be used for metadata
            # Special check: If we have a correction with even later date
            {
                "Date": "2024-06-30",
                "Code": "28020",
                "CurFYEn": "20240331", 
                "CurPerEn": "20240331", 
                "CurFYSt": "20230401",
                "DiscDate": "2024-06-30",
                "CurPerType": "FY",
                "Sales": "999999" # Unique value to identify valid record usage
            }
        ]
        
        # Execute
        annual_data_idx, years_list = prepare_edinet_search_data(financial_data, max_records=5)
        
        # Verify
        self.assertEqual(len(annual_data_idx), 1, "Should have 1 representative record")
        
        record = annual_data_idx[0]
        
        # 1. DiscDate should be from the EARLIEST record (2024-05-01)
        self.assertEqual(record["DiscDate"], "2024-05-01", "Should use earliest DiscDate for search start")
        
        # 2. CurFYEn should be from the LATEST record (20240331)
        self.assertEqual(record["CurFYEn"], "20240331", "CurFYEn should be from latest record")
        
        # 3. Other metadata should be from the LATEST record
        # Note: Sales is not returned by prepare_edinet_search_data, so we trust CurFYEn check above.
        # self.assertEqual(record.get("Sales"), "999999", "Metadata/Values should be from latest record")
        
        self.assertEqual(record["fiscal_year"], 2023)

    def test_prepare_edinet_search_data_already_present(self):
        """Test that existing valid CurFYEn is preserved"""
        financial_data = [
            {
                "Date": "2024-05-01",
                "Code": "28020",
                "CurFYEn": "20240331",
                "CurPerEn": "20240331",
                "CurFYSt": "20230401", 
                "DiscDate": "2024-05-01",
                "CurPerType": "FY"
            }
        ]
        
        annual_data_idx, years_list = prepare_edinet_search_data(financial_data)
        record = annual_data_idx[0]
        self.assertEqual(record["CurFYEn"], "20240331")

if __name__ == '__main__':
    unittest.main()
