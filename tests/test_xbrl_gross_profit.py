"""
売上総利益 XBRL 抽出 - ユニットテスト

損益計算書（Duration コンテキスト）から売上総利益を抽出するロジックを検証する。

検証対象基準・銘柄:
  J-GAAP: ニチレイ（2871）
  IFRS:   味の素（2802）・日立製作所（6501）
  US-GAAP: オムロン（6645）

抽出戦略:
  1. 直接法: GrossProfit タグ
  2. 計算法: 売上高 − 売上原価
"""

import unittest
import tempfile
from pathlib import Path

from mebuki.analysis.gross_profit import extract_gross_profit

NS_XBRLI = "http://www.xbrl.org/2003/instance"
NS_JPPFS = "http://disclosure.edinet-fsa.go.jp/taxonomy/jppfs/2022-11-01/jppfs_cor"
NS_JPIFRS = "http://disclosure.edinet-fsa.go.jp/taxonomy/jpifrs/2022-11-01/jpifrs_cor"
NS_JPCRP = "http://disclosure.edinet-fsa.go.jp/taxonomy/jpcrp/2022-11-01/jpcrp_cor"


def _make_xbrl_duration(elements_xml: str, extra_ns: str = "") -> str:
    """Duration コンテキストを持つ最小限の XBRL インスタンスを生成する。"""
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


