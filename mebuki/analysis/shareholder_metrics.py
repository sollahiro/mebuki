"""株式・配当・現金同等物 XBRL 抽出モジュール。"""

from pathlib import Path

from bs4 import BeautifulSoup

from mebuki.analysis.xbrl_utils import collect_numeric_elements, find_xbrl_files, parse_html_number
from mebuki.utils.xbrl_result_types import XbrlTagElements

_CASH_EQ_TAGS: list[str] = [
    "CashAndCashEquivalentsIFRS",
    "CashAndCashEquivalentsIFRSSummaryOfBusinessResults",
    "CashAndCashEquivalentsUSGAAPSummaryOfBusinessResults",
    "CashAndCashEquivalentsSummaryOfBusinessResults",
    "CashAndCashEquivalents",
]

_EPS_TAGS: list[str] = [
    "BasicEarningsLossPerShareIFRS",
    "BasicEarningsLossPerShareIFRSSummaryOfBusinessResults",
    "BasicEarningsLossPerShareUSGAAPSummaryOfBusinessResults",
    "BasicEarningsLossPerShareSummaryOfBusinessResults",
]

_BPS_TAGS: list[str] = [
    "EquityToAssetRatioIFRSSummaryOfBusinessResults",
    "EquityAttributableToOwnersOfParentPerShareIFRSSummaryOfBusinessResults",
    "EquityAttributableToOwnersOfParentPerShareUSGAAPSummaryOfBusinessResults",
    "NetAssetsPerShareSummaryOfBusinessResults",
]

_ISSUED_SHARES_TAGS: list[str] = [
    "NumberOfIssuedSharesAsOfFiscalYearEndIssuedSharesTotalNumberOfSharesEtc",
    "NumberOfIssuedSharesAsOfFilingDateIssuedSharesTotalNumberOfSharesEtc",
    "TotalNumberOfIssuedSharesSummaryOfBusinessResults",
]

_DIVIDEND_PER_SHARE_TAGS: list[str] = [
    "DividendPaidPerShareSummaryOfBusinessResults",
]

_INTERIM_DIVIDEND_PER_SHARE_TAGS: list[str] = [
    "InterimDividendPaidPerShareSummaryOfBusinessResults",
]

_DIVIDEND_TOTAL_TAGS: list[str] = [
    "TotalAmountOfDividendsDividendsOfSurplus",
    "DividendsFromSurplus",
]

_RELEVANT_TAGS: frozenset[str] = frozenset(
    _CASH_EQ_TAGS
    + _EPS_TAGS
    + _BPS_TAGS
    + _ISSUED_SHARES_TAGS
    + _DIVIDEND_PER_SHARE_TAGS
    + _INTERIM_DIVIDEND_PER_SHARE_TAGS
    + _DIVIDEND_TOTAL_TAGS
)

_CURRENT_CONTEXTS: tuple[str, ...] = (
    "CurrentYearInstant",
    "CurrentYearInstant_NonConsolidatedMember",
    "CurrentYearDuration",
    "CurrentYearDuration_NonConsolidatedMember",
    "InterimInstant",
    "InterimInstant_NonConsolidatedMember",
    "InterimDuration",
    "InterimDuration_NonConsolidatedMember",
    "CurrentYTDDuration",
    "CurrentYTDDuration_NonConsolidatedMember",
    "FilingDateInstant",
)


def _first_current_value(tag_elements: XbrlTagElements, tags: list[str]) -> float | None:
    for tag in tags:
        ctx_map = tag_elements.get(tag)
        if not ctx_map:
            continue
        for ctx in _CURRENT_CONTEXTS:
            if ctx in ctx_map:
                return ctx_map[ctx]
        for ctx, value in ctx_map.items():
            if (
                ctx.startswith("CurrentYear")
                or ctx.startswith("Interim")
                or ctx.startswith("CurrentYTD")
                or ctx.startswith("FilingDateInstant")
            ):
                return value
    return None


def _sum_filing_rows(tag_elements: XbrlTagElements, tags: list[str]) -> float | None:
    for tag in tags:
        ctx_map = tag_elements.get(tag)
        if not ctx_map:
            continue
        row_values = [
            abs(value)
            for ctx, value in ctx_map.items()
            if ctx.startswith("FilingDateInstant_Row")
        ]
        if row_values:
            return sum(row_values)
        current = _first_current_value(tag_elements, [tag])
        if current is not None:
            return abs(current)
    return None


def _derive_average_shares(net_profit: float | None, eps: float | None) -> float | None:
    if net_profit is None or eps is None or eps == 0:
        return None
    return net_profit / eps


def _extract_average_shares_from_html(xbrl_dir: Path) -> float | None:
    for html_file in xbrl_dir.rglob("*.htm"):
        try:
            soup = BeautifulSoup(html_file.read_text(encoding="utf-8", errors="ignore"), "html.parser")
        except OSError:
            continue
        for row in soup.find_all("tr"):
            cells = row.find_all(["td", "th"])
            if len(cells) < 2:
                continue
            label = cells[0].get_text(" ", strip=True)
            if "普通株式の加重平均株式数" not in label:
                continue
            current_text = cells[-1].get_text(" ", strip=True)
            current_text = current_text.replace("千株", "")
            value = parse_html_number(current_text)
            if value is not None:
                return value * 1000
    return None


def extract_shareholder_metrics(
    xbrl_dir: Path,
    *,
    pre_parsed: XbrlTagElements | None = None,
    net_profit: float | None = None,
) -> dict[str, float | None]:
    """XBRLから株式・配当・現金同等物を抽出する。

    年次レコードへ載せるため、金額は円単位、1株当たり値は円、
    株式数は株単位で返す。
    """
    if pre_parsed is not None:
        tag_elements: XbrlTagElements = {
            tag: ctx for tag, ctx in pre_parsed.items() if tag in _RELEVANT_TAGS
        }
    else:
        tag_elements = {}
        for f in find_xbrl_files(xbrl_dir):
            for tag, ctx_map in collect_numeric_elements(f, _RELEVANT_TAGS).items():
                if tag not in tag_elements:
                    tag_elements[tag] = {}
                tag_elements[tag].update(ctx_map)

    eps = _first_current_value(tag_elements, _EPS_TAGS)
    div_ann = _first_current_value(tag_elements, _DIVIDEND_PER_SHARE_TAGS)
    payout_ratio = round(div_ann / eps, 3) if div_ann is not None and eps else None
    avg_sh = _extract_average_shares_from_html(xbrl_dir)

    return {
        "CashEq": _first_current_value(tag_elements, _CASH_EQ_TAGS),
        "EPS": eps,
        "BPS": _first_current_value(tag_elements, _BPS_TAGS),
        "AvgSh": avg_sh if avg_sh is not None else _derive_average_shares(net_profit, eps),
        "ShOutFY": _first_current_value(tag_elements, _ISSUED_SHARES_TAGS),
        "DivAnn": div_ann,
        "Div2Q": _first_current_value(tag_elements, _INTERIM_DIVIDEND_PER_SHARE_TAGS),
        "DivTotalAnn": _sum_filing_rows(tag_elements, _DIVIDEND_TOTAL_TAGS),
        "PayoutRatioAnn": payout_ratio,
    }
