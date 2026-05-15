"""
有形固定資産（PPE）抽出テスト

3社の実XBRLキャッシュ値を期待値として検証する。
  味の素（IFRS, E00436）: PropertyPlantAndEquipmentIFRS 系タグ
  日立（IFRS, E01737）  : 同上。使用権資産によりその他が大きい
  大日本印刷（J-GAAP, E00693）: BuildingsAndStructuresNet 系タグ
"""

import tempfile
from pathlib import Path

import pytest

from blue_ticker.analysis.sections import BalanceSheetSection
from blue_ticker.analysis.tangible_fixed_assets import extract_tangible_fixed_assets
from blue_ticker.constants.financial import MILLION_YEN

NS_XBRLI = "http://www.xbrl.org/2003/instance"
NS_JPPFS = "http://disclosure.edinet-fsa.go.jp/taxonomy/jppfs/2024-11-01/jppfs_cor"
NS_JPIGP = "http://disclosure.edinet-fsa.go.jp/taxonomy/jpigp/2024-11-01/jpigp_cor"


def _make_xbrl(elements_xml: str, extra_ns: str = "") -> str:
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<xbrli:xbrl
    xmlns:xbrli="{NS_XBRLI}"
    xmlns:jppfs_cor="{NS_JPPFS}"
    xmlns:jpigp_cor="{NS_JPIGP}"{extra_ns}>
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
  <xbrli:unit id="JPY"><xbrli:measure>iso4217:JPY</xbrli:measure></xbrli:unit>
  {elements_xml}
