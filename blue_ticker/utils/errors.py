"""
エラーハンドリングとデータ不足時の対応モジュール
"""

from typing import Any
from collections.abc import Mapping
from enum import Enum


class DataAvailability(Enum):
    """データ取得状況"""
    SUFFICIENT = "sufficient"  # 十分なデータ
    INSUFFICIENT = "insufficient"  # データ不足
    NO_DATA = "no_data"  # データなし
    PARTIAL = "partial"  # 一部データのみ


def check_data_availability(
    metrics: Mapping[str, Any],
    required_years: int
) -> DataAvailability:
    """
    データ取得状況をチェック
    
    Args:
        metrics: 計算済み指標
        required_years: 必要な年数
        
    Returns:
        データ取得状況
    """
    years = metrics.get("years", [])
    available_years = metrics.get("available_years", len(years))
    
    if available_years == 0:
        return DataAvailability.NO_DATA
    elif available_years < required_years:
        return DataAvailability.INSUFFICIENT
    elif available_years == required_years:
        return DataAvailability.SUFFICIENT
    else:
        return DataAvailability.SUFFICIENT


def get_data_availability_message(
    metrics: Mapping[str, Any],
    required_years: int
) -> str:
    """
    データ取得状況のメッセージを取得
    
    Args:
        metrics: 計算済み指標
        required_years: 必要な年数
        
    Returns:
        メッセージ
    """
    years = metrics.get("years", [])
    available_years = metrics.get("available_years", len(years))
    
    if available_years == 0:
        return "データが取得できませんでした"
    elif available_years < required_years:
        return f"{required_years}年分のデータが必要ですが、{available_years}年分しか取得できませんでした"
    else:
        return f"{available_years}年分のデータを取得しました"


def validate_metrics_for_analysis(
    metrics: Mapping[str, Any],
    required_years: int = 2
) -> tuple[bool, str | None]:
    """
    分析に必要なデータが揃っているか検証
    
    Args:
        metrics: 計算済み指標
        required_years: 必要な年数
        
    Returns:
        (検証結果, エラーメッセージ)
    """
    years = metrics.get("years", [])
    available_years = metrics.get("available_years", len(years))
    
    if available_years < required_years:
        message = get_data_availability_message(metrics, required_years)
        return False, message
    
    latest_year = years[0] if isinstance(years, list) and years and isinstance(years[0], dict) else {}
    calculated = latest_year.get("CalculatedData") if isinstance(latest_year, dict) else {}
    latest_metrics = calculated if isinstance(calculated, Mapping) else {}

    # 主要指標（FCF、ROE、EPS）のデータが存在するか確認
    if (
        latest_metrics.get("CFC") is None
        and latest_metrics.get("ROE") is None
        and latest_metrics.get("AdjustedEPS") is None
    ):
        return False, "主要指標（FCF、ROE、EPS）のデータが不足しています"
    
    return True, None
