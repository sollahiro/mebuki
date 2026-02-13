"""
エラーハンドリングとデータ不足時の対応モジュール
"""

from typing import Optional, Dict, Any, Tuple
from enum import Enum


class DataAvailability(Enum):
    """データ取得状況"""
    SUFFICIENT = "sufficient"  # 十分なデータ
    INSUFFICIENT = "insufficient"  # データ不足
    NO_DATA = "no_data"  # データなし
    PARTIAL = "partial"  # 一部データのみ


class AnalysisError(Exception):
    """分析エラーの基底クラス"""
    pass


class InsufficientDataError(AnalysisError):
    """データ不足エラー"""
    
    def __init__(
        self,
        message: str,
        required_years: int,
        available_years: int,
        metric_name: Optional[str] = None
    ):
        """
        初期化
        
        Args:
            message: エラーメッセージ
            required_years: 必要な年数
            available_years: 取得可能な年数
            metric_name: 指標名
        """
        super().__init__(message)
        self.required_years = required_years
        self.available_years = available_years
        self.metric_name = metric_name


def check_data_availability(
    metrics: Dict[str, Any],
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
    metrics: Dict[str, Any],
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
    metrics: Dict[str, Any],
    required_years: int = 2
) -> Tuple[bool, Optional[str]]:
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
    
    # 主要指標（FCF、ROE、EPS）のデータが存在するか確認
    if metrics.get("latest_fcf") is None and metrics.get("latest_roe") is None and metrics.get("latest_eps") is None:
        return False, "主要指標（FCF、ROE、EPS）のデータが不足しています"
    
    return True, None

