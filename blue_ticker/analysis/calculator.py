"""
指標計算モジュール

年度データから各種財務指標を計算します。
"""

import logging
from typing import Any
from collections.abc import Sequence
from datetime import datetime

from ..utils.converters import to_float, is_valid_value, is_valid_financial_record, extract_year_month
from blue_ticker.constants.financial import (
    MILLION_YEN,
    PERCENT,
)
from blue_ticker.utils.metrics_types import RawData, CalculatedData, YearEntry, MetricsResult
from blue_ticker.utils.metrics_access import raw_metric_millions


def to_millions(value: float | None) -> float | None:
    """円単位の値を百万円単位に変換"""
    if value is None:
        return None
    return value / MILLION_YEN


def _calculate_profitability_metrics(np: float | None, op: float | None, eq: float | None, cfo: float | None) -> dict[str, float | None]:
    """収益性指標（ROE, ROIC, CF変換率）の計算"""
    roe = None
    if np is not None and eq is not None and eq != 0:
        roe = (np / eq) * PERCENT

    cf_conversion_rate = None
    if cfo is not None and op is not None and op != 0:
        cf_conversion_rate = (cfo / op) * PERCENT

    return {
        "roe": roe,
        "cf_conversion_rate": cf_conversion_rate
    }


from ..utils.errors import (
    check_data_availability,
    get_data_availability_message,
    validate_metrics_for_analysis,
    DataAvailability
)

logger = logging.getLogger(__name__)


def _filter_annual_data(annual_data: list[dict[str, Any]], analysis_years: int) -> list[dict[str, Any]]:
    """年数上限・未来日付除外・重複排除・バリデーションを適用してデータを絞り込む"""
    today = datetime.now()
    current_year = today.year
    current_month = today.month

    years_data = []
    seen_entries = set()
    fy_count = 0
    for year_data in annual_data:
        if fy_count >= analysis_years:
            break
        fy_end = year_data.get("CurFYEn")
        if not fy_end:
            continue
        per_type = year_data.get("CurPerType", "FY")
        dedup_key = (fy_end, per_type)
        if dedup_key in seen_entries:
            continue

        # 未来の年度データを除外
        try:
            y, m = extract_year_month(fy_end)
            if y is not None and m is not None and (
                y > current_year or (y == current_year and m > current_month)
            ):
                continue
        except (ValueError, IndexError):
            pass

        if not is_valid_financial_record(year_data):
            continue

        # FYレコードは財務実績データ必須
        # 業績予想修正（EarnForecastRevision）などの空レコードが
        # CurFYEn+DiscDateの緩和条件で通過するのを防ぐ
        if per_type == "FY" and not (
            is_valid_value(year_data.get("Sales"))
            or is_valid_value(year_data.get("OP"))
            or is_valid_value(year_data.get("NP"))
            or is_valid_value(year_data.get("NetAssets"))
        ):
            continue

        years_data.append(year_data)
        seen_entries.add(dedup_key)
        if per_type == "FY":
            fy_count += 1

    return years_data


