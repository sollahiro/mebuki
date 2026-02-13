"""
指標計算モジュール

年度データから各種財務指標を計算します。
"""

import logging
from typing import Optional, Dict, Any, List
from datetime import datetime

from ..utils.converters import to_float, is_valid_value, is_valid_financial_record


def to_millions(value):
    """円単位の値を百万円単位に変換"""
    if value is None:
        return None
    return value / 1_000_000


def calculate_adjustment_ratio(current_avg_sh: Optional[float], base_avg_sh: Optional[float]) -> Optional[float]:
    """
    株式分割等の調整倍率を計算（各年度の株式数 / 基準年度の株式数）
    
    過去のEPS, BPSにこの倍率を掛けることで「現在の株式数ベース」の数値に変換できます。
    """
    if base_avg_sh is not None and current_avg_sh is not None and base_avg_sh > 0:
        return current_avg_sh / base_avg_sh
    return None


def apply_adjustment(value: Optional[float], ratio: Optional[float]) -> Optional[float]:
    """値に調整倍率を適用"""
    if value is not None and ratio is not None:
        return value * ratio
    return value


def _calculate_profitability_metrics(np: Optional[float], op: Optional[float], eq: Optional[float], cfo: Optional[float]) -> Dict[str, Optional[float]]:
    """収益性指標（ROE, ROIC, CF変換率）の計算"""
    roe = None
    if np is not None and eq is not None and eq != 0:
        roe = (np / eq) * 100

    simple_roic = None
    if op is not None and eq is not None and eq != 0:
        simple_roic = (op / eq) * 100

    cf_conversion_rate = None
    if cfo is not None and op is not None and op != 0:
        cf_conversion_rate = (cfo / op) * 100
        
    return {
        "roe": roe,
        "simple_roic": simple_roic,
        "cf_conversion_rate": cf_conversion_rate
    }


def _calculate_market_metrics(price: Optional[float], adjusted_eps: Optional[float], adjusted_bps: Optional[float]) -> Dict[str, Optional[float]]:
    """市場指標（PER, PBR）の計算"""
    per = None
    if price is not None and adjusted_eps is not None and adjusted_eps > 0:
        per = float(price) / adjusted_eps

    pbr = None
    if price is not None and adjusted_bps is not None and adjusted_bps > 0:
        pbr = float(price) / adjusted_bps
        
    return {
        "per": per,
        "pbr": pbr
    }


from ..utils.errors import (
    check_data_availability,
    get_data_availability_message,
    validate_metrics_for_analysis,
    DataAvailability
)

logger = logging.getLogger(__name__)


