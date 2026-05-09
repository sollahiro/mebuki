import asyncio
import json
import os
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

from blue_ticker.analysis.balance_sheet import extract_balance_sheet
from blue_ticker.analysis.context_helpers import has_nonconsolidated_contexts
from blue_ticker.analysis.gross_profit import extract_gross_profit
from blue_ticker.analysis.income_statement import extract_income_statement
from blue_ticker.analysis.interest_bearing_debt import extract_interest_bearing_debt
from blue_ticker.services.edinet_smoke_cache import DEFAULT_SMOKE_COMPANIES
from blue_ticker.services.edinet_fetcher import EdinetFetcher
from blue_ticker.utils.fiscal_year import normalize_date_format

_DEFAULT_SMOKE_CACHE_DIR = Path("tmp_cache") / "edinet"
_ExpectedStandards = frozenset[str] | Callable[[str], frozenset[str]]
_ExpectedConsolidated = bool | Callable[[str], bool] | None


@dataclass(frozen=True)
class SmokeCompany:
    code: str
    name: str
    category: str
    expected_standards: _ExpectedStandards
    expected_has_consolidated_contexts: _ExpectedConsolidated = None


def _suzuki_expected_standards(fy_end: str) -> frozenset[str]:
    normalized = normalize_date_format(fy_end) or fy_end
    if normalized <= "2024-03-31":
        return frozenset({"J-GAAP"})
    return frozenset({"IFRS"})


def _canon_expected_standards(fy_end: str) -> frozenset[str]:
    normalized = normalize_date_format(fy_end) or fy_end
    if normalized <= "2026-12-31":
        return frozenset({"US-GAAP"})
    return frozenset({"IFRS"})


def _azplanning_expected_has_consolidated_contexts(fy_end: str) -> bool:
    normalized = normalize_date_format(fy_end) or fy_end
    return normalized >= "2024-02-29"


# 実企業スモークの対象。会計基準変更やテスト対象の見直しはこの表だけを更新する。
_SMOKE_COMPANY_BY_CODE = {company.code: company for company in DEFAULT_SMOKE_COMPANIES}
SMOKE_COMPANIES: tuple[SmokeCompany, ...] = (
    SmokeCompany(
        _SMOKE_COMPANY_BY_CODE["4901"].code,
        _SMOKE_COMPANY_BY_CODE["4901"].name,
        _SMOKE_COMPANY_BY_CODE["4901"].category,
        frozenset({"US-GAAP"}),
    ),
    SmokeCompany(
        _SMOKE_COMPANY_BY_CODE["7751"].code,
        _SMOKE_COMPANY_BY_CODE["7751"].name,
        _SMOKE_COMPANY_BY_CODE["7751"].category,
        _canon_expected_standards,
    ),
    SmokeCompany(
        _SMOKE_COMPANY_BY_CODE["8306"].code,
        _SMOKE_COMPANY_BY_CODE["8306"].name,
        _SMOKE_COMPANY_BY_CODE["8306"].category,
        frozenset({"J-GAAP"}),
    ),
    SmokeCompany(
        _SMOKE_COMPANY_BY_CODE["8316"].code,
        _SMOKE_COMPANY_BY_CODE["8316"].name,
        _SMOKE_COMPANY_BY_CODE["8316"].category,
        frozenset({"J-GAAP"}),
    ),
    SmokeCompany(
        _SMOKE_COMPANY_BY_CODE["6103"].code,
        _SMOKE_COMPANY_BY_CODE["6103"].name,
        _SMOKE_COMPANY_BY_CODE["6103"].category,
        frozenset({"J-GAAP"}),
    ),
    SmokeCompany(
        _SMOKE_COMPANY_BY_CODE["6326"].code,
        _SMOKE_COMPANY_BY_CODE["6326"].name,
        _SMOKE_COMPANY_BY_CODE["6326"].category,
        frozenset({"IFRS"}),
    ),
    SmokeCompany(
        _SMOKE_COMPANY_BY_CODE["2802"].code,
        _SMOKE_COMPANY_BY_CODE["2802"].name,
        _SMOKE_COMPANY_BY_CODE["2802"].category,
        frozenset({"IFRS"}),
    ),
    SmokeCompany(
        _SMOKE_COMPANY_BY_CODE["7269"].code,
        _SMOKE_COMPANY_BY_CODE["7269"].name,
        _SMOKE_COMPANY_BY_CODE["7269"].category,
        _suzuki_expected_standards,
    ),
    SmokeCompany(
        _SMOKE_COMPANY_BY_CODE["7422"].code,
        _SMOKE_COMPANY_BY_CODE["7422"].name,
        _SMOKE_COMPANY_BY_CODE["7422"].category,
        frozenset({"J-GAAP"}),
        False,
    ),
    SmokeCompany(
        _SMOKE_COMPANY_BY_CODE["3490"].code,
        _SMOKE_COMPANY_BY_CODE["3490"].name,
        _SMOKE_COMPANY_BY_CODE["3490"].category,
        frozenset({"J-GAAP"}),
        _azplanning_expected_has_consolidated_contexts,
    ),
)


class _CachedXbrlClient:
    """EDINET APIへ出ず、展開済みXBRLディレクトリだけを返すテスト用クライアント。"""

    api_key = "cached-smoke"

    def __init__(self, edinet_cache_dir: Path) -> None:
        self.edinet_cache_dir = edinet_cache_dir
        self.downloaded_doc_ids: list[str] = []

    async def download_document(self, doc_id: str, doc_type: int = 1) -> str | None:
        if doc_type != 1:
            raise AssertionError("smoke test should only request XBRL documents")
        self.downloaded_doc_ids.append(doc_id)
        xbrl_dir = self.edinet_cache_dir / f"{doc_id}_xbrl"
        return str(xbrl_dir) if xbrl_dir.is_dir() else None