def _extract_raw_values(year_data: dict[str, Any]) -> RawData:
    """年度データから生値を抽出する"""
    return {
        'CurPerType': year_data.get("CurPerType", ""),
        'CurFYSt': year_data.get("CurFYSt", ""),
        'CurFYEn': year_data.get("CurFYEn"),
        'DiscDate': year_data.get("DiscDate", ""),
        'SalesLabel': year_data.get("SalesLabel"),
        'Sales': to_float(year_data.get("Sales")),
        'OP': to_float(year_data.get("OP")),
        'NP': to_float(year_data.get("NP")),
        'NetAssets': to_float(year_data.get("NetAssets")),
        'CFO': to_float(year_data.get("CFO")),
        'CFI': to_float(year_data.get("CFI")),
        'EPS': to_float(year_data.get("EPS")),
        'BPS': to_float(year_data.get("BPS")),
        'ShOutFY': to_float(year_data.get("ShOutFY")),
        'AverageShares': to_float(year_data.get("AverageShares")),
        'TreasuryShares': to_float(year_data.get("TreasuryShares")),
        'SharesForBPS': to_float(year_data.get("SharesForBPS")),
        'ParentEquity': to_float(year_data.get("ParentEquity")),
        'CalculatedEPS': to_float(year_data.get("CalculatedEPS")),
        'CalculatedBPS': to_float(year_data.get("CalculatedBPS")),
        'EPSDirectDiff': to_float(year_data.get("EPSDirectDiff")),
        'BPSDirectDiff': to_float(year_data.get("BPSDirectDiff")),
        'DivTotalAnn': to_float(year_data.get("DivTotalAnn")),
        'PayoutRatioAnn': to_float(year_data.get("PayoutRatioAnn")),
        'CashEq': to_float(year_data.get("CashAndCashEquivalents")) or to_float(year_data.get("CashEq")) or to_float(year_data.get("Cash")),
        'Div2Q': to_float(year_data.get("Div2Q")),
        'DivAnn': to_float(year_data.get("DivAnn")),
        '_xbrl_source': bool(year_data.get("_xbrl_source")),
    }


def _add_per_share_calculation_values(
    values: CalculatedData,
    raw_values: RawData,
    base_source: str,
) -> None:
    metric_sources = values.setdefault("MetricSources", {})
    metric_sources["EPS"] = {
        "source": base_source,
        "unit": "yen_per_share",
        "method": "direct",
    }
    metric_sources["BPS"] = {
        "source": base_source,
        "unit": "yen_per_share",
        "method": "direct",
    }

    calculated_eps = raw_values.get("CalculatedEPS")
    if calculated_eps is not None:
        values["CalculatedEPS"] = calculated_eps
        values["AverageShares"] = raw_values.get("AverageShares")
        metric_sources["CalculatedEPS"] = {
            "source": "calculated",
            "method": "NP / AverageShares",
            "unit": "yen_per_share",
        }
    eps_direct_diff = raw_values.get("EPSDirectDiff")
    if eps_direct_diff is not None:
        values["EPSDirectDiff"] = eps_direct_diff
        metric_sources["EPSDirectDiff"] = {
            "source": "derived",
            "method": "EPS - CalculatedEPS",
            "unit": "yen_per_share",
        }

    calculated_bps = raw_values.get("CalculatedBPS")
    if calculated_bps is not None:
        values["CalculatedBPS"] = calculated_bps
        values["ParentEquity"] = raw_values.get("ParentEquity")
        values["TreasuryShares"] = raw_values.get("TreasuryShares")
        values["SharesForBPS"] = raw_values.get("SharesForBPS")
        metric_sources["CalculatedBPS"] = {
            "source": "calculated",
            "method": "ParentEquity / SharesForBPS",
            "unit": "yen_per_share",
        }
    bps_direct_diff = raw_values.get("BPSDirectDiff")
    if bps_direct_diff is not None:
        values["BPSDirectDiff"] = bps_direct_diff
        metric_sources["BPSDirectDiff"] = {
            "source": "derived",
            "method": "BPS - CalculatedBPS",
            "unit": "yen_per_share",
        }


def _calculate_base_values(raw_values: RawData) -> CalculatedData:
    """RawData を元に派生値を計算する。"""
    cfo = raw_values.get('CFO')
    cfi = raw_values.get('CFI')
    payout_ratio_ann = raw_values.get('PayoutRatioAnn')
    cfo_m = to_millions(cfo)
    cfi_m = to_millions(cfi)
    values: CalculatedData = {
        'PayoutRatio': payout_ratio_ann * PERCENT if payout_ratio_ann is not None else None,
        'CFC': (cfo_m + cfi_m) if (cfo_m is not None and cfi_m is not None) else None
    }
    base_source = "edinet" if raw_values.get("_xbrl_source") else "external"
    values["MetricSources"] = {
        "Sales": {"source": base_source, "unit": "million_yen"},
        "OP": {"source": base_source, "unit": "million_yen"},
        "NP": {"source": base_source, "unit": "million_yen"},
        "NetAssets": {"source": base_source, "unit": "million_yen"},
        "CFO": {"source": base_source, "unit": "million_yen"},
        "CFI": {"source": base_source, "unit": "million_yen"},
        "CashEq": {"source": base_source, "unit": "million_yen"},
        "PayoutRatio": {"source": base_source, "unit": "percent"},
        "CFC": {"source": "derived", "method": "CFO + CFI", "unit": "million_yen"},
    }
    sales_label = raw_values.get("SalesLabel")
    if isinstance(sales_label, str) and sales_label:
        values["MetricSources"]["Sales"]["label"] = sales_label
        values["MetricSources"]["Sales"]["source"] = "edinet"
    _add_per_share_calculation_values(values, raw_values, base_source)
    return values


