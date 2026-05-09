from pathlib import Path

from blue_ticker.analysis.xbrl_utils import filter_fact_index_by_sections
from blue_ticker.services.edinet_fetcher import _preparsed_for_statement
from blue_ticker.utils.xbrl_result_types import XbrlFact, XbrlFactIndex, XbrlTagElements


def _fact(
    tag: str,
    context_ref: str,
    value: float,
    section: str,
    consolidation: str,
) -> XbrlFact:
    return {
        "tag": tag,
        "contextRef": context_ref,
        "value": value,
        "section": section,
        "sections": [section],
        "consolidation": consolidation,
    }


def test_filter_fact_index_prefers_consolidated_statement_sections() -> None:
    facts: XbrlFactIndex = {
        "NetSales": {
            "CurrentYearDuration": _fact(
                "NetSales",
                "CurrentYearDuration",
                100.0,
                "ConsolidatedStatementOfIncome",
                "consolidated",
            ),
            "CurrentYearDuration_NonConsolidatedMember": _fact(
                "NetSales",
                "CurrentYearDuration_NonConsolidatedMember",
                10.0,
                "StatementOfIncome",
                "non_consolidated",
            ),
        }
    }

    filtered = filter_fact_index_by_sections(
        facts,
        ("ConsolidatedStatementOfIncome",),
        ("StatementOfIncome",),
    )

    assert list(filtered["NetSales"].keys()) == ["CurrentYearDuration"]


def test_filter_fact_index_uses_nonconsolidated_statement_as_explicit_fallback() -> None:
    facts: XbrlFactIndex = {
        "NetSales": {
            "CurrentYearDuration_NonConsolidatedMember": _fact(
                "NetSales",
                "CurrentYearDuration_NonConsolidatedMember",
                10.0,
                "StatementOfIncome",
                "non_consolidated",
            ),
        }
    }

    filtered = filter_fact_index_by_sections(
        facts,
        ("ConsolidatedStatementOfIncome",),
        ("StatementOfIncome",),
    )

    assert filtered["NetSales"]["CurrentYearDuration_NonConsolidatedMember"]["value"] == 10.0


def test_preparsed_for_statement_returns_statement_scoped_numeric_index() -> None:
    all_numeric: XbrlTagElements = {
        "NetSales": {
            "CurrentYearDuration": 100.0,
            "CurrentYearDuration_NonConsolidatedMember": 10.0,
        }
    }
    facts: XbrlFactIndex = {
        "NetSales": {
            "CurrentYearDuration": _fact(
                "NetSales",
                "CurrentYearDuration",
                100.0,
                "ConsolidatedStatementOfIncome",
                "consolidated",
            ),
            "CurrentYearDuration_NonConsolidatedMember": _fact(
                "NetSales",
                "CurrentYearDuration_NonConsolidatedMember",
                10.0,
                "StatementOfIncome",
                "non_consolidated",
            ),
        }
    }

    scoped = _preparsed_for_statement((Path("."), all_numeric, facts), "gp")

    assert scoped == {"NetSales": {"CurrentYearDuration": 100.0}}


def test_preparsed_for_statement_keeps_all_numeric_when_no_section_metadata() -> None:
    all_numeric: XbrlTagElements = {"NetSales": {"CurrentYearDuration": 100.0}}

    scoped = _preparsed_for_statement((Path("."), all_numeric, {}), "gp")

    assert scoped is all_numeric
