"""株式・配当・現金同等物 XBRL 抽出モジュール。"""

from pathlib import Path

from blue_ticker.analysis.xbrl_utils import collect_numeric_elements, find_xbrl_files
from blue_ticker.utils.xbrl_result_types import XbrlTagElements

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

_PAYOUT_RATIO_TAGS: list[str] = [
    "PayoutRatioSummaryOfBusinessResults",
]

_RELEVANT_TAGS: frozenset[str] = frozenset(
    _CASH_EQ_TAGS
    + _EPS_TAGS
    + _BPS_TAGS
    + _ISSUED_SHARES_TAGS
    + _DIVIDEND_PER_SHARE_TAGS
    + _INTERIM_DIVIDEND_PER_SHARE_TAGS
    + _DIVIDEND_TOTAL_TAGS
    + _PAYOUT_RATIO_TAGS
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
    payout_ratio = _first_current_value(tag_elements, _PAYOUT_RATIO_TAGS)
    if payout_ratio is None:
        payout_ratio = round(div_ann / eps, 3) if div_ann is not None and eps else None

    return {
        "CashEq": _first_current_value(tag_elements, _CASH_EQ_TAGS),
        "EPS": eps,
        "BPS": _first_current_value(tag_elements, _BPS_TAGS),
        "ShOutFY": _first_current_value(tag_elements, _ISSUED_SHARES_TAGS),
        "DivAnn": div_ann,
        "Div2Q": _first_current_value(tag_elements, _INTERIM_DIVIDEND_PER_SHARE_TAGS),
        "DivTotalAnn": _sum_filing_rows(tag_elements, _DIVIDEND_TOTAL_TAGS),
        "PayoutRatioAnn": payout_ratio,
    }
