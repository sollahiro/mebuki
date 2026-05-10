"""
支払利息 XBRL 抽出 - ユニットテスト

損益計算書（Duration コンテキスト）から支払利息を抽出するロジックを検証する。

会計基準: J-GAAP / IFRS / US-GAAP（HTML）
"""

import unittest
import tempfile
from pathlib import Path

from blue_ticker.analysis.interest_expense import extract_interest_expense
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


def _make_usgaap_html(rows: str) -> str:
    """US-GAAP 損益計算書 HTML の最小構成。"""
    return f"""<!DOCTYPE html>
<html>
<body>
<table>
  <tr>
    <th>科目</th>
    <th>前連結会計年度</th>
    <th>当連結会計年度</th>
  </tr>
  {rows}
</table>
</body>
</html>"""


class TestJGaap(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.xbrl_dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_direct_jgaap(self):
        """J-GAAP: InterestExpensesNOE タグから当期・前期を取得する。"""
        xml = _make_xbrl("""
            <jppfs_cor:InterestExpensesNOE contextRef="CurrentYearDuration"
                unitRef="JPY" decimals="-6">8752000000</jppfs_cor:InterestExpensesNOE>
            <jppfs_cor:InterestExpensesNOE contextRef="Prior1YearDuration"
                unitRef="JPY" decimals="-6">9000000000</jppfs_cor:InterestExpensesNOE>
        """)
        (self.xbrl_dir / "instance.xml").write_text(xml, encoding="utf-8")
        result = extract_interest_expense(IncomeStatementSection.from_xbrl(self.xbrl_dir))
        self.assertEqual(result["method"], "direct")
        self.assertEqual(result["accounting_standard"], "J-GAAP")
        self.assertAlmostEqual(result["current"], 8_752_000_000)
        self.assertAlmostEqual(result["prior"], 9_000_000_000)

    def test_consolidated_over_nonconsolidated(self):
        """連結値が存在する場合は個別値より優先する。"""
        xml = _make_xbrl("""
            <jppfs_cor:InterestExpensesNOE contextRef="CurrentYearDuration"
                unitRef="JPY" decimals="-6">8752000000</jppfs_cor:InterestExpensesNOE>
            <jppfs_cor:InterestExpensesNOE contextRef="CurrentYearDuration_NonConsolidatedMember"
                unitRef="JPY" decimals="-6">1000000000</jppfs_cor:InterestExpensesNOE>
        """)
        (self.xbrl_dir / "instance.xml").write_text(xml, encoding="utf-8")
        result = extract_interest_expense(IncomeStatementSection.from_xbrl(self.xbrl_dir))
        self.assertAlmostEqual(result["current"], 8_752_000_000)

    def test_nonconsolidated_fallback(self):
        """連結値がなければ個別値にフォールバックする。"""
        xml = _make_xbrl("""
            <jppfs_cor:InterestExpensesNOE contextRef="CurrentYearDuration_NonConsolidatedMember"
                unitRef="JPY" decimals="-6">1000000000</jppfs_cor:InterestExpensesNOE>
        """)
        (self.xbrl_dir / "instance.xml").write_text(xml, encoding="utf-8")
        result = extract_interest_expense(IncomeStatementSection.from_xbrl(self.xbrl_dir))
        self.assertEqual(result["method"], "direct")
        self.assertAlmostEqual(result["current"], 1_000_000_000)


class TestIfrs(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.xbrl_dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_interest_expenses_ifrs(self):
        """IFRS: InterestExpensesIFRS タグを取得する。"""
        xml = _make_xbrl("""
            <jpifrs_cor:BorrowingsCLIFRS contextRef="CurrentYearDuration"
                unitRef="JPY" decimals="-6">100000000000</jpifrs_cor:BorrowingsCLIFRS>
            <jpifrs_cor:InterestExpensesIFRS contextRef="CurrentYearDuration"
                unitRef="JPY" decimals="-6">5000000000</jpifrs_cor:InterestExpensesIFRS>
            <jpifrs_cor:InterestExpensesIFRS contextRef="Prior1YearDuration"
                unitRef="JPY" decimals="-6">4800000000</jpifrs_cor:InterestExpensesIFRS>
        """)
        (self.xbrl_dir / "instance.xml").write_text(xml, encoding="utf-8")
        result = extract_interest_expense(IncomeStatementSection.from_xbrl(self.xbrl_dir))
        self.assertEqual(result["method"], "direct")
        self.assertEqual(result["accounting_standard"], "IFRS")
        self.assertAlmostEqual(result["current"], 5_000_000_000)
        self.assertAlmostEqual(result["prior"], 4_800_000_000)

    def test_finance_costs_ifrs_fallback(self):
        """IFRS: InterestExpensesIFRS がない場合 FinanceCostsIFRS にフォールバックする。"""
        xml = _make_xbrl("""
            <jpifrs_cor:BorrowingsCLIFRS contextRef="CurrentYearDuration"
                unitRef="JPY" decimals="-6">100000000000</jpifrs_cor:BorrowingsCLIFRS>
            <jpifrs_cor:FinanceCostsIFRS contextRef="CurrentYearDuration"
                unitRef="JPY" decimals="-6">6000000000</jpifrs_cor:FinanceCostsIFRS>
        """)
        (self.xbrl_dir / "instance.xml").write_text(xml, encoding="utf-8")
        result = extract_interest_expense(IncomeStatementSection.from_xbrl(self.xbrl_dir))
        self.assertEqual(result["method"], "direct")
        self.assertEqual(result["accounting_standard"], "IFRS")
        self.assertAlmostEqual(result["current"], 6_000_000_000)

    def test_interest_expense_note_textblock_fallback(self):
        """IFRS: numeric タグがない場合、支払利息注記のテキストから取得する。"""
        xml = _make_xbrl("""
            <jpifrs_cor:BorrowingsCLIFRS contextRef="CurrentYearDuration"
                unitRef="JPY" decimals="-6">100000000000</jpifrs_cor:BorrowingsCLIFRS>
        """)
        (self.xbrl_dir / "instance.xml").write_text(xml, encoding="utf-8")
        html = """
            <html><body>
            <h4>（５）支払利息</h4>
            <p>2024年３月31日および2025年３月31日に終了した各１年間における支払利息は、
            それぞれ<span>1,213,021百万円</span>および<span>1,654,702百万円</span>です。</p>
            </body></html>
        """
        (self.xbrl_dir / "note_ixbrl.htm").write_text(html, encoding="utf-8")

        result = extract_interest_expense(IncomeStatementSection.from_xbrl(self.xbrl_dir))

        self.assertEqual(result["method"], "ifrs_textblock")
        self.assertEqual(result["accounting_standard"], "IFRS")
        self.assertAlmostEqual(result["prior"], 1_213_021_000_000)
        self.assertAlmostEqual(result["current"], 1_654_702_000_000)


class TestUsGaapHtml(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.xbrl_dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def _write_usgaap_xbrl(self):
        xml = _make_xbrl("""
            <jpcrp_cor:TotalAssetsUSGAAPSummaryOfBusinessResults
                contextRef="CurrentYearDuration"
                unitRef="JPY" decimals="-6">5000000000000</jpcrp_cor:TotalAssetsUSGAAPSummaryOfBusinessResults>
        """)
        (self.xbrl_dir / "instance.xml").write_text(xml, encoding="utf-8")

    def test_extracts_positive_values(self):
        """US-GAAP HTML: 正の数値から支払利息を取得する。"""
        self._write_usgaap_xbrl()
        html = _make_usgaap_html("""
            <tr><td>支払利息</td><td>9,000</td><td>8,752</td></tr>
        """)
        (self.xbrl_dir / "0105010_test_ixbrl.htm").write_text(html, encoding="utf-8")
        result = extract_interest_expense(IncomeStatementSection.from_xbrl(self.xbrl_dir))
        self.assertEqual(result["method"], "usgaap_html")
        self.assertEqual(result["accounting_standard"], "US-GAAP")
        self.assertAlmostEqual(result["current"], 8_752_000_000)
        self.assertAlmostEqual(result["prior"], 9_000_000_000)

    def test_extracts_delta_notation(self):
        """US-GAAP HTML: △記法（負数）の支払利息も絶対値で返す。"""
        self._write_usgaap_xbrl()
        html = _make_usgaap_html("""
            <tr><td>支払利息</td><td>△9,000</td><td>△8,752</td></tr>
        """)
        (self.xbrl_dir / "0105010_test_ixbrl.htm").write_text(html, encoding="utf-8")
        result = extract_interest_expense(IncomeStatementSection.from_xbrl(self.xbrl_dir))
        self.assertEqual(result["method"], "usgaap_html")
        self.assertAlmostEqual(result["current"], 8_752_000_000)
        self.assertAlmostEqual(result["prior"], 9_000_000_000)

    def test_no_html_file_returns_not_found(self):
        """US-GAAP で 0105010 HTML が存在しない場合 not_found を返す。"""
        self._write_usgaap_xbrl()
        result = extract_interest_expense(IncomeStatementSection.from_xbrl(self.xbrl_dir))
        self.assertEqual(result["method"], "not_found")
        self.assertEqual(result["accounting_standard"], "US-GAAP")
        self.assertIsNone(result["current"])


class TestNotFound(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.xbrl_dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_no_tags_returns_not_found(self):
        """支払利息タグが一切存在しない場合 not_found を返す。"""
        xml = _make_xbrl("")
        (self.xbrl_dir / "instance.xml").write_text(xml, encoding="utf-8")
        result = extract_interest_expense(IncomeStatementSection.from_xbrl(self.xbrl_dir))
        self.assertEqual(result["method"], "not_found")
        self.assertIsNone(result["current"])
        self.assertIsNone(result["prior"])

    def test_empty_directory(self):
        """XBRL ファイルが存在しない場合 not_found を返す。"""
        result = extract_interest_expense(IncomeStatementSection.from_xbrl(self.xbrl_dir))
        self.assertEqual(result["method"], "not_found")
        self.assertIsNone(result["current"])


if __name__ == "__main__":
    unittest.main()
