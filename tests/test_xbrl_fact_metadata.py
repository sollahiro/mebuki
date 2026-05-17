from pathlib import Path

from blue_ticker.analysis.xbrl_utils import (
    collect_all_numeric_facts,
    collect_numeric_elements,
    fact_index_to_numeric_elements,
)
from blue_ticker.services._xbrl_parse_cache import _numeric_elements_from_xbrl_parse_cache


def _write_minimal_xbrl_files(tmp_path: Path) -> Path:
    xbrl_dir = tmp_path / "xbrl"
    xbrl_dir.mkdir()
    (xbrl_dir / "sample.xbrl").write_text(
        """<?xml version="1.0" encoding="UTF-8"?>
<xbrli:xbrl
  xmlns:xbrli="http://www.xbrl.org/2003/instance"
  xmlns:jppfs_cor="http://disclosure.edinet-fsa.go.jp/taxonomy/jppfs/2024-11-01/jppfs_cor">
  <xbrli:context id="CurrentYearDuration">
    <xbrli:entity><xbrli:identifier scheme="test">E00000</xbrli:identifier></xbrli:entity>
    <xbrli:period><xbrli:startDate>2024-04-01</xbrli:startDate><xbrli:endDate>2025-03-31</xbrli:endDate></xbrli:period>
  </xbrli:context>
  <xbrli:context id="CurrentYearDuration_NonConsolidatedMember">
    <xbrli:entity><xbrli:identifier scheme="test">E00000</xbrli:identifier></xbrli:entity>
    <xbrli:period><xbrli:startDate>2024-04-01</xbrli:startDate><xbrli:endDate>2025-03-31</xbrli:endDate></xbrli:period>
  </xbrli:context>
  <jppfs_cor:NetSales contextRef="CurrentYearDuration" unitRef="JPY" decimals="-6">123000000</jppfs_cor:NetSales>
  <jppfs_cor:NetSales contextRef="CurrentYearDuration_NonConsolidatedMember" unitRef="JPY" decimals="-3">45000000</jppfs_cor:NetSales>
</xbrli:xbrl>
""",
        encoding="utf-8",
    )
    (xbrl_dir / "sample_lab.xml").write_text(
        """<?xml version="1.0" encoding="UTF-8"?>
<link:linkbase xmlns:link="http://www.xbrl.org/2003/linkbase" xmlns:xlink="http://www.w3.org/1999/xlink">
  <link:labelLink xlink:type="extended" xlink:role="http://www.xbrl.org/2003/role/link">
    <link:loc xlink:type="locator" xlink:href="taxonomy.xsd#jppfs_cor_NetSales" xlink:label="jppfs_cor_NetSales" />
    <link:label xml:lang="ja" xlink:type="resource" xlink:label="net_sales_label" xlink:role="http://www.xbrl.org/2003/role/label">売上高</link:label>
    <link:labelArc xlink:type="arc" xlink:from="jppfs_cor_NetSales" xlink:to="net_sales_label" xlink:arcrole="http://www.xbrl.org/2003/arcrole/concept-label" order="1" />
  </link:labelLink>
</link:linkbase>
""",
        encoding="utf-8",
    )
    (xbrl_dir / "sample_pre.xml").write_text(
        """<?xml version="1.0" encoding="UTF-8"?>
<link:linkbase xmlns:link="http://www.xbrl.org/2003/linkbase" xmlns:xlink="http://www.w3.org/1999/xlink">
  <link:presentationLink xlink:type="extended" xlink:role="http://disclosure.edinet-fsa.go.jp/role/jppfs/rol_ConsolidatedStatementOfIncome">
    <link:loc xlink:type="locator" xlink:href="taxonomy.xsd#jppfs_cor_NetSales" xlink:label="jppfs_cor_NetSales" />
  </link:presentationLink>
</link:linkbase>
""",
        encoding="utf-8",
    )
    return xbrl_dir


def test_collect_all_numeric_facts_preserves_fact_metadata(tmp_path: Path) -> None:
    xbrl_dir = _write_minimal_xbrl_files(tmp_path)

    facts = collect_all_numeric_facts(xbrl_dir)

    fact = facts["NetSales"]["CurrentYearDuration"]
    assert fact["tag"] == "NetSales"
    assert fact["contextRef"] == "CurrentYearDuration"
    assert fact.get("unitRef") == "JPY"
    assert fact.get("decimals") == "-6"
    assert fact["value"] == 123_000_000.0
    assert fact.get("label") == "売上高"
    assert fact.get("role") == "http://disclosure.edinet-fsa.go.jp/role/jppfs/rol_ConsolidatedStatementOfIncome"
    assert fact.get("section") == "ConsolidatedStatementOfIncome"
    assert fact["consolidation"] == "consolidated"

    non_consolidated = facts["NetSales"]["CurrentYearDuration_NonConsolidatedMember"]
    assert non_consolidated["consolidation"] == "non_consolidated"


def test_fact_index_converts_to_existing_numeric_index(tmp_path: Path) -> None:
    xbrl_dir = _write_minimal_xbrl_files(tmp_path)

    facts = collect_all_numeric_facts(xbrl_dir)
    numeric = fact_index_to_numeric_elements(facts)

    assert numeric == {
        "NetSales": {
            "CurrentYearDuration": 123_000_000.0,
            "CurrentYearDuration_NonConsolidatedMember": 45_000_000.0,
        }
    }


def test_collect_numeric_elements_keeps_legacy_shape(tmp_path: Path) -> None:
    xbrl_dir = _write_minimal_xbrl_files(tmp_path)

    numeric = collect_numeric_elements(xbrl_dir / "sample.xbrl")

    assert numeric["NetSales"]["CurrentYearDuration"] == 123_000_000.0


def test_xbrl_parse_cache_reads_fact_index_as_numeric_elements(tmp_path: Path) -> None:
    xbrl_dir = _write_minimal_xbrl_files(tmp_path)
    facts = collect_all_numeric_facts(xbrl_dir)

    numeric = _numeric_elements_from_xbrl_parse_cache(facts)

    assert numeric is not None
    assert numeric["NetSales"]["CurrentYearDuration"] == 123_000_000.0