def calculate_metrics_flexible(
    annual_data: List[Dict[str, Any]],
    prices: Optional[Dict[str, float]] = None,
    analysis_years: Optional[int] = None
) -> Dict[str, Any]:
    """
    年度データから各種指標を計算（柔軟な年数対応）
    """
    if not annual_data:
        return {}
    
    # 分析年数を取得
    if analysis_years is None:
        max_years = config.get_max_analysis_years()
        analysis_years = min(len(annual_data), max_years)
    
    # データフィルタリング
    today = datetime.now()
    current_year = today.year
    current_month = today.month
    
    years_data = []
    seen_fy_ends = set()
    for year_data in annual_data:
        fy_end = year_data.get("CurFYEn")
        if not fy_end or fy_end in seen_fy_ends:
            continue
        
        # 未来の年度データを除外
        try:
            if len(fy_end) == 8:
                y, m = int(fy_end[:4]), int(fy_end[4:6])
            elif len(fy_end) == 10:
                y, m = int(fy_end[:4]), int(fy_end[5:7])
            else:
                y, m = None, None
            
            if y is not None and (y > current_year or (y == current_year and m > current_month)):
                continue
        except (ValueError, IndexError):
            pass
        
        if not is_valid_financial_record(year_data):
            continue
        
        years_data.append(year_data)
        seen_fy_ends.add(fy_end)
        if len(years_data) >= analysis_years:
            break
    
    if not years_data:
        return {}
    
    # 最新年度のデータと株式数基準値
    latest = years_data[0]
    latest_avg_sh = to_float(latest.get("AvgSh"))
    
    metrics = {
        "code": latest.get("Code"),
        "latest_fy_end": latest.get("CurFYEn"),
        "analysis_years": len(years_data),
        "available_years": len(years_data),
    }
    
    years_metrics = []
    for year_data in years_data:
        fy_end = year_data.get("CurFYEn")
        
        # 数値抽出と基本変換
        raw_values = {
            'CurPerType': year_data.get("CurPerType", ""),
            'CurFYSt': year_data.get("CurFYSt", ""),
            'CurFYEn': fy_end,
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

        # 百万円単位への変換とFCF計算
        calc_values = {
            'Sales': to_millions(raw_values['Sales']),
            'OP': to_millions(raw_values['OP']),
            'NP': to_millions(raw_values['NP']),
            'Eq': to_millions(raw_values['Eq']),
            'CFO': to_millions(raw_values['CFO']),
            'CFI': to_millions(raw_values['CFI']),
            'CashEq': to_millions(raw_values['CashEq']),
            'PayoutRatio': raw_values['PayoutRatioAnn'] * 100 if raw_values['PayoutRatioAnn'] is not None else None,
            'CFC': (to_millions(raw_values['CFO']) + to_millions(raw_values['CFI'])) if (raw_values['CFO'] is not None and raw_values['CFI'] is not None) else None
        }

        # 決算期の計算 (YYYY年MM月期)
        financial_period = ""
        if fy_end:
            try:
                if len(fy_end) == 8:
                    y, m = int(fy_end[:4]), int(fy_end[4:6])
                    financial_period = f"{y}年{m:02d}月期"
                elif len(fy_end) >= 10:
                    y, m = int(fy_end[:4]), int(fy_end[5:7])
                    financial_period = f"{y}年{m:02d}月期"
            except (ValueError, IndexError):
                pass

        calc_values['FinancialPeriod'] = financial_period

        # 収益性指標の計算
        profit_metrics = _calculate_profitability_metrics(calc_values['NP'], calc_values['OP'], calc_values['Eq'], calc_values['CFO'])
        calc_values.update({
            'ROE': profit_metrics['roe'],
            'SimpleROIC': profit_metrics['simple_roic'],
            'CFCVR': profit_metrics['cf_conversion_rate']
        })

        # 株式分割調整の計算と適用
        ratio = calculate_adjustment_ratio(raw_values['AvgSh'], latest_avg_sh)
        calc_values.update({
            'AdjustmentRatio': ratio,
            'AdjustedEPS': apply_adjustment(raw_values['EPS'], ratio),
            'AdjustedBPS': apply_adjustment(raw_values['BPS'], ratio)
        })

        # 株価の取得と市場指標の計算
        price = None
        if prices and fy_end:
            price = prices.get(fy_end) or prices.get(fy_end.replace("-", ""))
        
        market_metrics = _calculate_market_metrics(price, calc_values['AdjustedEPS'], calc_values['AdjustedBPS'])
        calc_values.update({
            'Price': price,
            'PER': market_metrics['per'],
            'PBR': market_metrics['pbr']
        })

        # 決算期の文字列作成 (YYYY年MM月期)
        financial_period = ""
        if fy_end:
            if len(fy_end) == 8:
                financial_period = f"{fy_end[:4]}年{fy_end[4:6]}月期"
            elif len(fy_end) >= 10:
                financial_period = f"{fy_end[:4]}年{fy_end[5:7]}月期"

        years_metrics.append({
            "fy_end": fy_end,
            "FinancialPeriod": financial_period,
            "RawData": raw_values,
            "CalculatedData": calc_values
        })
    
    metrics["years"] = years_metrics
    
    # 最新年度の要約値を設定
    if years_metrics:
        latest_calc = years_metrics[0]["CalculatedData"]
        metrics.update({
            "latest_fcf": latest_calc.get("CFC"),
            "latest_roe": latest_calc.get("ROE"),
            "latest_eps": latest_calc.get("AdjustedEPS"),
            "latest_per": latest_calc.get("PER"),
            "latest_pbr": latest_calc.get("PBR"),
            "latest_sales": latest_calc.get("Sales")
        })
    
    # データステータスの確認と検証
    data_status = check_data_availability(metrics, analysis_years)
    metrics["data_availability"] = data_status.value
    metrics["data_availability_message"] = get_data_availability_message(metrics, analysis_years)
    
    is_valid, validation_message = validate_metrics_for_analysis(metrics, min(2, analysis_years))
    metrics["data_valid"] = is_valid
    if not is_valid:
        metrics["validation_message"] = validation_message
    
    return metrics


def calculate_quarterly_metrics(
    quarterly_data: List[Dict[str, Any]],
    prices: Optional[Dict[str, float]] = None,
    quarters: int = 8
) -> Dict[str, Any]:
    """
    四半期データから各種指標を計算（直近N四半期分）
    """
    if not quarterly_data:
        return {}
    
    quarters_data = quarterly_data[:quarters]
    if not quarters_data:
        return {}
    
    latest = quarters_data[0]
    metrics = {
        "code": latest.get("Code"),
        "latest_quarter_end": latest.get("CurFYEn"),
        "quarters": len(quarters_data),
    }
    
    quarters_metrics = []
    for quarter_data in quarters_data:
        quarter_end = quarter_data.get("_quarter_end_date") or quarter_data.get("CurFYEn")
        
        # 数値抽出
        sales = to_millions(to_float(quarter_data.get("Sales")))
        np = to_millions(to_float(quarter_data.get("NP")))
        eq_raw = to_float(quarter_data.get("Eq"))
        eq = to_millions(eq_raw)
        eps = to_float(quarter_data.get("EPS"))
        bps = to_float(quarter_data.get("BPS"))
        
        # BPS補足計算
        if bps is None:
            sh_out = to_float(quarter_data.get("ShOutFY"))
            if eq_raw is not None and sh_out is not None and sh_out > 0:
                bps = eq_raw / (sh_out * 1000)
        
        # 株価と市場指標
        price = None
        if prices and quarter_end:
            date_key = quarter_end
            if len(quarter_end) == 8:
                date_key = f"{quarter_end[:4]}-{quarter_end[4:6]}-{quarter_end[6:8]}"
            price = prices.get(date_key) or prices.get(quarter_end)
        
        market_metrics = _calculate_market_metrics(price, eps, bps)
        
        # 決算期の文字列作成 (YYYY年MM月期)
        financial_period = ""
        if quarter_end:
            if len(quarter_end) == 8:
                financial_period = f"{quarter_end[:4]}年{quarter_end[4:6]}月期"
            elif len(quarter_end) >= 10:
                financial_period = f"{quarter_end[:4]}年{quarter_end[5:7]}月期"

        quarters_metrics.append({
            "quarter_end": quarter_end,
            "FinancialPeriod": financial_period,
            "per_type": quarter_data.get("CurPerType"),
            "sales": sales,
            "np": np,
            "eq": eq,
            "eps": eps,
            "bps": bps,
            "price": price,
            "per": market_metrics['per'],
            "pbr": market_metrics['pbr'],
        })
    
    metrics["quarters_data"] = quarters_metrics
    
    # 指数化（基準 = 最も古い四半期）
    if len(quarters_metrics) >= 2:
        oldest = quarters_metrics[-1]
        
        def calc_idx(curr, base):
            return (curr / base) * 100 if curr is not None and base and base > 0 else None

        metrics.update({
            "price_index": [calc_idx(m['price'], oldest['price']) for m in quarters_metrics],
            "eps_index": [calc_idx(m['eps'], oldest['eps']) for m in quarters_metrics],
            "sales_index": [calc_idx(m['sales'], oldest['sales']) for m in quarters_metrics],
            "oldest_quarter_end": oldest.get("quarter_end")
        })
    else:
        metrics.update({
            "price_index": [],
            "eps_index": [],
            "sales_index": [],
            "oldest_quarter_end": None
        })
    
    return metrics

