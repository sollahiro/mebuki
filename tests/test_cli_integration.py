import json
import sys
from unittest.mock import AsyncMock, Mock, patch

from mebuki.app.cli.main import main


def _run_cli(monkeypatch, argv: list[str]) -> None:
    monkeypatch.setattr(sys, "argv", ["mebuki", *argv])
    with patch("mebuki.app.cli.main.print_banner"):
        main()


def test_main_keyboard_interrupt_exits_cleanly(monkeypatch, capsys) -> None:
    monkeypatch.setattr(sys, "argv", ["mebuki", "search", "トヨタ", "--format", "json"])

    with patch("mebuki.app.cli.analyze.master_data_manager.search", side_effect=KeyboardInterrupt):
        exit_code = main()

    captured = capsys.readouterr()
    assert exit_code == 130
    assert captured.out == ""
    assert captured.err == "\n中断しました。\n"


def test_main_search_outputs_json(monkeypatch, capsys) -> None:
    results = [
        {"code": "7203", "name": "トヨタ自動車", "market": "プライム", "sector": "輸送用機器"},
    ]

    with patch("mebuki.app.cli.analyze.master_data_manager.search", return_value=results) as search:
        _run_cli(monkeypatch, ["search", "トヨタ", "--format", "json"])

    captured = capsys.readouterr()
    assert json.loads(captured.out) == results
    assert captured.err == ""
    search.assert_called_once_with("トヨタ")


def test_main_analyze_outputs_json_and_closes_service(monkeypatch, capsys) -> None:
    data_service = Mock()
    data_service.fetch_stock_basic_info.return_value = {
        "name": "トヨタ自動車",
        "market_name": "プライム",
    }
    data_service.get_raw_analysis_data = AsyncMock(return_value={
        "metrics": {
            "years": [
                {
                    "fy_end": "2024-03-31",
                    "RawData": {"CurPerType": "FY"},
                    "CalculatedData": {"Sales": 1_000.0},
                }
            ]
        }
    })
    data_service.close = AsyncMock()

    with patch("mebuki.services.data_service.data_service", data_service):
        _run_cli(monkeypatch, ["analyze", "7203", "--years", "2", "--format", "json", "--no-cache"])

    captured = capsys.readouterr()
    assert json.loads(captured.out)["metrics"]["years"][0]["CalculatedData"]["Sales"] == 1_000.0
    assert "分析中: 72030 トヨタ自動車" in captured.err
    data_service.get_raw_analysis_data.assert_awaited_once_with(
        "72030",
        use_cache=False,
        analysis_years=2,
        include_debug_fields=False,
    )
    data_service.close.assert_awaited_once()


def test_main_filings_outputs_json(monkeypatch, capsys) -> None:
    docs = [
        {"docID": "S100TEST", "docTypeCode": "120", "docDescription": "有価証券報告書"},
    ]
    data_service = Mock()
    data_service.search_filings = AsyncMock(return_value=docs)
    data_service.close = AsyncMock()

    with patch("mebuki.services.data_service.data_service", data_service):
        _run_cli(monkeypatch, ["filings", "7203", "--format", "json"])

    captured = capsys.readouterr()
    assert json.loads(captured.out) == docs
    data_service.search_filings.assert_awaited_once_with(
        "72030",
        max_years=10,
        doc_types=["120", "130", "140", "150", "160", "170"],
        max_documents=10,
    )
    data_service.close.assert_awaited_once()


def test_main_filing_outputs_json_with_sections(monkeypatch, capsys) -> None:
    result = {
        "doc_id": "S100TEST",
        "sections": {"mda": "経営成績の分析"},
    }
    data_service = Mock()
    data_service.extract_filing_content = AsyncMock(return_value=result)
    data_service.close = AsyncMock()

    with patch("mebuki.services.data_service.data_service", data_service):
        _run_cli(
            monkeypatch,
            ["filing", "7203", "--doc-id", "S100TEST", "--sections", "mda", "--format", "json"],
        )

    captured = capsys.readouterr()
    assert json.loads(captured.out) == result
    data_service.extract_filing_content.assert_awaited_once_with(
        "72030",
        doc_id="S100TEST",
        sections=["mda"],
    )
    data_service.close.assert_awaited_once()


