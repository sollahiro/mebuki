"""
営業利益 XBRL 抽出 - ユニットテスト

損益計算書（Duration コンテキスト）から営業利益を抽出するロジックを検証する。

検証対象:
  J-GAAP: OperatingIncomeLoss タグ直接取得
  IFRS:   OperatingProfitLossIFRS タグ直接取得
  IFRS:   GrossProfitIFRS − SGA 計算（日立等 OperatingProfitLossIFRS なし）
  経常利益: 金融機関フォールバック
  連結優先: 連結タグがなければ個別にフォールバック
"""

import unittest
import tempfile
from pathlib import Path

from blue_ticker.analysis.operating_profit import extract_operating_profit
from blue_ticker.analysis.sections import IncomeStatementSection

NS_XBRLI = "http://www.xbrl.org/2003/instance"
NS_JPPFS = "http://disclosure.edinet-fsa.go.jp/taxonomy/jppfs/2022-11-01/jppfs_cor"
NS_JPIFRS = "http://disclosure.edinet-fsa.go.jp/taxonomy/jpifrs/2022-11-01/jpifrs_cor"
NS_JPCRP = "http://disclosure.edinet-fsa.go.jp/taxonomy/jpcrp/2022-11-01/jpcrp_cor"


def _make_xbrl(elements_xml: str, extra_ns: str = "") -> str:
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<xbrli:xbrl
    xmlns:xbrli="{NS_XBRLI}"
    xmlns:jppfs_cor="{NS_JPPFS}"
    xmlns:jpifrs_cor="{NS_JPIFRS}"
    xmlns:jpcrp_cor="{NS_JPCRP}"{extra_ns}>

  <xbrli:context id="CurrentYearDuration">
    <xbrli:entity>
      <xbrli:identifier scheme="http://disclosure.edinet-fsa.go.jp">E12345</xbrli:identifier>
    </xbrli:entity>
    <xbrli:period>
      <xbrli:startDate>2023-04-01</xbrli:startDate>
      <xbrli:endDate>2024-03-31</xbrli:endDate>
    </xbrli:period>
  </xbrli:context>

  <xbrli:context id="Prior1YearDuration">
    <xbrli:entity>
      <xbrli:identifier scheme="http://disclosure.edinet-fsa.go.jp">E12345</xbrli:identifier>
    </xbrli:entity>
    <xbrli:period>
      <xbrli:startDate>2022-04-01</xbrli:startDate>
      <xbrli:endDate>2023-03-31</xbrli:endDate>
    </xbrli:period>
  </xbrli:context>

  <xbrli:context id="CurrentYearDuration_NonConsolidatedMember">
    <xbrli:entity>
      <xbrli:identifier scheme="http://disclosure.edinet-fsa.go.jp">E12345</xbrli:identifier>
    </xbrli:entity>
    <xbrli:period>
      <xbrli:startDate>2023-04-01</xbrli:startDate>
      <xbrli:endDate>2024-03-31</xbrli:endDate>
    </xbrli:period>
  </xbrli:context>

  <xbrli:context id="Prior1YearDuration_NonConsolidatedMember">
    <xbrli:entity>
      <xbrli:identifier scheme="http://disclosure.edinet-fsa.go.jp">E12345</xbrli:identifier>
    </xbrli:entity>
    <xbrli:period>
      <xbrli:startDate>2022-04-01</xbrli:startDate>
      <xbrli:endDate>2023-03-31</xbrli:endDate>
    </xbrli:period>
  </xbrli:context>

  <xbrli:unit id="JPY"><xbrli:measure>iso4217:JPY</xbrli:measure></xbrli:unit>

  {elements_xml}