</xbrli:xbrl>"""


def _extract(elements_xml: str) -> dict:
    with tempfile.TemporaryDirectory() as tmp:
        xbrl_dir = Path(tmp)
        (xbrl_dir / "instance.xml").write_text(_make_xbrl(elements_xml), encoding="utf-8")
        section = BalanceSheetSection.from_xbrl(xbrl_dir)
        return extract_tangible_fixed_assets(section)


MN = MILLION_YEN  # 1_000_000


class TestIFRSExtraction:
    """IFRS（味の素・日立相当）の抽出テスト"""

    def test_ajinomoto_values(self):
        """味の素（E00436, 2025-03期）の実値を検証する。"""
        result = _extract("""
            <jpigp_cor:PropertyPlantAndEquipmentIFRS contextRef="CurrentYearInstant" decimals="-6" unitRef="JPY">581330000000</jpigp_cor:PropertyPlantAndEquipmentIFRS>
            <jpigp_cor:BuildingsAndStructuresIFRS contextRef="CurrentYearInstant" decimals="-6" unitRef="JPY">244337000000</jpigp_cor:BuildingsAndStructuresIFRS>
            <jpigp_cor:LandIFRS contextRef="CurrentYearInstant" decimals="-6" unitRef="JPY">46252000000</jpigp_cor:LandIFRS>
            <jpigp_cor:MachineryAndVehiclesIFRS contextRef="CurrentYearInstant" decimals="-6" unitRef="JPY">212696000000</jpigp_cor:MachineryAndVehiclesIFRS>
            <jpigp_cor:ToolsFurnitureAndFixturesIFRS contextRef="CurrentYearInstant" decimals="-6" unitRef="JPY">23870000000</jpigp_cor:ToolsFurnitureAndFixturesIFRS>
            <jpigp_cor:ConstructionInProgressIFRS contextRef="CurrentYearInstant" decimals="-6" unitRef="JPY">54172000000</jpigp_cor:ConstructionInProgressIFRS>
        """)

        assert result["accounting_standard"] == "IFRS"
        assert result["method"] == "field_parser"
        assert result["total"] == pytest.approx(581_330 * MN)
        assert result["buildings"] == pytest.approx(244_337 * MN)
        assert result["land"] == pytest.approx(46_252 * MN)
        assert result["machinery"] == pytest.approx(212_696 * MN)
        assert result["tools"] == pytest.approx(23_870 * MN)
        assert result["construction_in_progress"] == pytest.approx(54_172 * MN)
        # others ≈ 3（rounding、実質ゼロ）
        assert result["others"] == pytest.approx(3 * MN, abs=5 * MN)

    def test_hitachi_values(self):
        """日立（E01737, 2025-03期）の実値を検証する。使用権資産によりその他が大きい。"""
        result = _extract("""
            <jpigp_cor:PropertyPlantAndEquipmentIFRS contextRef="CurrentYearInstant" decimals="-6" unitRef="JPY">1341537000000</jpigp_cor:PropertyPlantAndEquipmentIFRS>
            <jpigp_cor:BuildingsAndStructuresIFRS contextRef="CurrentYearInstant" decimals="-6" unitRef="JPY">452774000000</jpigp_cor:BuildingsAndStructuresIFRS>
            <jpigp_cor:LandIFRS contextRef="CurrentYearInstant" decimals="-6" unitRef="JPY">93953000000</jpigp_cor:LandIFRS>
            <jpigp_cor:MachineryAndVehiclesIFRS contextRef="CurrentYearInstant" decimals="-6" unitRef="JPY">242157000000</jpigp_cor:MachineryAndVehiclesIFRS>
            <jpigp_cor:ToolsFurnitureAndFixturesIFRS contextRef="CurrentYearInstant" decimals="-6" unitRef="JPY">141718000000</jpigp_cor:ToolsFurnitureAndFixturesIFRS>
            <jpigp_cor:ConstructionInProgressIFRS contextRef="CurrentYearInstant" decimals="-6" unitRef="JPY">151158000000</jpigp_cor:ConstructionInProgressIFRS>
        """)

        assert result["accounting_standard"] == "IFRS"
        assert result["total"] == pytest.approx(1_341_537 * MN)
        assert result["buildings"] == pytest.approx(452_774 * MN)
        assert result["land"] == pytest.approx(93_953 * MN)
        assert result["machinery"] == pytest.approx(242_157 * MN)
        assert result["tools"] == pytest.approx(141_718 * MN)
        assert result["construction_in_progress"] == pytest.approx(151_158 * MN)
        # others = 使用権資産(250,217) + その他(9,560) = 259,777
        assert result["others"] == pytest.approx(259_777 * MN)

    def test_prior_year_values(self):
        """前期値も正しく取得できることを確認する。"""
        result = _extract("""
            <jpigp_cor:PropertyPlantAndEquipmentIFRS contextRef="CurrentYearInstant" decimals="-6" unitRef="JPY">581330000000</jpigp_cor:PropertyPlantAndEquipmentIFRS>
            <jpigp_cor:PropertyPlantAndEquipmentIFRS contextRef="Prior1YearInstant" decimals="-6" unitRef="JPY">587407000000</jpigp_cor:PropertyPlantAndEquipmentIFRS>
            <jpigp_cor:BuildingsAndStructuresIFRS contextRef="CurrentYearInstant" decimals="-6" unitRef="JPY">244337000000</jpigp_cor:BuildingsAndStructuresIFRS>
            <jpigp_cor:BuildingsAndStructuresIFRS contextRef="Prior1YearInstant" decimals="-6" unitRef="JPY">254914000000</jpigp_cor:BuildingsAndStructuresIFRS>
            <jpigp_cor:LandIFRS contextRef="CurrentYearInstant" decimals="-6" unitRef="JPY">46252000000</jpigp_cor:LandIFRS>
            <jpigp_cor:MachineryAndVehiclesIFRS contextRef="CurrentYearInstant" decimals="-6" unitRef="JPY">212696000000</jpigp_cor:MachineryAndVehiclesIFRS>
            <jpigp_cor:ToolsFurnitureAndFixturesIFRS contextRef="CurrentYearInstant" decimals="-6" unitRef="JPY">23870000000</jpigp_cor:ToolsFurnitureAndFixturesIFRS>
            <jpigp_cor:ConstructionInProgressIFRS contextRef="CurrentYearInstant" decimals="-6" unitRef="JPY">54172000000</jpigp_cor:ConstructionInProgressIFRS>
        """)

        assert result["total"] == pytest.approx(581_330 * MN)
        assert result["buildings"] == pytest.approx(244_337 * MN)


class TestJGAAPExtraction:
    """J-GAAP（大日本印刷相当）の抽出テスト"""

    def test_dnp_values(self):
        """大日本印刷（E00693, 2025-03期）の実値を検証する。工具器具及び備品は連結で未開示。"""
        result = _extract("""
            <jppfs_cor:PropertyPlantAndEquipment contextRef="CurrentYearInstant" decimals="-6" unitRef="JPY">405795000000</jppfs_cor:PropertyPlantAndEquipment>
            <jppfs_cor:BuildingsAndStructuresNet contextRef="CurrentYearInstant" decimals="-6" unitRef="JPY">151499000000</jppfs_cor:BuildingsAndStructuresNet>
            <jppfs_cor:Land contextRef="CurrentYearInstant" decimals="-6" unitRef="JPY">141787000000</jppfs_cor:Land>
            <jppfs_cor:MachineryEquipmentAndVehiclesNet contextRef="CurrentYearInstant" decimals="-6" unitRef="JPY">61072000000</jppfs_cor:MachineryEquipmentAndVehiclesNet>
            <jppfs_cor:ConstructionInProgress contextRef="CurrentYearInstant" decimals="-6" unitRef="JPY">17607000000</jppfs_cor:ConstructionInProgress>
        """)

        assert result["accounting_standard"] == "J-GAAP"
        assert result["method"] == "field_parser"
        assert result["total"] == pytest.approx(405_795 * MN)
        assert result["buildings"] == pytest.approx(151_499 * MN)
        assert result["land"] == pytest.approx(141_787 * MN)
        assert result["machinery"] == pytest.approx(61_072 * MN)
        assert result["tools"] is None  # 連結XBRLに ToolsFurnitureAndFixturesNet なし
        assert result["construction_in_progress"] == pytest.approx(17_607 * MN)
        # others = 405,795 - (151,499 + 141,787 + 61,072 + 17,607) = 33,830
        assert result["others"] == pytest.approx(33_830 * MN)

    def test_jgaap_uses_net_tags_not_acquisition_cost(self):
        """BuildingsAndStructures（取得原価）ではなくNet（帳簿価額）タグを優先することを確認する。"""
        result = _extract("""
            <jppfs_cor:PropertyPlantAndEquipment contextRef="CurrentYearInstant" decimals="-6" unitRef="JPY">200000000000</jppfs_cor:PropertyPlantAndEquipment>
            <jppfs_cor:BuildingsAndStructures contextRef="CurrentYearInstant" decimals="-6" unitRef="JPY">500000000000</jppfs_cor:BuildingsAndStructures>
            <jppfs_cor:BuildingsAndStructuresNet contextRef="CurrentYearInstant" decimals="-6" unitRef="JPY">150000000000</jppfs_cor:BuildingsAndStructuresNet>
            <jppfs_cor:Land contextRef="CurrentYearInstant" decimals="-6" unitRef="JPY">50000000000</jppfs_cor:Land>
        """)

        # BuildingsAndStructuresNet（帳簿価額）が採用されること
        assert result["buildings"] == pytest.approx(150_000 * MN)


class TestCostMinusDepreciation:
    """取得原価 - 累計減価償却による差引計算フォールバックのテスト（トヨタ相当）"""

    def test_toyota_values(self):
        """トヨタ自動車（E02144, 2025-03期）の実値を検証する。直接帳簿価額タグなし、差引計算で取得。"""
        result = _extract("""
            <jpigp_cor:PropertyPlantAndEquipmentIFRS contextRef="CurrentYearInstant" decimals="-6" unitRef="JPY">15333693000000</jpigp_cor:PropertyPlantAndEquipmentIFRS>
            <jpigp_cor:BuildingsAcquisitionCostIFRS contextRef="CurrentYearInstant" decimals="-6" unitRef="JPY">6170063000000</jpigp_cor:BuildingsAcquisitionCostIFRS>
            <jpigp_cor:BuildingsAccumulatedDepreciationAndImpairmentLossesIFRS contextRef="CurrentYearInstant" decimals="-6" unitRef="JPY">-3867037000000</jpigp_cor:BuildingsAccumulatedDepreciationAndImpairmentLossesIFRS>
            <jpigp_cor:LandAcquisitionCostIFRS contextRef="CurrentYearInstant" decimals="-6" unitRef="JPY">1428122000000</jpigp_cor:LandAcquisitionCostIFRS>
            <jpigp_cor:LandAccumulatedImpairmentLossesIFRS contextRef="CurrentYearInstant" decimals="-6" unitRef="JPY">-6927000000</jpigp_cor:LandAccumulatedImpairmentLossesIFRS>
            <jpigp_cor:MachineryAndEquipmentAcquisitionCostIFRS contextRef="CurrentYearInstant" decimals="-6" unitRef="JPY">16621243000000</jpigp_cor:MachineryAndEquipmentAcquisitionCostIFRS>
            <jpigp_cor:MachineryAndEquipmentAccumulatedDepreciationAndImpairmentLossesIFRS contextRef="CurrentYearInstant" decimals="-6" unitRef="JPY">-13157598000000</jpigp_cor:MachineryAndEquipmentAccumulatedDepreciationAndImpairmentLossesIFRS>
            <jpigp_cor:ConstructionInProgressAcquisitionCostIFRS contextRef="CurrentYearInstant" decimals="-6" unitRef="JPY">1596145000000</jpigp_cor:ConstructionInProgressAcquisitionCostIFRS>
            <jpigp_cor:ConstructionInProgressAccumulatedImpairmentLossesIFRS contextRef="CurrentYearInstant" decimals="-6" unitRef="JPY">-3678000000</jpigp_cor:ConstructionInProgressAccumulatedImpairmentLossesIFRS>
        """)

        assert result["accounting_standard"] == "IFRS"
        assert result["method"] == "field_parser"
        assert result["total"] == pytest.approx(15_333_693 * MN)
        assert result["buildings"] == pytest.approx((6_170_063 - 3_867_037) * MN)   # 2,303,026
        assert result["land"] == pytest.approx((1_428_122 - 6_927) * MN)             # 1,421,195
        assert result["machinery"] == pytest.approx((16_621_243 - 13_157_598) * MN)  # 3,463,645
        assert result["tools"] is None
        assert result["construction_in_progress"] == pytest.approx((1_596_145 - 3_678) * MN)  # 1,592,467

    def test_direct_tag_takes_priority_over_cost_calculation(self):
        """直接帳簿価額タグがある場合は取得原価計算より優先されることを確認する。"""
        result = _extract("""
            <jpigp_cor:PropertyPlantAndEquipmentIFRS contextRef="CurrentYearInstant" decimals="-6" unitRef="JPY">500000000000</jpigp_cor:PropertyPlantAndEquipmentIFRS>
            <jpigp_cor:BuildingsAndStructuresIFRS contextRef="CurrentYearInstant" decimals="-6" unitRef="JPY">100000000000</jpigp_cor:BuildingsAndStructuresIFRS>
            <jpigp_cor:BuildingsAcquisitionCostIFRS contextRef="CurrentYearInstant" decimals="-6" unitRef="JPY">300000000000</jpigp_cor:BuildingsAcquisitionCostIFRS>
            <jpigp_cor:BuildingsAccumulatedDepreciationAndImpairmentLossesIFRS contextRef="CurrentYearInstant" decimals="-6" unitRef="JPY">-150000000000</jpigp_cor:BuildingsAccumulatedDepreciationAndImpairmentLossesIFRS>
        """)

        # BuildingsAndStructuresIFRS（直接タグ）が採用されること
        assert result["buildings"] == pytest.approx(100_000 * MN)

    def test_total_fallback_to_cost_calculation(self):
        """合計の直接タグがない場合も取得原価計算でフォールバックすることを確認する。"""
        result = _extract("""
            <jpigp_cor:PropertyPlantAndEquipmentAcquisitionCostIFRS contextRef="CurrentYearInstant" decimals="-6" unitRef="JPY">33867518000000</jpigp_cor:PropertyPlantAndEquipmentAcquisitionCostIFRS>
            <jpigp_cor:PropertyPlantAndEquipmentAccumulatedDepreciationAndImpairmentLossesIFRS contextRef="CurrentYearInstant" decimals="-6" unitRef="JPY">-18533826000000</jpigp_cor:PropertyPlantAndEquipmentAccumulatedDepreciationAndImpairmentLossesIFRS>
        """)

        assert result["method"] == "field_parser"
        assert result["total"] == pytest.approx((33_867_518 - 18_533_826) * MN)  # 15,333,692


class TestNotFound:
    """タグが存在しない場合のフォールバック検証"""

    def test_returns_not_found_when_no_ppe_tags(self):
        result = _extract("""
            <jppfs_cor:CurrentAssets contextRef="CurrentYearInstant" decimals="-6" unitRef="JPY">1000000000000</jppfs_cor:CurrentAssets>
        """)

        assert result["method"] == "not_found"
        assert result["total"] is None
        assert result["buildings"] is None
        assert result["others"] is None

    def test_others_is_none_when_total_is_none(self):
        """合計が取得できない場合、その他も None になることを確認する。"""
        result = _extract("")
        assert result["total"] is None
        assert result["others"] is None