def _smoke_cache_dir() -> Path:
    return Path(
        os.environ.get("BLUE_TICKER_EDINET_SMOKE_CACHE_DIR")
        or os.environ.get("MEBUKI_EDINET_SMOKE_CACHE_DIR")
        or str(_DEFAULT_SMOKE_CACHE_DIR)
    )


def _load_search_cache_documents(edinet_cache_dir: Path) -> list[dict[str, Any]]:
    docs: list[dict[str, Any]] = []
    for path in sorted(edinet_cache_dir.glob("search_*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(payload, list):
            docs.extend(doc for doc in payload if isinstance(doc, dict))
    return docs


def _latest_cached_annual_doc(company: SmokeCompany, edinet_cache_dir: Path) -> dict[str, Any] | None:
    sec_code = f"{company.code}0"
    candidates = [
        doc
        for doc in _load_search_cache_documents(edinet_cache_dir)
        if doc.get("secCode") == sec_code
        and doc.get("docTypeCode") == "120"
        and isinstance(doc.get("docID"), str)
        and isinstance(doc.get("periodEnd"), str)
        and (edinet_cache_dir / f"{doc['docID']}_xbrl").is_dir()
    ]
    if not candidates:
        return None
    doc = sorted(candidates, key=lambda item: str(item.get("submitDateTime") or ""), reverse=True)[0].copy()
    doc["edinet_fy_end"] = normalize_date_format(str(doc["periodEnd"])) or doc["periodEnd"]
    doc["period_type"] = "FY"
    return doc


def _financial_record_from_doc(doc: dict[str, Any]) -> dict[str, Any]:
    fy_end = str(doc["edinet_fy_end"])
    submit_date = normalize_date_format(str(doc.get("submitDateTime") or "")) or str(doc.get("submitDateTime") or "")
    return {
        "CurPerType": "FY",
        "CurFYEn": fy_end,
        "DiscDate": submit_date,
        "_docID": doc["docID"],
    }


def _expected_standards(company: SmokeCompany, fy_end: str) -> frozenset[str]:
    if callable(company.expected_standards):
        return company.expected_standards(fy_end)
    return company.expected_standards


def _expected_has_consolidated_contexts(company: SmokeCompany, fy_end: str) -> bool | None:
    expected = company.expected_has_consolidated_contexts
    if callable(expected):
        return expected(fy_end)
    return expected


@pytest.mark.parametrize("company", SMOKE_COMPANIES, ids=lambda company: f"{company.code}-{company.name}")
def test_edinet_only_smoke_from_cached_search_and_xbrl(company: SmokeCompany) -> None:
    """日次検索キャッシュから書類を選び、展開済みXBRLをparseするEDINET-onlyスモーク。

    ネットワークと分析結果キャッシュは使わない。必要な `search_*.json` と
    `{docID}_xbrl/` がローカルにない環境では skip する。
    """
    edinet_cache_dir = _smoke_cache_dir()
    if not edinet_cache_dir.is_dir():
        pytest.skip(f"EDINET smoke cache directory not found: {edinet_cache_dir}")

    doc = _latest_cached_annual_doc(company, edinet_cache_dir)
    if doc is None:
        pytest.skip(f"cached annual XBRL not found for {company.code} {company.name} in {edinet_cache_dir}")

    client = _CachedXbrlClient(edinet_cache_dir)
    fetcher = EdinetFetcher(edinet_client=client)  # type: ignore[arg-type]
    financial_data = [_financial_record_from_doc(doc)]

    pre_parsed_map = asyncio.run(fetcher.predownload_and_parse(company.code, financial_data, max_years=1))
    fy_key = str(doc["edinet_fy_end"]).replace("-", "")

    assert fy_key in pre_parsed_map
    assert client.downloaded_doc_ids == [doc["docID"]]

    xbrl_dir, pre_parsed = pre_parsed_map[fy_key]
    assert pre_parsed

    expected_consolidated_contexts = _expected_has_consolidated_contexts(company, str(doc["edinet_fy_end"]))
    if expected_consolidated_contexts is not None:
        assert has_nonconsolidated_contexts(pre_parsed) is expected_consolidated_contexts

    income = extract_income_statement(xbrl_dir, pre_parsed=pre_parsed)
    assert income["accounting_standard"] in _expected_standards(company, str(doc["edinet_fy_end"]))
    assert any(income.get(key) is not None for key in ("sales", "operating_profit", "net_profit"))

    balance_sheet = extract_balance_sheet(xbrl_dir, pre_parsed=pre_parsed)
    assert balance_sheet["accounting_standard"] in _expected_standards(company, str(doc["edinet_fy_end"]))
    assert any(
        balance_sheet.get(key) is not None
        for key in (
            "current_assets",
            "non_current_assets",
            "current_liabilities",
            "non_current_liabilities",
            "net_assets",
        )
    )

    gross_profit = extract_gross_profit(xbrl_dir, pre_parsed=pre_parsed)
    assert gross_profit["accounting_standard"] in _expected_standards(company, str(doc["edinet_fy_end"]))
    assert gross_profit["method"] != "not_found" or company.category == "J-GAAP financial"

    ibd = extract_interest_bearing_debt(xbrl_dir, pre_parsed=pre_parsed)
    assert ibd["accounting_standard"] in _expected_standards(company, str(doc["edinet_fy_end"]))
    assert ibd["method"] != "not_found" or company.category == "J-GAAP financial"