</xbrli:xbrl>"""


class TestOperatingProfitDirectMethod(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.xbrl_dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_direct_jgaap(self):
        """J-GAAP: OperatingIncomeLoss タグを直接取得する"""
        xml = _make_xbrl("""
            <jppfs_cor:OperatingIncomeLoss contextRef="CurrentYearDuration"
                unitRef="JPY" decimals="-6">500000000000</jppfs_cor:OperatingIncomeLoss>
            <jppfs_cor:OperatingIncomeLoss contextRef="Prior1YearDuration"
                unitRef="JPY" decimals="-6">450000000000</jppfs_cor:OperatingIncomeLoss>
        """)
        (self.xbrl_dir / "instance.xml").write_text(xml, encoding="utf-8")
        result = extract_operating_profit(IncomeStatementSection.from_xbrl(self.xbrl_dir))
        self.assertEqual(result["method"], "direct")
        self.assertEqual(result["label"], "営業利益")
        self.assertEqual(result["accounting_standard"], "J-GAAP")
        self.assertAlmostEqual(result["current"], 500_000_000_000)
        self.assertAlmostEqual(result["prior"], 450_000_000_000)

    def test_direct_ifrs(self):
        """IFRS: OperatingProfitLossIFRS タグを直接取得する"""
        xml = _make_xbrl("""
            <jpifrs_cor:BorrowingsCLIFRS contextRef="CurrentYearDuration"
                unitRef="JPY" decimals="-6">100000000000</jpifrs_cor:BorrowingsCLIFRS>
            <jpifrs_cor:OperatingProfitLossIFRS contextRef="CurrentYearDuration"
                unitRef="JPY" decimals="-6">755816000000</jpifrs_cor:OperatingProfitLossIFRS>
            <jpifrs_cor:OperatingProfitLossIFRS contextRef="Prior1YearDuration"
                unitRef="JPY" decimals="-6">696000000000</jpifrs_cor:OperatingProfitLossIFRS>
        """)
        (self.xbrl_dir / "instance.xml").write_text(xml, encoding="utf-8")
        result = extract_operating_profit(IncomeStatementSection.from_xbrl(self.xbrl_dir))
        self.assertEqual(result["method"], "direct")
        self.assertEqual(result["accounting_standard"], "IFRS")
        self.assertAlmostEqual(result["current"], 755_816_000_000)
        self.assertAlmostEqual(result["prior"], 696_000_000_000)


class TestOperatingProfitComputedMethod(unittest.TestCase):
    """GP − SGA フォールバック（日立等 OperatingProfitLossIFRS なし IFRS 企業向け）"""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.xbrl_dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_computed_ifrs_gp_minus_sga(self):
        """IFRS: OperatingProfitLossIFRS なし・GrossProfitIFRS と SGA あり → GP − SGA で算出"""
        gp_current = 2_607_357_000_000
        gp_prior = 2_434_185_000_000
        sga_current = 1_851_541_000_000
        sga_prior = 1_686_041_000_000

        xml = _make_xbrl(f"""
            <jpifrs_cor:BorrowingsCLIFRS contextRef="CurrentYearDuration"
                unitRef="JPY" decimals="-6">100000000000</jpifrs_cor:BorrowingsCLIFRS>
            <jpifrs_cor:GrossProfitIFRS contextRef="CurrentYearDuration"
                unitRef="JPY" decimals="-6">{gp_current}</jpifrs_cor:GrossProfitIFRS>
            <jpifrs_cor:GrossProfitIFRS contextRef="Prior1YearDuration"
                unitRef="JPY" decimals="-6">{gp_prior}</jpifrs_cor:GrossProfitIFRS>
            <jpifrs_cor:SellingGeneralAndAdministrativeExpensesIFRS contextRef="CurrentYearDuration"
                unitRef="JPY" decimals="-6">{sga_current}</jpifrs_cor:SellingGeneralAndAdministrativeExpensesIFRS>
            <jpifrs_cor:SellingGeneralAndAdministrativeExpensesIFRS contextRef="Prior1YearDuration"
                unitRef="JPY" decimals="-6">{sga_prior}</jpifrs_cor:SellingGeneralAndAdministrativeExpensesIFRS>
        """)
        (self.xbrl_dir / "instance.xml").write_text(xml, encoding="utf-8")
        result = extract_operating_profit(IncomeStatementSection.from_xbrl(self.xbrl_dir))
        self.assertEqual(result["method"], "computed")
        self.assertEqual(result["label"], "営業利益")
        self.assertEqual(result["accounting_standard"], "IFRS")
        self.assertAlmostEqual(result["current"], gp_current - sga_current)
        self.assertAlmostEqual(result["prior"], gp_prior - sga_prior)
        self.assertAlmostEqual(result["current_sga"], sga_current)
        self.assertAlmostEqual(result["prior_sga"], sga_prior)

    def test_computed_ifrs_prior_only(self):
        """GP・SGA の前期値しかない場合は prior のみ返す"""
        xml = _make_xbrl("""
            <jpifrs_cor:BorrowingsCLIFRS contextRef="CurrentYearDuration"
                unitRef="JPY" decimals="-6">100000000000</jpifrs_cor:BorrowingsCLIFRS>
            <jpifrs_cor:GrossProfitIFRS contextRef="Prior1YearDuration"
                unitRef="JPY" decimals="-6">2000000000000</jpifrs_cor:GrossProfitIFRS>
            <jpifrs_cor:SellingGeneralAndAdministrativeExpensesIFRS contextRef="Prior1YearDuration"
                unitRef="JPY" decimals="-6">1500000000000</jpifrs_cor:SellingGeneralAndAdministrativeExpensesIFRS>
        """)
        (self.xbrl_dir / "instance.xml").write_text(xml, encoding="utf-8")
        result = extract_operating_profit(IncomeStatementSection.from_xbrl(self.xbrl_dir))
        self.assertEqual(result["method"], "computed")
        self.assertIsNone(result["current"])
        self.assertAlmostEqual(result["prior"], 500_000_000_000)

    def test_computed_prefers_direct_over_gp_sga(self):
        """OperatingProfitLossIFRS が存在する場合は GP − SGA より優先される"""
        xml = _make_xbrl("""
            <jpifrs_cor:BorrowingsCLIFRS contextRef="CurrentYearDuration"
                unitRef="JPY" decimals="-6">100000000000</jpifrs_cor:BorrowingsCLIFRS>
            <jpifrs_cor:OperatingProfitLossIFRS contextRef="CurrentYearDuration"
                unitRef="JPY" decimals="-6">800000000000</jpifrs_cor:OperatingProfitLossIFRS>
            <jpifrs_cor:GrossProfitIFRS contextRef="CurrentYearDuration"
                unitRef="JPY" decimals="-6">2000000000000</jpifrs_cor:GrossProfitIFRS>
            <jpifrs_cor:SellingGeneralAndAdministrativeExpensesIFRS contextRef="CurrentYearDuration"
                unitRef="JPY" decimals="-6">1500000000000</jpifrs_cor:SellingGeneralAndAdministrativeExpensesIFRS>
        """)
        (self.xbrl_dir / "instance.xml").write_text(xml, encoding="utf-8")
        result = extract_operating_profit(IncomeStatementSection.from_xbrl(self.xbrl_dir))
        self.assertEqual(result["method"], "direct")
        self.assertAlmostEqual(result["current"], 800_000_000_000)
        self.assertAlmostEqual(result["current_sga"], 1_500_000_000_000)


class TestOperatingProfitFallbacks(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.xbrl_dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_ordinary_income_fallback(self):
        """経常利益フォールバック: 営業利益タグがない金融機関向け"""
        xml = _make_xbrl("""
            <jppfs_cor:OrdinaryIncomeSummaryOfBusinessResults contextRef="CurrentYearDuration"
                unitRef="JPY" decimals="-6">1200000000000</jppfs_cor:OrdinaryIncomeSummaryOfBusinessResults>
            <jppfs_cor:OrdinaryIncomeSummaryOfBusinessResults contextRef="Prior1YearDuration"
                unitRef="JPY" decimals="-6">1000000000000</jppfs_cor:OrdinaryIncomeSummaryOfBusinessResults>
            <jppfs_cor:OrdinaryIncome contextRef="CurrentYearDuration"
                unitRef="JPY" decimals="-6">300000000000</jppfs_cor:OrdinaryIncome>
            <jppfs_cor:OrdinaryIncome contextRef="Prior1YearDuration"
                unitRef="JPY" decimals="-6">280000000000</jppfs_cor:OrdinaryIncome>
        """)
        (self.xbrl_dir / "instance.xml").write_text(xml, encoding="utf-8")
        result = extract_operating_profit(IncomeStatementSection.from_xbrl(self.xbrl_dir))
        self.assertEqual(result["method"], "ordinary_income")
        self.assertEqual(result["label"], "経常利益")
        self.assertAlmostEqual(result["current"], 300_000_000_000)
        self.assertAlmostEqual(result.get("current_sales"), 1_200_000_000_000)
        self.assertAlmostEqual(result.get("prior_sales"), 1_000_000_000_000)

    def test_consolidated_preferred_over_nonconsolidated(self):
        """連結タグがある場合は個別タグより優先される"""
        xml = _make_xbrl("""
            <jppfs_cor:OperatingIncomeLoss contextRef="CurrentYearDuration"
                unitRef="JPY" decimals="-6">900000000000</jppfs_cor:OperatingIncomeLoss>
            <jppfs_cor:OperatingIncomeLoss contextRef="CurrentYearDuration_NonConsolidatedMember"
                unitRef="JPY" decimals="-6">100000000000</jppfs_cor:OperatingIncomeLoss>
        """)
        (self.xbrl_dir / "instance.xml").write_text(xml, encoding="utf-8")
        result = extract_operating_profit(IncomeStatementSection.from_xbrl(self.xbrl_dir))
        self.assertEqual(result["method"], "direct")
        self.assertAlmostEqual(result["current"], 900_000_000_000)

    def test_pure_context_over_segment_context(self):
        """同一タグにセグメント修飾値があっても純コンテキストを優先する"""
        xml = _make_xbrl("""
            <jppfs_cor:OperatingIncomeLoss contextRef="CurrentYearDuration"
                unitRef="JPY" decimals="-6">900000000000</jppfs_cor:OperatingIncomeLoss>
            <jppfs_cor:OperatingIncomeLoss contextRef="CurrentYearDuration_SomeSegmentMember"
                unitRef="JPY" decimals="-6">100000000000</jppfs_cor:OperatingIncomeLoss>
            <jppfs_cor:OperatingIncomeLoss contextRef="Prior1YearDuration"
                unitRef="JPY" decimals="-6">850000000000</jppfs_cor:OperatingIncomeLoss>
            <jppfs_cor:OperatingIncomeLoss contextRef="Prior1YearDuration_SomeSegmentMember"
                unitRef="JPY" decimals="-6">90000000000</jppfs_cor:OperatingIncomeLoss>
        """)
        (self.xbrl_dir / "instance.xml").write_text(xml, encoding="utf-8")
        result = extract_operating_profit(IncomeStatementSection.from_xbrl(self.xbrl_dir))
        self.assertEqual(result["method"], "direct")
        self.assertAlmostEqual(result["current"], 900_000_000_000)
        self.assertAlmostEqual(result["prior"], 850_000_000_000)

    def test_single_entity_uses_plain_context(self):
        """単体のみ企業（_NonConsolidatedMember なし）は plain context の値を返す"""
        xml = _make_xbrl("""
            <jppfs_cor:OperatingIncomeLoss contextRef="CurrentYearDuration"
                unitRef="JPY" decimals="-6">150000000000</jppfs_cor:OperatingIncomeLoss>
        """)
        (self.xbrl_dir / "instance.xml").write_text(xml, encoding="utf-8")
        result = extract_operating_profit(IncomeStatementSection.from_xbrl(self.xbrl_dir))
        self.assertEqual(result["method"], "direct")
        self.assertAlmostEqual(result["current"], 150_000_000_000)

    def test_single_entity_pure_context_over_segment_context(self):
        """単体のみ企業でもセグメント修飾値より純コンテキストを優先する"""
        xml = _make_xbrl("""
            <jppfs_cor:OperatingIncomeLoss contextRef="CurrentYearDuration"
                unitRef="JPY" decimals="-6">150000000000</jppfs_cor:OperatingIncomeLoss>
            <jppfs_cor:OperatingIncomeLoss contextRef="CurrentYearDuration_SomeSegmentMember"
                unitRef="JPY" decimals="-6">25000000000</jppfs_cor:OperatingIncomeLoss>
            <jppfs_cor:OperatingIncomeLoss contextRef="Prior1YearDuration"
                unitRef="JPY" decimals="-6">140000000000</jppfs_cor:OperatingIncomeLoss>
            <jppfs_cor:OperatingIncomeLoss contextRef="Prior1YearDuration_SomeSegmentMember"
                unitRef="JPY" decimals="-6">20000000000</jppfs_cor:OperatingIncomeLoss>
        """)
        (self.xbrl_dir / "instance.xml").write_text(xml, encoding="utf-8")
        result = extract_operating_profit(IncomeStatementSection.from_xbrl(self.xbrl_dir))
        self.assertEqual(result["method"], "direct")
        self.assertAlmostEqual(result["current"], 150_000_000_000)
        self.assertAlmostEqual(result["prior"], 140_000_000_000)

    def test_not_found(self):
        """該当タグが一切ない場合は not_found を返す"""
        xml = _make_xbrl("")
        (self.xbrl_dir / "instance.xml").write_text(xml, encoding="utf-8")
        result = extract_operating_profit(IncomeStatementSection.from_xbrl(self.xbrl_dir))
        self.assertEqual(result["method"], "not_found")
        self.assertIsNone(result["current"])
        self.assertIsNone(result["prior"])
