from pathlib import Path

from blue_ticker.analysis.shareholder_metrics import extract_shareholder_metrics


def test_extract_shareholder_metrics_from_ifrs_summary() -> None:
    result = extract_shareholder_metrics(
        Path("."),
        pre_parsed={
            "CashAndCashEquivalentsIFRS": {
                "CurrentYearInstant": 276_959_000_000.0,
            },
            "BasicEarningsLossPerShareIFRS": {
                "CurrentYearDuration": 163.44,
            },
            "EquityToAssetRatioIFRSSummaryOfBusinessResults": {
                "CurrentYearInstant": 0.42,
            },
            "EquityAttributableToOwnersOfParentPerShareIFRSSummaryOfBusinessResults": {
                "CurrentYearInstant": 2306.8,
            },
            "NumberOfIssuedSharesAsOfFiscalYearEndIssuedSharesTotalNumberOfSharesEtc": {
                "FilingDateInstant": 1_138_716_846.0,
            },
            "DividendPaidPerShareSummaryOfBusinessResults": {
                "CurrentYearDuration_NonConsolidatedMember": 50.0,
            },
            "PayoutRatioSummaryOfBusinessResults": {
                "CurrentYearDuration_NonConsolidatedMember": 0.507,
            },
            "InterimDividendPaidPerShareSummaryOfBusinessResults": {
                "CurrentYearDuration_NonConsolidatedMember": 25.0,
            },
            "TotalAmountOfDividendsDividendsOfSurplus": {
                "FilingDateInstant_Row1Member": 28_460_000_000.0,
                "FilingDateInstant_Row2Member": 28_460_000_000.0,
            },
        },
        net_profit=186_687_000_000.0,
    )

    assert result["CashEq"] == 276_959_000_000.0
    assert result["EPS"] == 163.44
    assert result["BPS"] == 2306.8
    assert result["ShOutFY"] == 1_138_716_846.0
    assert result["DivAnn"] == 50.0
    assert result["Div2Q"] == 25.0
    assert result["DivTotalAnn"] == 56_920_000_000.0
    assert result["PayoutRatioAnn"] == 0.507


def test_extract_shareholder_metrics_prefers_consolidated_per_share_values() -> None:
    result = extract_shareholder_metrics(
        Path("."),
        pre_parsed={
            "BasicEarningsLossPerShareIFRSSummaryOfBusinessResults": {
                "CurrentYearDuration": 69.77,
            },
            "BasicEarningsLossPerShareSummaryOfBusinessResults": {
                "CurrentYearDuration_NonConsolidatedMember": 89.44,
            },
            "EquityToAssetRatioIFRSSummaryOfBusinessResults": {
                "CurrentYearInstant": 751.01,
            },
            "NetAssetsPerShareSummaryOfBusinessResults": {
                "CurrentYearInstant_NonConsolidatedMember": 362.64,
            },
        },
    )

    assert result["EPS"] == 69.77
    assert result["BPS"] == 751.01


def test_extract_shareholder_metrics_prefers_consolidated_cash_equivalents() -> None:
    result = extract_shareholder_metrics(
        Path("."),
        pre_parsed={
            "CashAndCashEquivalentsIFRSSummaryOfBusinessResults": {
                "CurrentYearInstant": 100.0,
                "CurrentYearInstant_NonConsolidatedMember": 10.0,
            },
        },
    )

    assert result["CashEq"] == 100.0


def test_extract_shareholder_metrics_prefers_explicit_bps_tag_over_ratio_named_tag() -> None:
    result = extract_shareholder_metrics(
        Path("."),
        pre_parsed={
            "EquityAttributableToOwnersOfParentPerShareIFRSSummaryOfBusinessResults": {
                "CurrentYearInstant": 2306.8,
            },
            "EquityToAssetRatioIFRSSummaryOfBusinessResults": {
                "CurrentYearInstant": 751.01,
            },
        },
    )

    assert result["BPS"] == 2306.8


def test_extract_shareholder_metrics_falls_back_to_non_consolidated_when_needed() -> None:
    result = extract_shareholder_metrics(
        Path("."),
        pre_parsed={
            "BasicEarningsLossPerShareSummaryOfBusinessResults": {
                "CurrentYearDuration_NonConsolidatedMember": 89.44,
            },
            "NetAssetsPerShareSummaryOfBusinessResults": {
                "CurrentYearInstant_NonConsolidatedMember": 362.64,
            },
        },
    )

    assert result["EPS"] == 89.44
    assert result["BPS"] == 362.64


def test_extract_shareholder_metrics_ignores_ratio_like_bps_values() -> None:
    result = extract_shareholder_metrics(
        Path("."),
        pre_parsed={
            "EquityToAssetRatioIFRSSummaryOfBusinessResults": {
                "CurrentYearInstant": 0.42,
            },
            "NetAssetsPerShareSummaryOfBusinessResults": {
                "CurrentYearInstant_NonConsolidatedMember": 500.0,
            },
        },
    )

    assert result["BPS"] == 500.0


