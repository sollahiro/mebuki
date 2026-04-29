"""
指標計算モジュール

年度データから各種財務指標を計算します。
"""

import logging
from typing import Any
from datetime import datetime

from ..utils.converters import to_float, is_valid_value, is_valid_financial_record, extract_year_month
from mebuki.constants.financial import PERCENT, MILLION_YEN


def to_millions(value: Any) -> float | None:
    """円単位の値を百万円単位に変換"""
    if value is None:
        return None
    return value / MILLION_YEN


def calculate_adjustment_ratio(current_avg_sh: float | None, base_avg_sh: float | None) -> float | None:
    """
    株式分割等の調整倍率を計算（各年度の株式数 / 基準年度の株式数）

    過去のEPS, BPSにこの倍率を掛けることで「現在の株式数ベース」の数値に変換できます。
    """
    if base_avg_sh is not None and current_avg_sh is not None and base_avg_sh > 0:
        return current_avg_sh / base_avg_sh
    return None


def apply_adjustment(value: float | None, ratio: float | None) -> float | None:
    """値に調整倍率を適用"""
    if value is not None and ratio is not None:
        return value * ratio
    return value


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
            if y is not None and (y > current_year or (y == current_year and m > current_month)):
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
            or is_valid_value(year_data.get("Eq"))
        ):
            continue

        years_data.append(year_data)
        seen_entries.add(dedup_key)
        if per_type == "FY":
            fy_count += 1

    return years_data


def _extract_raw_values(year_data: dict[str, Any]) -> dict[str, Any]:
    """年度データから生値を抽出する"""
    return {
        'CurPerType': year_data.get("CurPerType", ""),
        'CurFYSt': year_data.get("CurFYSt", ""),
        'CurFYEn': year_data.get("CurFYEn"),
        'DiscDate': year_data.get("DiscDate", ""),
        'Sales': to_float(year_data.get("Sales")),
        'OP': to_float(year_data.get("OP")),
        'NP': to_float(year_data.get("NP")),
        'Eq': to_float(year_data.get("Eq")),
        'CFO': to_float(year_data.get("CFO")),
        'CFI': to_float(year_data.get("CFI")),
        'EPS': to_float(year_data.get("EPS")),
        'BPS': to_float(year_data.get("BPS")),
        'AvgSh': to_float(year_data.get("AvgSh")),
        'DivTotalAnn': to_float(year_data.get("DivTotalAnn")),
        'PayoutRatioAnn': to_float(year_data.get("PayoutRatioAnn")),
        'CashEq': to_float(year_data.get("CashAndCashEquivalents")) or to_float(year_data.get("CashEq")) or to_float(year_data.get("Cash")),
        'DivAnn': to_float(year_data.get("DivAnn")),
        'NxFDivAnn': to_float(year_data.get("NxFDivAnn"))
    }


def _calculate_base_values(raw_values: dict[str, Any]) -> dict[str, Any]:
    """百万円単位への変換とFCF(CFC)を計算する"""
    cfo_m = to_millions(raw_values['CFO'])
    cfi_m = to_millions(raw_values['CFI'])
    return {
        'Sales': to_millions(raw_values['Sales']),
        'OP': to_millions(raw_values['OP']),
        'NP': to_millions(raw_values['NP']),
        'Eq': to_millions(raw_values['Eq']),
        'CFO': cfo_m,
        'CFI': cfi_m,
        'CashEq': to_millions(raw_values['CashEq']),
        'PayoutRatio': raw_values['PayoutRatioAnn'] * PERCENT if raw_values['PayoutRatioAnn'] is not None else None,
        'CFC': (cfo_m + cfi_m) if (raw_values['CFO'] is not None and raw_values['CFI'] is not None) else None
    }


def _format_financial_period(fy_end: str, per_type: str) -> str:
    """決算期の文字列を返す（例: "2024年03月期" / "2024年03月期 (2Q)"）"""
    period = ""
    if fy_end:
        year, month = extract_year_month(fy_end)
        if year is not None:
            period = f"{year}年{month:02d}月期"
    if per_type == "2Q":
        period += " (2Q)"
    return period


def _build_year_entry(
    year_data: dict[str, Any],
    latest_avg_sh: float | None,
) -> dict[str, Any]:
    """1年分の指標エントリを組み立てる"""
    fy_end = year_data.get("CurFYEn")
    per_type = year_data.get("CurPerType", "FY")

    raw_values = _extract_raw_values(year_data)
    calc_values = _calculate_base_values(raw_values)

    # 収益性指標
    profit_metrics = _calculate_profitability_metrics(
        calc_values['NP'], calc_values['OP'], calc_values['Eq'], calc_values['CFO']
    )
    calc_values.update({
        'ROE': profit_metrics['roe'],
        'CFCVR': profit_metrics['cf_conversion_rate']
    })

    # 株式分割調整
    ratio = calculate_adjustment_ratio(raw_values['AvgSh'], latest_avg_sh)
    calc_values.update({
        'AdjustmentRatio': ratio,
        'AdjustedEPS': apply_adjustment(raw_values['EPS'], ratio),
        'AdjustedBPS': apply_adjustment(raw_values['BPS'], ratio)
    })

    # 2Qは6ヶ月分のEPS/BPSのため、比率系指標は無効
    if per_type == "2Q":
        calc_values.update({'ROE': None, 'CFCVR': None})

    return {
        "fy_end": fy_end,
        "FinancialPeriod": _format_financial_period(fy_end, per_type),
        "RawData": raw_values,
        "CalculatedData": calc_values
    }


def _assemble_summary(metrics: dict[str, Any], years_metrics: list[dict[str, Any]], analysis_years: int) -> None:
    """最新年度の要約値設定・データ可用性チェック・バリデーションを実行し metrics を更新する"""
    if years_metrics:
        latest_calc = years_metrics[0]["CalculatedData"]
        metrics.update({
            "latest_fcf": latest_calc.get("CFC"),
            "latest_roe": latest_calc.get("ROE"),
            "latest_eps": latest_calc.get("AdjustedEPS"),
            "latest_sales": latest_calc.get("Sales")
        })

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
) -> dict[str, Any]:
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
    latest_avg_sh = to_float(latest.get("AvgSh"))

    metrics = {
        "code": latest.get("Code"),
        "latest_fy_end": latest.get("CurFYEn"),
        "analysis_years": len(years_data),
        "available_years": len(years_data),
    }

    years_metrics = [_build_year_entry(yd, latest_avg_sh) for yd in years_data]
    metrics["years"] = years_metrics

    _assemble_summary(metrics, years_metrics, analysis_years)
    return metrics