def test_main_cache_prune_outputs_json(monkeypatch, capsys) -> None:
    summary = Mock()
    summary.to_dict.return_value = {
        "removed_files": 1,
        "removed_dirs": 2,
        "freed_bytes": 3,
        "scanned_files": 1,
        "scanned_dirs": 2,
        "dry_run": False,
    }
    pruner = Mock()
    pruner.prune.return_value = summary

    with (
        patch("mebuki.app.cli.cache.settings_store") as settings,
        patch("mebuki.app.cli.cache.CachePruner", return_value=pruner) as pruner_cls,
    ):
        settings.cache_dir = "/tmp/mebuki-cache"
        _run_cli(
            monkeypatch,
            [
                "cache",
                "prune",
                "--execute",
                "--edinet-search-days",
                "30",
                "--edinet-xbrl-days",
                "60",
                "--format",
                "json",
            ],
        )

    captured = capsys.readouterr()
    assert json.loads(captured.out)["freed_bytes"] == 3
    pruner_cls.assert_called_once_with("/tmp/mebuki-cache")
    pruner.prune.assert_called_once_with(
        dry_run=False,
        include_boj=True,
        edinet_search_days=30,
        edinet_xbrl_days=60,
    )


def test_main_cache_stats_outputs_json(monkeypatch, capsys) -> None:
    stats = Mock()
    stats.to_dict.return_value = {
        "cache_dir": "/tmp/mebuki-cache",
        "total_files": 3,
        "total_dirs": 1,
        "total_bytes": 1024,
        "metadata_entries": 2,
        "root_json_files": 2,
        "edinet_search_files": 1,
        "edinet_xbrl_dirs": 0,
        "boj_files": 1,
        "boj_metadata_entries": 1,
        "unknown_root_json_files": 0,
    }
    pruner = Mock()
    pruner.stats.return_value = stats

    with (
        patch("mebuki.app.cli.cache.settings_store") as settings,
        patch("mebuki.app.cli.cache.CachePruner", return_value=pruner) as pruner_cls,
    ):
        settings.cache_dir = "/tmp/mebuki-cache"
        _run_cli(monkeypatch, ["cache", "stats", "--format", "json"])

    captured = capsys.readouterr()
    assert json.loads(captured.out)["total_bytes"] == 1024
    pruner_cls.assert_called_once_with("/tmp/mebuki-cache")
    pruner.stats.assert_called_once_with()



def test_main_watch_add_outputs_json(monkeypatch, capsys) -> None:
    result = {
        "status": "added",
        "item": {"ticker_code": "7203", "name": "トヨタ自動車"},
    }
    portfolio_service = Mock()
    portfolio_service.add_watch.return_value = result

    with patch("mebuki.services.portfolio_service.portfolio_service", portfolio_service):
        _run_cli(monkeypatch, ["watch", "add", "7203", "--name", "トヨタ自動車", "--format", "json"])

    captured = capsys.readouterr()
    assert json.loads(captured.out) == result
    assert captured.err == ""
    portfolio_service.add_watch.assert_called_once_with("7203", name="トヨタ自動車")


def test_main_portfolio_list_outputs_json(monkeypatch, capsys) -> None:
    holdings = [
        {"ticker_code": "7203", "name": "トヨタ自動車", "total_quantity": 100, "avg_cost_price": 2500.0},
    ]
    portfolio_service = Mock()
    portfolio_service.get_consolidated.return_value = holdings

    with patch("mebuki.services.portfolio_service.portfolio_service", portfolio_service):
        _run_cli(monkeypatch, ["portfolio", "list", "--format", "json"])

    captured = capsys.readouterr()
    assert json.loads(captured.out) == holdings
    assert captured.err == ""
    portfolio_service.get_consolidated.assert_called_once_with()