def test_extract_shareholder_metrics_derives_payout_ratio_when_direct_tag_missing() -> None:
    result = extract_shareholder_metrics(
        Path("."),
        pre_parsed={
            "BasicEarningsLossPerShareIFRS": {
                "CurrentYearDuration": 163.44,
            },
            "DividendPaidPerShareSummaryOfBusinessResults": {
                "CurrentYearDuration_NonConsolidatedMember": 50.0,
            },
        },
    )

    assert result["PayoutRatioAnn"] == 0.306


def test_extract_shareholder_metrics_calculates_eps_bps_for_verification() -> None:
    result = extract_shareholder_metrics(
        Path("."),
        pre_parsed={
            "BasicEarningsLossPerShareIFRS": {
                "CurrentYearDuration": 18.25,
            },
            "EquityAttributableToOwnersOfParentPerShareIFRSSummaryOfBusinessResults": {
                "CurrentYearInstant": 98.0,
            },
            "AverageNumberOfSharesDuringPeriodBasicEarningsLossPerShareInformation": {
                "CurrentYearDuration": 100.0,
            },
            "EquityAttributableToOwnersOfParentIFRS": {
                "CurrentYearInstant": 10_000.0,
            },
            "NumberOfIssuedSharesAsOfFiscalYearEndIssuedSharesTotalNumberOfSharesEtc": {
                "FilingDateInstant": 110.0,
            },
            "TotalNumberOfSharesHeldTreasurySharesEtc": {
                "CurrentYearInstant_Row1Member": 10.0,
            },
        },
        net_profit=2_000.0,
    )

    assert result["AverageShares"] == 100.0
    assert result["TreasuryShares"] == 10.0
    assert result["SharesForBPS"] == 100.0
    assert result["ParentEquity"] == 10_000.0
    assert result["CalculatedEPS"] == 20.0
    assert result["CalculatedBPS"] == 100.0
    assert result["EPSDirectDiff"] == -1.75
    assert result["BPSDirectDiff"] == -2.0


def test_extract_shareholder_metrics_does_not_calculate_bps_without_treasury_shares() -> None:
    result = extract_shareholder_metrics(
        Path("."),
        pre_parsed={
            "EquityAttributableToOwnersOfParentIFRS": {
                "CurrentYearInstant": 10_000.0,
            },
            "NumberOfIssuedSharesAsOfFiscalYearEndIssuedSharesTotalNumberOfSharesEtc": {
                "FilingDateInstant": 110.0,
            },
        },
    )

    assert result["TreasuryShares"] is None
    assert result["SharesForBPS"] is None
    assert result["CalculatedBPS"] is None


def test_extract_shareholder_metrics_uses_per_share_textblock_tables(tmp_path: Path) -> None:
    xbrl_file = tmp_path / "sample.xbrl"
    xbrl_file.write_text(
        """
        <xbrli:xbrl xmlns:xbrli="http://www.xbrl.org/2003/instance"
                    xmlns:jpcrp_cor="http://example.com/jpcrp">
          <jpcrp_cor:NotesPerShareInformationConsolidatedFinancialStatementsTextBlock contextRef="CurrentYearDuration">
            &lt;table&gt;
              &lt;tr&gt;&lt;th&gt;&lt;/th&gt;&lt;th&gt;前連結会計年度&lt;/th&gt;&lt;th&gt;当連結会計年度&lt;/th&gt;&lt;/tr&gt;
              &lt;tr&gt;&lt;td&gt;普通株式の期中平均株式数(株)&lt;/td&gt;&lt;td&gt;90&lt;/td&gt;&lt;td&gt;100&lt;/td&gt;&lt;/tr&gt;
              &lt;tr&gt;&lt;td&gt;普通株式の期末株式数(株)&lt;/td&gt;&lt;td&gt;95&lt;/td&gt;&lt;td&gt;100&lt;/td&gt;&lt;/tr&gt;
            &lt;/table&gt;
            &lt;p&gt;普通株式１株につき３株の割合で株式分割を実施しております。&lt;/p&gt;
          </jpcrp_cor:NotesPerShareInformationConsolidatedFinancialStatementsTextBlock>
          <jpcrp_cor:NotesRegardingIssuedSharesAndTreasurySharesTextBlock contextRef="CurrentYearDuration">
            &lt;p&gt;(単位：株)&lt;/p&gt;
            &lt;table&gt;
              &lt;tr&gt;&lt;th&gt;&lt;/th&gt;&lt;th&gt;当期首&lt;/th&gt;&lt;th&gt;増加&lt;/th&gt;&lt;th&gt;減少&lt;/th&gt;&lt;th&gt;当期末&lt;/th&gt;&lt;/tr&gt;
              &lt;tr&gt;&lt;td&gt;自己株式&lt;/td&gt;&lt;td&gt;5&lt;/td&gt;&lt;td&gt;7&lt;/td&gt;&lt;td&gt;2&lt;/td&gt;&lt;td&gt;10&lt;/td&gt;&lt;/tr&gt;
            &lt;/table&gt;
          </jpcrp_cor:NotesRegardingIssuedSharesAndTreasurySharesTextBlock>
        </xbrli:xbrl>
        """,
        encoding="utf-8",
    )

    result = extract_shareholder_metrics(
        tmp_path,
        pre_parsed={
            "BasicEarningsLossPerShareIFRS": {"CurrentYearDuration": 18.25},
            "EquityAttributableToOwnersOfParentPerShareIFRSSummaryOfBusinessResults": {
                "CurrentYearInstant": 98.0,
            },
            "EquityAttributableToOwnersOfParentIFRS": {"CurrentYearInstant": 10_000.0},
            "NumberOfIssuedSharesAsOfFiscalYearEndIssuedSharesTotalNumberOfSharesEtc": {
                "FilingDateInstant": 110.0,
            },
        },
        net_profit=2_000.0,
    )

    assert result["AverageShares"] == 100.0
    assert result["TreasuryShares"] == 10.0
    assert result["SharesForBPS"] == 100.0
    assert result["CalculatedEPS"] == 20.0
    assert result["CalculatedBPS"] == 100.0
    assert result["StockSplitRatio"] == 3.0
    sources = result["MetricSources"]
    assert isinstance(sources, dict)
    assert sources["AverageShares"]["source"] == "fallback"
    assert sources["AverageShares"]["statement"] == "notes"
    assert sources["AverageShares"]["confidence"] == 0.65
    assert sources["CalculatedEPS"]["source"] == "calculated"


