import tempfile
from pathlib import Path

from mebuki.analysis.order_book import extract_order_book

NS_XBRLI = "http://www.xbrl.org/2003/instance"
NS_JPCRP = "http://disclosure.edinet-fsa.go.jp/taxonomy/jpcrp/2022-11-01/jpcrp_cor"
NS_XHTML = "http://www.w3.org/1999/xhtml"


def _make_xbrl(textblock_xml: str) -> str:
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<xbrli:xbrl
    xmlns:xbrli="{NS_XBRLI}"
    xmlns:jpcrp_cor="{NS_JPCRP}"
    xmlns:xhtml="{NS_XHTML}">
  <jpcrp_cor:ManagementAnalysisOfFinancialPositionOperatingResultsAndCashFlowsTextBlock contextRef="CurrentYearDuration">
    {textblock_xml}
  </jpcrp_cor:ManagementAnalysisOfFinancialPositionOperatingResultsAndCashFlowsTextBlock>
</xbrli:xbrl>"""


def _write_instance(xbrl_dir: Path, body: str) -> None:
    (xbrl_dir / "instance.xml").write_text(_make_xbrl(body), encoding="utf-8")


class TestOrderBookExtraction:
    def setup_method(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.xbrl_dir = Path(self.tmp.name)

    def teardown_method(self):
        self.tmp.cleanup()

    def test_extracts_with_header_columns(self):
        _write_instance(
            self.xbrl_dir,
            """
            <xhtml:table>
              <xhtml:tr>
                <xhtml:th></xhtml:th>
                <xhtml:th>前連結会計年度</xhtml:th>
                <xhtml:th>当連結会計年度</xhtml:th>
              </xhtml:tr>
              <xhtml:tr>
                <xhtml:td>受注高</xhtml:td>
                <xhtml:td>140,000</xhtml:td>
                <xhtml:td>151,272</xhtml:td>
              </xhtml:tr>
              <xhtml:tr>
                <xhtml:td>受注残高</xhtml:td>
                <xhtml:td>90,000</xhtml:td>
                <xhtml:td>105,778</xhtml:td>
              </xhtml:tr>
            </xhtml:table>
            """,
        )

        result = extract_order_book(self.xbrl_dir)

        assert result["method"] == "mda_textblock_table"
        assert result["order_intake"] == 151_272_000_000
        assert result["order_intake_prior"] == 140_000_000_000
        assert result["order_backlog"] == 105_778_000_000
        assert result["order_backlog_prior"] == 90_000_000_000

    def test_extracts_without_header_from_typical_three_numeric_columns(self):
        _write_instance(
            self.xbrl_dir,
            """
            <xhtml:table>
              <xhtml:tr>
                <xhtml:td>受注高（百万円）</xhtml:td>
                <xhtml:td>200,000</xhtml:td>
                <xhtml:td>215,627</xhtml:td>
                <xhtml:td>15,627</xhtml:td>
              </xhtml:tr>
              <xhtml:tr>
                <xhtml:td>期末受注残高（百万円）</xhtml:td>
                <xhtml:td>80,000</xhtml:td>
                <xhtml:td>96,452</xhtml:td>
                <xhtml:td>16,452</xhtml:td>
              </xhtml:tr>
            </xhtml:table>
            """,
        )

        result = extract_order_book(self.xbrl_dir)

        assert result["order_intake"] == 215_627_000_000
        assert result["order_backlog"] == 96_452_000_000

    def test_extracts_kubota_expected_values_with_year_headers(self):
        _write_instance(
            self.xbrl_dir,
            """
            <xhtml:table>
              <xhtml:tr>
                <xhtml:th>前年度</xhtml:th>
                <xhtml:th>当年度</xhtml:th>
              </xhtml:tr>
              <xhtml:tr>
                <xhtml:td>受注高</xhtml:td>
                <xhtml:td>300,000</xhtml:td>
                <xhtml:td>326,535</xhtml:td>
              </xhtml:tr>
              <xhtml:tr>
                <xhtml:td>受注残高</xhtml:td>
                <xhtml:td>310,000</xhtml:td>
                <xhtml:td>333,781</xhtml:td>
              </xhtml:tr>
            </xhtml:table>
            """,
        )

        result = extract_order_book(self.xbrl_dir)

        assert result["order_intake"] == 326_535_000_000
        assert result["order_backlog"] == 333_781_000_000

    def test_extracts_kubota_expected_values_from_escaped_total_row_table(self):
        _write_instance(
            self.xbrl_dir,
            """
            &lt;table&gt;
              &lt;tbody&gt;
                &lt;tr&gt;
                  &lt;td&gt;事業別セグメントの名称&lt;/td&gt;
                  &lt;td&gt;受注高(百万円)&lt;/td&gt;
                  &lt;td&gt;前年度比(％)&lt;/td&gt;
                  &lt;td&gt;受注残高(百万円)&lt;/td&gt;
                  &lt;td&gt;前年度末比(％)&lt;/td&gt;
                &lt;/tr&gt;
                &lt;tr&gt;
                  &lt;td&gt;水・環境&lt;/td&gt;
                  &lt;td&gt;319,301&lt;/td&gt;
                  &lt;td&gt;23.9&lt;/td&gt;
                  &lt;td&gt;329,918&lt;/td&gt;
                  &lt;td&gt;10.4&lt;/td&gt;
                &lt;/tr&gt;
                &lt;tr&gt;
                  &lt;td&gt;合計&lt;/td&gt;
                  &lt;td&gt;326,535&lt;/td&gt;
                  &lt;td&gt;23.8&lt;/td&gt;
                  &lt;td&gt;333,781&lt;/td&gt;
                  &lt;td&gt;10.4&lt;/td&gt;
                &lt;/tr&gt;
              &lt;/tbody&gt;
            &lt;/table&gt;
            """,
        )

        result = extract_order_book(self.xbrl_dir)

        assert result["order_intake"] == 326_535_000_000
        assert result["order_backlog"] == 333_781_000_000

    def test_extracts_organo_expected_values_from_escaped_text(self):
        _write_instance(
            self.xbrl_dir,
            """
            &lt;p&gt;この結果、当連結会計年度の業績は受注高&lt;span&gt;151,272百万円&lt;/span&gt;
            （前連結会計年度比4.7％増）となりました。また、翌年度以降の売上のベースとなる
            繰越受注残は&lt;span&gt;105,778百万円&lt;/span&gt;となりました。&lt;/p&gt;
            """,
        )

        result = extract_order_book(self.xbrl_dir)

        assert result["method"] == "mda_textblock_text"
        assert result["order_intake"] == 151_272_000_000
        assert result["order_backlog"] == 105_778_000_000

    def test_skips_ambiguous_headerless_rows_with_many_numbers(self):
        _write_instance(
            self.xbrl_dir,
            """
            <xhtml:table>
              <xhtml:tr>
                <xhtml:td>受注高</xhtml:td>
                <xhtml:td>1</xhtml:td>
                <xhtml:td>2</xhtml:td>
                <xhtml:td>3</xhtml:td>
                <xhtml:td>4</xhtml:td>
              </xhtml:tr>
            </xhtml:table>
            """,
        )

        result = extract_order_book(self.xbrl_dir)

        assert result["method"] == "not_found"
        assert result["order_intake"] is None
        assert result["order_backlog"] is None

    def test_returns_not_found_when_no_textblock(self):
        (self.xbrl_dir / "instance.xml").write_text(
            f"""<?xml version="1.0" encoding="UTF-8"?>
<xbrli:xbrl xmlns:xbrli="{NS_XBRLI}" xmlns:jpcrp_cor="{NS_JPCRP}">
  <jpcrp_cor:BusinessRisksTextBlock>受注高 1,000</jpcrp_cor:BusinessRisksTextBlock>
</xbrli:xbrl>""",
            encoding="utf-8",
        )

        result = extract_order_book(self.xbrl_dir)

        assert result["method"] == "not_found"
        assert result["order_intake"] is None
        assert result["order_backlog"] is None
