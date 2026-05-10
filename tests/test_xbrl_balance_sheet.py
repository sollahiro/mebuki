import tempfile
from pathlib import Path
from typing import Any, cast

import pytest

from blue_ticker.analysis.balance_sheet import extract_balance_sheet
from blue_ticker.constants.financial import MILLION_YEN
from blue_ticker.services.analyzer import _apply_balance_sheet
from blue_ticker.utils.metrics_types import YearEntry

NS_XBRLI = "http://www.xbrl.org/2003/instance"
NS_JPPFS = "http://disclosure.edinet-fsa.go.jp/taxonomy/jppfs/2024-11-01/jppfs_cor"
NS_JPCRP = "http://disclosure.edinet-fsa.go.jp/taxonomy/jpcrp/2024-11-01/jpcrp_cor"


def _make_xbrl(elements_xml: str) -> str:
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<xbrli:xbrl
    xmlns:xbrli="{NS_XBRLI}"
    xmlns:jppfs_cor="{NS_JPPFS}"
    xmlns:jpcrp_cor="{NS_JPCRP}">
  <xbrli:context id="CurrentYearInstant">
    <xbrli:entity>
      <xbrli:identifier scheme="http://disclosure.edinet-fsa.go.jp">E12345</xbrli:identifier>
    </xbrli:entity>
    <xbrli:period><xbrli:instant>2025-03-31</xbrli:instant></xbrli:period>
  </xbrli:context>
  <xbrli:context id="Prior1YearInstant">
    <xbrli:entity>
      <xbrli:identifier scheme="http://disclosure.edinet-fsa.go.jp">E12345</xbrli:identifier>
    </xbrli:entity>
    <xbrli:period><xbrli:instant>2024-03-31</xbrli:instant></xbrli:period>
  </xbrli:context>
  <xbrli:context id="CurrentYearInstant_NonConsolidatedMember">
    <xbrli:entity>
      <xbrli:identifier scheme="http://disclosure.edinet-fsa.go.jp">E12345</xbrli:identifier>
    </xbrli:entity>
    <xbrli:period><xbrli:instant>2025-03-31</xbrli:instant></xbrli:period>
  </xbrli:context>
  <xbrli:unit id="JPY"><xbrli:measure>iso4217:JPY</xbrli:measure></xbrli:unit>
  {elements_xml}