def test_extract_shareholder_metrics_keeps_structured_stock_split_events(
    tmp_path: Path,
) -> None:
    xbrl_file = tmp_path / "sample.xbrl"
    xbrl_file.write_text(
        """
        <xbrli:xbrl xmlns:xbrli="http://www.xbrl.org/2003/instance"
                    xmlns:jpcrp_cor="http://example.com/jpcrp">
          <jpcrp_cor:NotesPerShareInformationConsolidatedFinancialStatementsTextBlock contextRef="CurrentYearDuration">
            当社は、2024年９月20日付及び2025年３月１日付でそれぞれ普通株式１株につき５株の割合で株式分割を実施しております。
            １株当たり当期純利益は、第９期の期首に当該株式分割が行われたと仮定して算定しております。
          </jpcrp_cor:NotesPerShareInformationConsolidatedFinancialStatementsTextBlock>
        </xbrli:xbrl>
        """,
        encoding="utf-8",
    )

    result = extract_shareholder_metrics(tmp_path, pre_parsed={})

    assert result["StockSplitRatio"] == 5.0
    assert result["CumulativeStockSplitRatio"] == 25.0
    events = result["StockSplitEvents"]
    assert isinstance(events, list)
    assert [event.get("ratio") for event in events] == [5.0, 5.0]
    assert [event.get("effective_date") for event in events] == [
        "2024-09-20",
        "2025-03-01",
    ]
    assert all(event.get("already_reflected") for event in events)
    assert all(event.get("applies_to") == "per_share_metrics" for event in events)
    sources = result["MetricSources"]
    assert isinstance(sources, dict)
    assert sources["StockSplitEvents"]["method"] == "textblock_events"


def test_extract_shareholder_metrics_uses_split_effective_date_only(
    tmp_path: Path,
) -> None:
    xbrl_file = tmp_path / "sample.xbrl"
    xbrl_file.write_text(
        """
        <xbrli:xbrl xmlns:xbrli="http://www.xbrl.org/2003/instance"
                    xmlns:jpcrp_cor="http://example.com/jpcrp">
          <jpcrp_cor:NotesPerShareInformationConsolidatedFinancialStatementsTextBlock contextRef="CurrentYearDuration">
            2023年12月13日開催の取締役会決議により、2024年４月１日付で普通株式１株につき４株の割合で株式分割を実施しております。
            また、2024年９月30日を基準日、2024年10月１日を効力発生日として、普通株式１株につき３株の割合で株式分割を実施しております。
            なお、2024年９月30日を基準日、10月１日を効力発生日として、普通株式１株につき３株の割合で株式分割を実施しております。
          </jpcrp_cor:NotesPerShareInformationConsolidatedFinancialStatementsTextBlock>
        </xbrli:xbrl>
        """,
        encoding="utf-8",
    )

    result = extract_shareholder_metrics(tmp_path, pre_parsed={})

    assert result["StockSplitRatio"] == 4.0
    assert result["CumulativeStockSplitRatio"] == 12.0
    events = result["StockSplitEvents"]
    assert isinstance(events, list)
    assert [event.get("ratio") for event in events] == [4.0, 3.0]
    assert [event.get("effective_date") for event in events] == [
        "2024-04-01",
        "2024-10-01",
    ]