def _format_financial_period(fy_end: str | None, per_type: str) -> str:
    """決算期の文字列を返す（例: "2024年03月期" / "2024年03月期 (2Q)"）"""
    period = ""
    if fy_end:
        year, month = extract_year_month(fy_end)
        if year is not None and month is not None:
            period = f"{year}年{month:02d}月期"
    if per_type == "2Q":
        period += " (2Q)"
    return period


def _build_year_entry(year_data: dict[str, Any]) -> YearEntry:
    """1年分の指標エントリを組み立てる"""
    fy_end = year_data.get("CurFYEn")
    per_type = year_data.get("CurPerType", "FY")

    raw_values = _extract_raw_values(year_data)
    calc_values = _calculate_base_values(raw_values)

    # 収益性指標
    profit_metrics = _calculate_profitability_metrics(
        raw_metric_millions(raw_values, "NP"),
        raw_metric_millions(raw_values, "OP"),
        raw_metric_millions(raw_values, "NetAssets"),
        raw_metric_millions(raw_values, "CFO"),
    )
    calc_values.update({
        'ROE': profit_metrics['roe'],
        'CFCVR': profit_metrics['cf_conversion_rate']
    })
    metric_sources = calc_values.get("MetricSources") or {}
    metric_sources.update({
        "ROE": {"source": "derived", "method": "NP / NetAssets", "unit": "percent"},
        "CFCVR": {"source": "derived", "method": "CFO / NP", "unit": "percent"},
    })
    calc_values["MetricSources"] = metric_sources

    # 2Qは6ヶ月分のEPS/BPSのため、比率系指標は無効
    if per_type == "2Q":
        calc_values.update({'ROE': None, 'CFCVR': None})

    return {
        "fy_end": fy_end,
        "FinancialPeriod": _format_financial_period(fy_end, per_type),
        "RawData": raw_values,
        "CalculatedData": calc_values
    }


def _assemble_summary(metrics: MetricsResult, years_metrics: Sequence[YearEntry], analysis_years: int) -> None:
    """最新年度の要約値設定・データ可用性チェック・バリデーションを実行し metrics を更新する"""
    data_status = check_data_availability(metrics, analysis_years)
    metrics["data_availability"] = data_status.value
    metrics["data_availability_message"] = get_data_availability_message(metrics, analysis_years)

    is_valid, validation_message = validate_metrics_for_analysis(metrics, min(2, analysis_years))
    metrics["data_valid"] = is_valid
    if not is_valid:
        metrics["validation_message"] = validation_message


def calculate_metrics_flexible(
    annual_data: list[dict[str, Any]],
    analysis_years: int | None = None
) -> MetricsResult:
    """
    年度データから各種指標を計算（柔軟な年数対応）
    """
    if not annual_data:
        return {}

    if analysis_years is None:
        analysis_years = len(annual_data)

    years_data = _filter_annual_data(annual_data, analysis_years)
    if not years_data:
        return {}

    latest = years_data[0]
    metrics: MetricsResult = {
        "code": latest.get("Code"),
        "latest_fy_end": latest.get("CurFYEn"),
        "analysis_years": len(years_data),
        "available_years": len(years_data),
    }

    years_metrics = [_build_year_entry(yd) for yd in years_data]
    metrics["years"] = years_metrics

    _assemble_summary(metrics, years_metrics, analysis_years)
    return metrics