</xbrli:xbrl>"""


def _write_xbrl(xbrl_dir: Path, elements_xml: str) -> None:
    (xbrl_dir / "instance.xml").write_text(_make_xbrl(elements_xml), encoding="utf-8")


class TestBalanceSheetExtraction:
    def test_extracts_jgaap_balance_sheet_components(self):
        with tempfile.TemporaryDirectory() as tmp:
            xbrl_dir = Path(tmp)
            _write_xbrl(
                xbrl_dir,
                """
                <jppfs_cor:CurrentAssets contextRef="CurrentYearInstant" unitRef="JPY">2923181000000</jppfs_cor:CurrentAssets>
                <jppfs_cor:NoncurrentAssets contextRef="CurrentYearInstant" unitRef="JPY">3281728000000</jppfs_cor:NoncurrentAssets>
                <jppfs_cor:CurrentLiabilities contextRef="CurrentYearInstant" unitRef="JPY">1770928000000</jppfs_cor:CurrentLiabilities>
                <jppfs_cor:NoncurrentLiabilities contextRef="CurrentYearInstant" unitRef="JPY">1560957000000</jppfs_cor:NoncurrentLiabilities>
                <jppfs_cor:NetAssets contextRef="CurrentYearInstant" unitRef="JPY">2873024000000</jppfs_cor:NetAssets>
                <jppfs_cor:TotalAssets contextRef="CurrentYearInstant" unitRef="JPY">6204909000000</jppfs_cor:TotalAssets>
                <jppfs_cor:NetAssets contextRef="CurrentYearInstant_NonControllingInterestsMember" unitRef="JPY">250039000000</jppfs_cor:NetAssets>
                """,
            )

            result = extract_balance_sheet(xbrl_dir)

        assert result["accounting_standard"] == "J-GAAP"
        assert result["method"] == "field_parser"
        assert result["current_assets"] == pytest.approx(2_923_181 * MILLION_YEN)
        assert result["non_current_assets"] == pytest.approx(3_281_728 * MILLION_YEN)
        assert result["total_assets"] == pytest.approx(6_204_909 * MILLION_YEN)
        assert result["current_liabilities"] == pytest.approx(1_770_928 * MILLION_YEN)
        assert result["non_current_liabilities"] == pytest.approx(1_560_957 * MILLION_YEN)
        assert result["net_assets"] == pytest.approx(2_873_024 * MILLION_YEN)

    def test_extracts_ifrs_balance_sheet_components(self):
        with tempfile.TemporaryDirectory() as tmp:
            xbrl_dir = Path(tmp)
            _write_xbrl(
                xbrl_dir,
                """
                <jppfs_cor:CurrentAssetsIFRS contextRef="CurrentYearInstant" unitRef="JPY">6597843000000</jppfs_cor:CurrentAssetsIFRS>
                <jppfs_cor:NonCurrentAssetsIFRS contextRef="CurrentYearInstant" unitRef="JPY">6686970000000</jppfs_cor:NonCurrentAssetsIFRS>
                <jppfs_cor:TotalCurrentLiabilitiesIFRS contextRef="CurrentYearInstant" unitRef="JPY">5907845000000</jppfs_cor:TotalCurrentLiabilitiesIFRS>
                <jppfs_cor:LiabilitiesIFRS contextRef="CurrentYearInstant" unitRef="JPY">7253396000000</jppfs_cor:LiabilitiesIFRS>
                <jppfs_cor:EquityIFRS contextRef="CurrentYearInstant" unitRef="JPY">6031417000000</jppfs_cor:EquityIFRS>
                """,
            )

            result = extract_balance_sheet(xbrl_dir)

        assert result["accounting_standard"] == "IFRS"
        assert result["current_assets"] == pytest.approx(6_597_843 * MILLION_YEN)
        assert result["non_current_assets"] == pytest.approx(6_686_970 * MILLION_YEN)
        assert result["current_liabilities"] == pytest.approx(5_907_845 * MILLION_YEN)
        assert result["non_current_liabilities"] == pytest.approx(1_345_551 * MILLION_YEN)
        assert result["net_assets"] == pytest.approx(6_031_417 * MILLION_YEN)

    def test_computes_usgaap_non_current_assets_from_components(self):
        with tempfile.TemporaryDirectory() as tmp:
            xbrl_dir = Path(tmp)
            _write_xbrl(
                xbrl_dir,
                """
                <jppfs_cor:CurrentAssetsUSGAAP contextRef="CurrentYearInstant" unitRef="JPY">1581681000000</jppfs_cor:CurrentAssetsUSGAAP>
                <jppfs_cor:InvestmentsAndLongTermReceivablesUSGAAP contextRef="CurrentYearInstant" unitRef="JPY">1398318000000</jppfs_cor:InvestmentsAndLongTermReceivablesUSGAAP>
                <jppfs_cor:PropertyPlantAndEquipmentNetUSGAAP contextRef="CurrentYearInstant" unitRef="JPY">1785062000000</jppfs_cor:PropertyPlantAndEquipmentNetUSGAAP>
                <jppfs_cor:OtherAssetsUSGAAP contextRef="CurrentYearInstant" unitRef="JPY">484957000000</jppfs_cor:OtherAssetsUSGAAP>
                <jppfs_cor:CurrentLiabilitiesUSGAAP contextRef="CurrentYearInstant" unitRef="JPY">1125940000000</jppfs_cor:CurrentLiabilitiesUSGAAP>
                <jppfs_cor:LongTermLiabilitiesUSGAAP contextRef="CurrentYearInstant" unitRef="JPY">771286000000</jppfs_cor:LongTermLiabilitiesUSGAAP>
                <jppfs_cor:TotalEquityUSGAAP contextRef="CurrentYearInstant" unitRef="JPY">3352682000000</jppfs_cor:TotalEquityUSGAAP>
                """,
            )

            result = extract_balance_sheet(xbrl_dir)

        assert result["accounting_standard"] == "US-GAAP"
        assert result["current_assets"] == pytest.approx(1_581_681 * MILLION_YEN)
        assert result["non_current_assets"] == pytest.approx(3_668_337 * MILLION_YEN)
        assert result["current_liabilities"] == pytest.approx(1_125_940 * MILLION_YEN)
        assert result["non_current_liabilities"] == pytest.approx(771_286 * MILLION_YEN)
        assert result["net_assets"] == pytest.approx(3_352_682 * MILLION_YEN)
        assert "InvestmentsAndLongTermReceivablesUSGAAP" in (result["components"][2]["tag"] or "")

    def test_uses_usgaap_html_balance_sheet_rows_when_xbrl_has_only_summary(self):
        html = """
        <html><body><table>
          <tr><td>流動資産合計</td><td>1,574,628</td><td>1,581,681</td></tr>
          <tr><td>投資及び長期債権合計</td><td>207,877</td><td>209,294</td></tr>
          <tr><td>有形固定資産合計</td><td>1,395,735</td><td>1,786,475</td></tr>
          <tr><td>その他の資産合計</td><td>1,605,220</td><td>1,672,458</td></tr>
          <tr><td>流動負債合計</td><td>1,165,841</td><td>1,125,940</td></tr>
          <tr><td>固定負債合計</td><td>444,304</td><td>771,286</td></tr>
          <tr><td>純資産合計</td><td>3,173,315</td><td>3,352,682</td></tr>
        </table></body></html>
        """
        with tempfile.TemporaryDirectory() as tmp:
            xbrl_dir = Path(tmp)
            _write_xbrl(
                xbrl_dir,
                """
                <jpcrp_cor:EquityAttributableToOwnersOfParentUSGAAPSummaryOfBusinessResults
                    contextRef="CurrentYearInstant" unitRef="JPY">3348480000000</jpcrp_cor:EquityAttributableToOwnersOfParentUSGAAPSummaryOfBusinessResults>
                """,
            )
            (xbrl_dir / "0105010_honbun_ixbrl.htm").write_text(html, encoding="utf-8")

            result = extract_balance_sheet(xbrl_dir)

        assert result["current_assets"] == pytest.approx(1_581_681 * MILLION_YEN)
        assert result["non_current_assets"] == pytest.approx(3_668_227 * MILLION_YEN)
        assert result["current_liabilities"] == pytest.approx(1_125_940 * MILLION_YEN)
        assert result["non_current_liabilities"] == pytest.approx(771_286 * MILLION_YEN)
        assert result["net_assets"] == pytest.approx(3_352_682 * MILLION_YEN)

    def test_prefers_usgaap_total_equity_summary_over_parent_equity_summary(self):
        with tempfile.TemporaryDirectory() as tmp:
            xbrl_dir = Path(tmp)
            _write_xbrl(
                xbrl_dir,
                """
                <jpcrp_cor:EquityIncludingPortionAttributableToNonControllingInterestUSGAAPSummaryOfBusinessResults
                    contextRef="CurrentYearInstant" unitRef="JPY">3352682000000</jpcrp_cor:EquityIncludingPortionAttributableToNonControllingInterestUSGAAPSummaryOfBusinessResults>
                <jpcrp_cor:EquityAttributableToOwnersOfParentUSGAAPSummaryOfBusinessResults
                    contextRef="CurrentYearInstant" unitRef="JPY">3348480000000</jpcrp_cor:EquityAttributableToOwnersOfParentUSGAAPSummaryOfBusinessResults>
                """,
            )

            result = extract_balance_sheet(xbrl_dir)

        assert result["net_assets"] == pytest.approx(3_352_682 * MILLION_YEN)

    def test_partial_aggregate_label_shows_actual_tag(self):
        with tempfile.TemporaryDirectory() as tmp:
            xbrl_dir = Path(tmp)
            _write_xbrl(
                xbrl_dir,
                """
                <jppfs_cor:OtherAssetsUSGAAP contextRef="CurrentYearInstant" unitRef="JPY">484957000000</jppfs_cor:OtherAssetsUSGAAP>
                """,
            )

            result = extract_balance_sheet(xbrl_dir)

        assert result["components"][2]["tag"] == "OtherAssetsUSGAAP"

    def test_single_entity_uses_plain_context(self):
        """単体のみ企業（_NonConsolidatedMember なし）は plain context のBS値を返す"""
        with tempfile.TemporaryDirectory() as tmp:
            xbrl_dir = Path(tmp)
            _write_xbrl(
                xbrl_dir,
                """
                <jppfs_cor:CurrentAssets contextRef="CurrentYearInstant" unitRef="JPY">184600000000</jppfs_cor:CurrentAssets>
                <jppfs_cor:NoncurrentAssets contextRef="CurrentYearInstant" unitRef="JPY">113568000000</jppfs_cor:NoncurrentAssets>
                <jppfs_cor:CurrentLiabilities contextRef="CurrentYearInstant" unitRef="JPY">42737000000</jppfs_cor:CurrentLiabilities>
                <jppfs_cor:NoncurrentLiabilities contextRef="CurrentYearInstant" unitRef="JPY">60103000000</jppfs_cor:NoncurrentLiabilities>
                <jppfs_cor:NetAssets contextRef="CurrentYearInstant" unitRef="JPY">238065000000</jppfs_cor:NetAssets>
                """,
            )

            result = extract_balance_sheet(xbrl_dir)

        assert result["current_assets"] == pytest.approx(184_600 * MILLION_YEN)
        assert result["non_current_assets"] == pytest.approx(113_568 * MILLION_YEN)
        assert result["current_liabilities"] == pytest.approx(42_737 * MILLION_YEN)
        assert result["non_current_liabilities"] == pytest.approx(60_103 * MILLION_YEN)
        assert result["net_assets"] == pytest.approx(238_065 * MILLION_YEN)


class TestApplyBalanceSheet:
    def test_sets_balance_sheet_fields_in_millions(self):
        years = cast(list[YearEntry], [{"fy_end": "2025-03-31", "CalculatedData": {}, "RawData": {}}])
        _apply_balance_sheet(
            years,
            {
                "20250331": {
                    "current_assets": 164_367_000_000,
                    "total_assets": 194_395_000_000,
                    "non_current_assets": 30_028_000_000,
                    "current_liabilities": 64_401_000_000,
                    "non_current_liabilities": 8_799_000_000,
                    "net_assets": 121_194_000_000,
                    "method": "direct",
                    "accounting_standard": "J-GAAP",
                    "docID": "S100TEST",
                    "components": [{"label": "流動資産", "current": 164_367_000_000, "prior": None}],
                }
            },
        )

        cd = cast(dict[str, Any], years[0]["CalculatedData"])
        assert cd["TotalAssets"] == pytest.approx(194_395)
        assert cd["CurrentAssets"] == pytest.approx(164_367)
        assert cd["NonCurrentAssets"] == pytest.approx(30_028)
        assert cd["CurrentLiabilities"] == pytest.approx(64_401)
        assert cd["NonCurrentLiabilities"] == pytest.approx(8_799)
        assert cd["NetAssets"] == pytest.approx(121_194)
        assert cd["BalanceSheetAccountingStandard"] == "J-GAAP"
        assert cd["MetricSources"]["CurrentAssets"]["docID"] == "S100TEST"
