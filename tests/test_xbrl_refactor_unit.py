
import unittest
import tempfile
from pathlib import Path
from blue_ticker.analysis.xbrl_parser import XBRLParser
from blue_ticker.constants.xbrl import XBRL_SECTIONS

class TestXBRLParserRefactor(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.xbrl_path = Path(self.temp_dir.name)
        
        # Create a dummy XBRL instance file
        self.xml_content = """<?xml version="1.0" encoding="UTF-8"?>
<xbrli:xbrl xmlns:xbrli="http://www.xbrl.org/2003/instance" xmlns:jpcrp_cor="http://disclosure.edinet-fsa.go.jp/taxonomy/jpcrp/2022-11-01/jpcrp_cor">
    <jpcrp_cor:BusinessRisksTextBlock>
        当社グループの事業におけるリスクは以下の通りです。
        1. 市場リスク... 市場状況の変動により、当社の業績に重大な影響を及ぼす可能性があります。具体的には競合他社の動向や景気後退などが挙げられます。
    </jpcrp_cor:BusinessRisksTextBlock>
    <jpcrp_cor:ManagementAnalysisOfFinancialPositionOperatingResultsAndCashFlowsTextBlock>
        当連結会計年度の経営成績は、主力のDX事業が好調に推移した結果、売上高は前期比10%増となりました。営業利益についてもコスト削減が進み、大幅な増益を達成しております。今後も成長投資を継続してまいります。
    </jpcrp_cor:ManagementAnalysisOfFinancialPositionOperatingResultsAndCashFlowsTextBlock>
    <jpcrp_cor:OverviewOfCapitalExpendituresEtcOwnUsedAssetsLEATextBlock>
        設備投資の総額は100億円です。このうち、新工場の建設に80億円、既存設備の更新に20億円を充当いたしました。これにより将来の生産能力が1.5倍に拡大する見込みです。
    </jpcrp_cor:OverviewOfCapitalExpendituresEtcOwnUsedAssetsLEATextBlock>
</xbrli:xbrl>
"""
        (self.xbrl_path / "test_instance.xml").write_text(self.xml_content, encoding="utf-8")
        self.parser = XBRLParser()

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_section_extraction_with_new_ids(self):
        """新しくリファクタリングしたIDでセクションが取得できるかテスト"""
        sections = self.parser.extract_sections_by_type(self.xbrl_path)
        
        # mda (旧D) が取得できるか
        self.assertIn('mda', sections)
        self.assertIn('当連結会計年度の経営成績', sections['mda'])
        
        # business_risks が取得できるか
        self.assertIn('business_risks', sections)
        self.assertIn('市場リスク', sections['business_risks'])
        
        # capex_overview が取得できるか
        self.assertIn('capex_overview', sections)
        self.assertIn('100億円', sections['capex_overview'])
        
        # 旧ID 'D' が存在しないことを確認
        self.assertNotIn('D', sections)

    def test_section_order(self):
        """定義順（business_risks -> mda -> capex...）でセクションが返されるかテスト"""
        sections = self.parser.extract_sections_by_type(self.xbrl_path)
        keys = [k for k, v in sections.items() if v]

        pos_risks = keys.index("business_risks")
        pos_mda = keys.index("mda")
        pos_capex = keys.index("capex_overview")

        self.assertTrue(pos_risks < pos_mda < pos_capex, f"Order is wrong: risks({pos_risks}), mda({pos_mda}), capex({pos_capex})")
    
    def test_all_sections_presence(self):
        """すべての定義済みセクションが結果に含まれているかテスト"""
        sections = self.parser.extract_sections_by_type(self.xbrl_path)
        for section_id in XBRL_SECTIONS.keys():
            self.assertIn(section_id, sections)

if __name__ == "__main__":
    unittest.main()