class TestGrossProfitDirectMethod(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.xbrl_dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_direct_tag_jgaap(self):
        """J-GAAP: GrossProfit タグが直接存在する場合（ニチレイ想定）"""
        xml = _make_xbrl_duration("""
            <jppfs_cor:GrossProfit contextRef="CurrentYearDuration"
                unitRef="JPY" decimals="-6">120000000000</jppfs_cor:GrossProfit>
            <jppfs_cor:GrossProfit contextRef="Prior1YearDuration"
                unitRef="JPY" decimals="-6">110000000000</jppfs_cor:GrossProfit>
        """)
        (self.xbrl_dir / "instance.xml").write_text(xml, encoding="utf-8")
        result = extract_gross_profit(self.xbrl_dir)
        self.assertEqual(result["method"], "direct")
        self.assertEqual(result["accounting_standard"], "J-GAAP")
        self.assertAlmostEqual(result["current"], 120_000_000_000)
        self.assertAlmostEqual(result["prior"], 110_000_000_000)
        self.assertEqual(len(result["components"]), 1)
        self.assertEqual(result["components"][0]["tag"], "GrossProfit")

    def test_direct_tag_ifrs(self):
        """IFRS: GrossProfitIFRS タグが直接存在する場合（味の素・日立想定）"""
        xml = _make_xbrl_duration("""
            <jpifrs_cor:BorrowingsCLIFRS contextRef="CurrentYearDuration"
                unitRef="JPY" decimals="-6">10000000000</jpifrs_cor:BorrowingsCLIFRS>
            <jpifrs_cor:GrossProfitIFRS contextRef="CurrentYearDuration"
                unitRef="JPY" decimals="-6">550764000000</jpifrs_cor:GrossProfitIFRS>
            <jpifrs_cor:GrossProfitIFRS contextRef="Prior1YearDuration"
                unitRef="JPY" decimals="-6">520000000000</jpifrs_cor:GrossProfitIFRS>
        """)
        (self.xbrl_dir / "instance.xml").write_text(xml, encoding="utf-8")
        result = extract_gross_profit(self.xbrl_dir)
        self.assertEqual(result["method"], "direct")
        self.assertEqual(result["accounting_standard"], "IFRS")
        self.assertAlmostEqual(result["current"], 550_764_000_000)
        self.assertAlmostEqual(result["prior"], 520_000_000_000)


class TestGrossProfitComputedMethod(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.xbrl_dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_computed_jgaap_netsales_costofsales(self):
        """J-GAAP: NetSales − CostOfSales で計算（GrossProfit タグなし）"""
        xml = _make_xbrl_duration("""
            <jppfs_cor:NetSales contextRef="CurrentYearDuration"
                unitRef="JPY" decimals="-6">300000000000</jppfs_cor:NetSales>
            <jppfs_cor:NetSales contextRef="Prior1YearDuration"
                unitRef="JPY" decimals="-6">280000000000</jppfs_cor:NetSales>
            <jppfs_cor:CostOfSales contextRef="CurrentYearDuration"
                unitRef="JPY" decimals="-6">180000000000</jppfs_cor:CostOfSales>
            <jppfs_cor:CostOfSales contextRef="Prior1YearDuration"
                unitRef="JPY" decimals="-6">170000000000</jppfs_cor:CostOfSales>
        """)
        (self.xbrl_dir / "instance.xml").write_text(xml, encoding="utf-8")
        result = extract_gross_profit(self.xbrl_dir)
        self.assertEqual(result["method"], "computed")
        self.assertEqual(result["accounting_standard"], "J-GAAP")
        self.assertAlmostEqual(result["current"], 120_000_000_000)  # 300B - 180B
        self.assertAlmostEqual(result["prior"], 110_000_000_000)    # 280B - 170B

    def test_computed_ifrs_revenue_costofsales(self):
        """IFRS: NetSalesIFRS − CostOfSalesIFRS で計算（GrossProfitIFRS タグなし）"""
        xml = _make_xbrl_duration("""
            <jpifrs_cor:BorrowingsCLIFRS contextRef="CurrentYearDuration"
                unitRef="JPY" decimals="-6">10000000000</jpifrs_cor:BorrowingsCLIFRS>
            <jpifrs_cor:NetSalesIFRS contextRef="CurrentYearDuration"
                unitRef="JPY" decimals="-6">500000000000</jpifrs_cor:NetSalesIFRS>
            <jpifrs_cor:NetSalesIFRS contextRef="Prior1YearDuration"
                unitRef="JPY" decimals="-6">460000000000</jpifrs_cor:NetSalesIFRS>
            <jpifrs_cor:CostOfSalesIFRS contextRef="CurrentYearDuration"
                unitRef="JPY" decimals="-6">300000000000</jpifrs_cor:CostOfSalesIFRS>
            <jpifrs_cor:CostOfSalesIFRS contextRef="Prior1YearDuration"
                unitRef="JPY" decimals="-6">280000000000</jpifrs_cor:CostOfSalesIFRS>
        """)
        (self.xbrl_dir / "instance.xml").write_text(xml, encoding="utf-8")
        result = extract_gross_profit(self.xbrl_dir)
        self.assertEqual(result["method"], "computed")
        self.assertEqual(result["accounting_standard"], "IFRS")
        self.assertAlmostEqual(result["current"], 200_000_000_000)  # 500B - 300B
        self.assertAlmostEqual(result["prior"], 180_000_000_000)    # 460B - 280B

    def test_computed_no_cogs_uses_sales_only(self):
        """売上原価タグがない場合、売上高がそのまま売上総利益になる（COGS=0扱い）"""
        xml = _make_xbrl_duration("""
            <jppfs_cor:NetSales contextRef="CurrentYearDuration"
                unitRef="JPY" decimals="-6">100000000000</jppfs_cor:NetSales>
        """)
        (self.xbrl_dir / "instance.xml").write_text(xml, encoding="utf-8")
        result = extract_gross_profit(self.xbrl_dir)
        self.assertEqual(result["method"], "computed")
        self.assertAlmostEqual(result["current"], 100_000_000_000)


class TestGrossProfitConsolidatedPriority(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.xbrl_dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_consolidated_over_nonconsolidated(self):
        """連結値が存在する場合、個別値より連結を優先する"""
        xml = _make_xbrl_duration("""
            <jppfs_cor:GrossProfit contextRef="CurrentYearDuration"
                unitRef="JPY" decimals="-6">200000000000</jppfs_cor:GrossProfit>
            <jppfs_cor:GrossProfit contextRef="CurrentYearDuration_NonConsolidatedMember"
                unitRef="JPY" decimals="-6">50000000000</jppfs_cor:GrossProfit>
        """)
        (self.xbrl_dir / "instance.xml").write_text(xml, encoding="utf-8")
        result = extract_gross_profit(self.xbrl_dir)
        self.assertEqual(result["method"], "direct")
        self.assertAlmostEqual(result["current"], 200_000_000_000)  # 連結値

    def test_pure_context_over_segment_context(self):
        """同一タグにセグメント修飾値があっても純コンテキストを優先する"""
        xml = _make_xbrl_duration("""
            <jppfs_cor:GrossProfit contextRef="CurrentYearDuration"
                unitRef="JPY" decimals="-6">200000000000</jppfs_cor:GrossProfit>
            <jppfs_cor:GrossProfit contextRef="CurrentYearDuration_SomeSegmentMember"
                unitRef="JPY" decimals="-6">50000000000</jppfs_cor:GrossProfit>
            <jppfs_cor:GrossProfit contextRef="Prior1YearDuration"
                unitRef="JPY" decimals="-6">180000000000</jppfs_cor:GrossProfit>
            <jppfs_cor:GrossProfit contextRef="Prior1YearDuration_SomeSegmentMember"
                unitRef="JPY" decimals="-6">45000000000</jppfs_cor:GrossProfit>
        """)
        (self.xbrl_dir / "instance.xml").write_text(xml, encoding="utf-8")
        result = extract_gross_profit(self.xbrl_dir)
        self.assertEqual(result["method"], "direct")
        self.assertAlmostEqual(result["current"], 200_000_000_000)
        self.assertAlmostEqual(result["prior"], 180_000_000_000)

    def test_falls_back_to_nonconsolidated(self):
        """連結値がなく個別値のみの場合、個別値を返す"""
        xml = _make_xbrl_duration("""
            <jppfs_cor:GrossProfit contextRef="CurrentYearDuration_NonConsolidatedMember"
                unitRef="JPY" decimals="-6">50000000000</jppfs_cor:GrossProfit>
        """)
        (self.xbrl_dir / "instance.xml").write_text(xml, encoding="utf-8")
        result = extract_gross_profit(self.xbrl_dir)
        self.assertEqual(result["method"], "direct")
        self.assertAlmostEqual(result["current"], 50_000_000_000)

    def test_pure_nonconsolidated_context_over_segment_context(self):
        """個別フォールバックでもセグメント修飾値より純コンテキストを優先する"""
        xml = _make_xbrl_duration("""
            <jppfs_cor:GrossProfit contextRef="CurrentYearDuration_NonConsolidatedMember"
                unitRef="JPY" decimals="-6">50000000000</jppfs_cor:GrossProfit>
            <jppfs_cor:GrossProfit contextRef="CurrentYearDuration_NonConsolidatedMember_SomeSegmentMember"
                unitRef="JPY" decimals="-6">10000000000</jppfs_cor:GrossProfit>
            <jppfs_cor:GrossProfit contextRef="Prior1YearDuration_NonConsolidatedMember"
                unitRef="JPY" decimals="-6">45000000000</jppfs_cor:GrossProfit>
            <jppfs_cor:GrossProfit contextRef="Prior1YearDuration_NonConsolidatedMember_SomeSegmentMember"
                unitRef="JPY" decimals="-6">9000000000</jppfs_cor:GrossProfit>
        """)
        (self.xbrl_dir / "instance.xml").write_text(xml, encoding="utf-8")
        result = extract_gross_profit(self.xbrl_dir)
        self.assertEqual(result["method"], "direct")
        self.assertAlmostEqual(result["current"], 50_000_000_000)
        self.assertAlmostEqual(result["prior"], 45_000_000_000)


class TestGrossProfitNotFound(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.xbrl_dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_not_found_empty_dir(self):
        """XMLファイルが存在しない場合は not_found を返す"""
        result = extract_gross_profit(self.xbrl_dir)
        self.assertEqual(result["method"], "not_found")
        self.assertIsNone(result["current"])
        self.assertIsNone(result["prior"])

    def test_not_found_no_matching_tags(self):
        """対象タグが存在しない XBRL では not_found を返す"""
        xml = _make_xbrl_duration("""
            <jppfs_cor:TotalAssets contextRef="CurrentYearDuration"
                unitRef="JPY" decimals="-6">999000000000</jppfs_cor:TotalAssets>
        """)
        (self.xbrl_dir / "instance.xml").write_text(xml, encoding="utf-8")
        result = extract_gross_profit(self.xbrl_dir)
        self.assertEqual(result["method"], "not_found")
        self.assertIsNone(result["current"])

    def test_pre_parsed_keeps_usgaap_cash_marker(self):
        """pre_parsed 経由でも US-GAAP 判定マーカーを落とさない"""
        result = extract_gross_profit(
            self.xbrl_dir,
            pre_parsed={
                "CashAndCashEquivalentsUSGAAPSummaryOfBusinessResults": {
                    "CurrentYearDuration": 100_000_000_000.0
                }
            },
        )
        self.assertEqual(result["method"], "not_found")
        self.assertEqual(result["accounting_standard"], "US-GAAP")

    def test_usgaap_html_attaches_summary_revenues_for_yoy(self):
        """US-GAAP HTML抽出でも要約情報の売上高当期・前期を付与する"""
        html = """
        <html><body><table>
          <tr><th></th><th>前連結会計年度</th><th>当連結会計年度</th></tr>
          <tr><td>売上総利益</td><td>1,033,224</td><td>1,137,928</td></tr>
        </table></body></html>
        """
        (self.xbrl_dir / "0105010.htm").write_text(html, encoding="utf-8")
        result = extract_gross_profit(
            self.xbrl_dir,
            pre_parsed={
                "CashAndCashEquivalentsUSGAAPSummaryOfBusinessResults": {
                    "CurrentYearDuration": 1.0
                },
                "RevenuesUSGAAPSummaryOfBusinessResults": {
                    "CurrentYearDuration": 2_859_041_000_000.0,
                    "Prior1YearDuration": 2_525_773_000_000.0,
                },
            },
        )
        self.assertEqual(result["method"], "usgaap_html")
        self.assertEqual(result["accounting_standard"], "US-GAAP")
        self.assertAlmostEqual(result.get("current_sales"), 2_859_041_000_000.0)
        self.assertAlmostEqual(result.get("prior_sales"), 2_525_773_000_000.0)

    def test_prior_only(self):
        """前期値のみ存在する場合も正常に返す"""
        xml = _make_xbrl_duration("""
            <jppfs_cor:GrossProfit contextRef="Prior1YearDuration"
                unitRef="JPY" decimals="-6">100000000000</jppfs_cor:GrossProfit>
        """)
        (self.xbrl_dir / "instance.xml").write_text(xml, encoding="utf-8")
        result = extract_gross_profit(self.xbrl_dir)
        self.assertEqual(result["method"], "direct")
        self.assertIsNone(result["current"])
        self.assertAlmostEqual(result["prior"], 100_000_000_000)


class TestSalesTagPriorityForYoY(unittest.TestCase):
    """_extract_sales_for_yoy: 当期・前期が両方揃うタグを片側だけのタグより優先する"""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.xbrl_dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_prefers_both_sides_tag_over_current_only_tag(self):
        """先行タグが当期のみ・後続タグが当期+前期 → 後続タグを採用して prior_sales が取れる"""
        xml = _make_xbrl_duration("""
            <jpifrs_cor:BorrowingsCLIFRS contextRef="CurrentYearDuration"
                unitRef="JPY" decimals="-6">10000000000</jpifrs_cor:BorrowingsCLIFRS>
            <jpifrs_cor:GrossProfitIFRS contextRef="CurrentYearDuration"
                unitRef="JPY" decimals="-6">500000000000</jpifrs_cor:GrossProfitIFRS>
            <jpifrs_cor:GrossProfitIFRS contextRef="Prior1YearDuration"
                unitRef="JPY" decimals="-6">450000000000</jpifrs_cor:GrossProfitIFRS>
            <jpifrs_cor:NetSalesIFRS contextRef="CurrentYearDuration"
                unitRef="JPY" decimals="-6">1000000000000</jpifrs_cor:NetSalesIFRS>
            <jpifrs_cor:Revenue contextRef="CurrentYearDuration"
                unitRef="JPY" decimals="-6">900000000000</jpifrs_cor:Revenue>
            <jpifrs_cor:Revenue contextRef="Prior1YearDuration"
                unitRef="JPY" decimals="-6">800000000000</jpifrs_cor:Revenue>
        """)
        (self.xbrl_dir / "instance.xml").write_text(xml, encoding="utf-8")
        result = extract_gross_profit(self.xbrl_dir)
        self.assertEqual(result["method"], "direct")
        self.assertIsNotNone(result.get("prior_sales"), "prior_sales が取得できていない（片側タグで止まった可能性）")
        self.assertAlmostEqual(result.get("prior_sales"), 800_000_000_000)
        self.assertAlmostEqual(result.get("current_sales"), 900_000_000_000)

    def test_falls_back_to_partial_tag_when_no_both_sides(self):
        """全タグが当期のみの場合は最初の候補を返す（current_sales のみ）"""
        xml = _make_xbrl_duration("""
            <jpifrs_cor:BorrowingsCLIFRS contextRef="CurrentYearDuration"
                unitRef="JPY" decimals="-6">10000000000</jpifrs_cor:BorrowingsCLIFRS>
            <jpifrs_cor:GrossProfitIFRS contextRef="CurrentYearDuration"
                unitRef="JPY" decimals="-6">500000000000</jpifrs_cor:GrossProfitIFRS>
            <jpifrs_cor:GrossProfitIFRS contextRef="Prior1YearDuration"
                unitRef="JPY" decimals="-6">450000000000</jpifrs_cor:GrossProfitIFRS>
            <jpifrs_cor:NetSalesIFRS contextRef="CurrentYearDuration"
                unitRef="JPY" decimals="-6">1000000000000</jpifrs_cor:NetSalesIFRS>
        """)
        (self.xbrl_dir / "instance.xml").write_text(xml, encoding="utf-8")
        result = extract_gross_profit(self.xbrl_dir)
        self.assertEqual(result["method"], "direct")
        self.assertAlmostEqual(result.get("current_sales"), 1_000_000_000_000)
        self.assertIsNone(result.get("prior_sales"))


if __name__ == "__main__":
    unittest.main()
