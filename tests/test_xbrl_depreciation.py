"""
減価償却費 XBRL抽出 - ユニットテスト
"""

import tempfile
import unittest
from pathlib import Path

from mebuki.analysis.depreciation import extract_depreciation

NS_XBRLI = "http://www.xbrl.org/2003/instance"
NS_JPPFS = "http://disclosure.edinet-fsa.go.jp/taxonomy/jppfs/2022-11-01/jppfs_cor"
NS_JPIGP = "http://disclosure.edinet-fsa.go.jp/taxonomy/jpigp/2022-11-01/jpigp_cor"
NS_JPIFRS = "http://disclosure.edinet-fsa.go.jp/taxonomy/jpifrs/2022-11-01/jpifrs_cor"
NS_JPCRP = "http://disclosure.edinet-fsa.go.jp/taxonomy/jpcrp/2022-11-01/jpcrp_cor"


def _make_xbrl(elements_xml: str, extra_ns: str = "") -> str:
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<xbrli:xbrl
    xmlns:xbrli="{NS_XBRLI}"
    xmlns:jppfs_cor="{NS_JPPFS}"
    xmlns:jpigp_cor="{NS_JPIGP}"
    xmlns:jpifrs_cor="{NS_JPIFRS}"
    xmlns:jpcrp_cor="{NS_JPCRP}"{extra_ns}>

  <xbrli:context id="CurrentYearDuration">
    <xbrli:entity><xbrli:identifier scheme="http://disclosure.edinet-fsa.go.jp">E12345</xbrli:identifier></xbrli:entity>
    <xbrli:period><xbrli:startDate>2023-04-01</xbrli:startDate><xbrli:endDate>2024-03-31</xbrli:endDate></xbrli:period>
  </xbrli:context>

  <xbrli:context id="Prior1YearDuration">
    <xbrli:entity><xbrli:identifier scheme="http://disclosure.edinet-fsa.go.jp">E12345</xbrli:identifier></xbrli:entity>
    <xbrli:period><xbrli:startDate>2022-04-01</xbrli:startDate><xbrli:endDate>2023-03-31</xbrli:endDate></xbrli:period>
  </xbrli:context>

  <xbrli:context id="CurrentYearDuration_NonConsolidatedMember">
    <xbrli:entity><xbrli:identifier scheme="http://disclosure.edinet-fsa.go.jp">E12345</xbrli:identifier></xbrli:entity>
    <xbrli:period><xbrli:startDate>2023-04-01</xbrli:startDate><xbrli:endDate>2024-03-31</xbrli:endDate></xbrli:period>
  </xbrli:context>

  <xbrli:context id="CurrentYearInstant">
    <xbrli:entity><xbrli:identifier scheme="http://disclosure.edinet-fsa.go.jp">E12345</xbrli:identifier></xbrli:entity>
    <xbrli:period><xbrli:instant>2024-03-31</xbrli:instant></xbrli:period>
  </xbrli:context>

{elements_xml}
</xbrli:xbrl>"""


def _write_xbrl(tmp_dir: Path, content: str, filename: str = "test.xbrl") -> Path:
    file_path = tmp_dir / filename
    file_path.write_text(content, encoding="utf-8")
    return tmp_dir


class TestExtractDepreciationJGAAP(unittest.TestCase):
    def test_jgaap_consolidated_current(self):
        with tempfile.TemporaryDirectory() as tmp:
            xbrl_dir = _write_xbrl(
                Path(tmp),
                _make_xbrl(
                    '<jppfs_cor:DepreciationAndAmortizationOpeCF contextRef="CurrentYearDuration" decimals="-6" unitRef="JPY">9209000000</jppfs_cor:DepreciationAndAmortizationOpeCF>'
                ),
            )
            result = extract_depreciation(xbrl_dir)
        self.assertEqual(result["current"], 9209000000.0)
        self.assertIsNone(result["prior"])
        self.assertEqual(result["accounting_standard"], "J-GAAP")
        self.assertEqual(result["method"], "direct")

    def test_jgaap_prior_value(self):
        with tempfile.TemporaryDirectory() as tmp:
            xbrl_dir = _write_xbrl(
                Path(tmp),
                _make_xbrl(
                    '<jppfs_cor:DepreciationAndAmortizationOpeCF contextRef="CurrentYearDuration" decimals="-6" unitRef="JPY">9209000000</jppfs_cor:DepreciationAndAmortizationOpeCF>\n'
                    '<jppfs_cor:DepreciationAndAmortizationOpeCF contextRef="Prior1YearDuration" decimals="-6" unitRef="JPY">8500000000</jppfs_cor:DepreciationAndAmortizationOpeCF>'
                ),
            )
            result = extract_depreciation(xbrl_dir)
        self.assertEqual(result["current"], 9209000000.0)
        self.assertEqual(result["prior"], 8500000000.0)

    def test_jgaap_nonconsolidated_fallback(self):
        """連結コンテキストがなく個別のみの場合、個別値にフォールバックする"""
        with tempfile.TemporaryDirectory() as tmp:
            xbrl_dir = _write_xbrl(
                Path(tmp),
                _make_xbrl(
                    '<jppfs_cor:DepreciationAndAmortizationOpeCF contextRef="CurrentYearDuration_NonConsolidatedMember" decimals="-6" unitRef="JPY">1925000000</jppfs_cor:DepreciationAndAmortizationOpeCF>'
                ),
            )
            result = extract_depreciation(xbrl_dir)
        self.assertEqual(result["current"], 1925000000.0)
        self.assertEqual(result["accounting_standard"], "J-GAAP")

    def test_not_found(self):
        with tempfile.TemporaryDirectory() as tmp:
            xbrl_dir = _write_xbrl(Path(tmp), _make_xbrl(""))
            result = extract_depreciation(xbrl_dir)
        self.assertIsNone(result["current"])
        self.assertEqual(result["method"], "not_found")


class TestExtractDepreciationIFRS(unittest.TestCase):
    _IFRS_MARKER = (
        '<jpifrs_cor:BorrowingsNCLIFRS contextRef="CurrentYearInstant" decimals="-6" unitRef="JPY">100000000000</jpifrs_cor:BorrowingsNCLIFRS>'
    )

    def test_ifrs_consolidated_current(self):
        with tempfile.TemporaryDirectory() as tmp:
            xbrl_dir = _write_xbrl(
                Path(tmp),
                _make_xbrl(
                    self._IFRS_MARKER + "\n"
                    '<jpigp_cor:DepreciationAndAmortizationOpeCFIFRS contextRef="CurrentYearDuration" decimals="-6" unitRef="JPY">133784000000</jpigp_cor:DepreciationAndAmortizationOpeCFIFRS>'
                ),
            )
            result = extract_depreciation(xbrl_dir)
        self.assertEqual(result["current"], 133784000000.0)
        self.assertEqual(result["accounting_standard"], "IFRS")
        self.assertEqual(result["method"], "direct")


if __name__ == "__main__":
    unittest.main()