def test_extract_shareholder_metrics_uses_dividend_textblock_table(tmp_path: Path) -> None:
    xbrl_file = tmp_path / "sample.xbrl"
    xbrl_file.write_text(
        """
        <xbrli:xbrl xmlns:xbrli="http://www.xbrl.org/2003/instance"
                    xmlns:jpcrp_cor="http://example.com/jpcrp">
          <jpcrp_cor:NotesDividendsConsolidatedFinancialStatementsIFRSTextBlock contextRef="CurrentYearDuration">
            &lt;p&gt;(単位：百万円)&lt;/p&gt;
            &lt;table&gt;
              &lt;tr&gt;&lt;th&gt;&lt;/th&gt;&lt;th&gt;前連結会計年度&lt;/th&gt;&lt;th&gt;当連結会計年度&lt;/th&gt;&lt;/tr&gt;
              &lt;tr&gt;&lt;td&gt;配当金の総額&lt;/td&gt;&lt;td&gt;1,000&lt;/td&gt;&lt;td&gt;2,000&lt;/td&gt;&lt;/tr&gt;
              &lt;tr&gt;&lt;td&gt;１株当たり配当額&lt;/td&gt;&lt;td&gt;40.0&lt;/td&gt;&lt;td&gt;50.0&lt;/td&gt;&lt;/tr&gt;
            &lt;/table&gt;
          </jpcrp_cor:NotesDividendsConsolidatedFinancialStatementsIFRSTextBlock>
        </xbrli:xbrl>
        """,
        encoding="utf-8",
    )

    result = extract_shareholder_metrics(
        tmp_path,
        pre_parsed={
            "BasicEarningsLossPerShareIFRS": {"CurrentYearDuration": 100.0},
        },
    )

    assert result["DivAnn"] == 50.0
    assert result["DivTotalAnn"] == 2_000_000_000.0
    assert result["PayoutRatioAnn"] == 0.5
    sources = result["MetricSources"]
    assert isinstance(sources, dict)
    assert sources["DivAnn"]["source"] == "fallback"
    assert sources["PayoutRatioAnn"]["source"] == "calculated"


def test_extract_shareholder_metrics_uses_basic_average_shares_textblock_table(
    tmp_path: Path,
) -> None:
    xbrl_file = tmp_path / "sample.xbrl"
    xbrl_file.write_text(
        """
        <xbrli:xbrl xmlns:xbrli="http://www.xbrl.org/2003/instance"
                    xmlns:jpigp_cor="http://example.com/jpigp">
          <jpigp_cor:NotesEarningsPerShareConsolidatedFinancialStatementsIFRSTextBlock contextRef="CurrentYearDuration">
            &lt;table&gt;
              &lt;tr&gt;&lt;td&gt;&lt;/td&gt;&lt;td&gt;&lt;/td&gt;&lt;td&gt;（単位：千株）&lt;/td&gt;&lt;/tr&gt;
              &lt;tr&gt;&lt;td&gt;&lt;/td&gt;&lt;td&gt;前連結会計年度&lt;/td&gt;&lt;td&gt;当連結会計年度&lt;/td&gt;&lt;/tr&gt;
              &lt;tr&gt;&lt;td&gt;期中平均普通株式数&lt;/td&gt;&lt;td&gt;1,040,657&lt;/td&gt;&lt;td&gt;1,007,203&lt;/td&gt;&lt;/tr&gt;
              &lt;tr&gt;&lt;td&gt;希薄化効果調整後期中平均普通株式数&lt;/td&gt;&lt;td&gt;1,040,866&lt;/td&gt;&lt;td&gt;1,007,206&lt;/td&gt;&lt;/tr&gt;
            &lt;/table&gt;
          </jpigp_cor:NotesEarningsPerShareConsolidatedFinancialStatementsIFRSTextBlock>
        </xbrli:xbrl>
        """,
        encoding="utf-8",
    )

    result = extract_shareholder_metrics(
        tmp_path,
        pre_parsed={
            "BasicEarningsLossPerShareIFRS": {"CurrentYearDuration": 69.77},
        },
        net_profit=70_272_000_000.0,
    )

    assert result["AverageShares"] == 1_007_203_000.0
    assert result["CalculatedEPS"] == 69.76945064698974
    sources = result["MetricSources"]
    assert isinstance(sources, dict)
    assert sources["AverageShares"]["source"] == "fallback"
    assert sources["AverageShares"]["statement"] == "notes"
