"""
フォーマットユーティリティ

数値や日付のフォーマット関数を提供します。
"""

from typing import Optional

from .fiscal_year import extract_fiscal_year_from_fy_end as _extract_fiscal_year_from_fy_end


def format_currency(value: Optional[float], decimals: int = 0) -> str:
    """
    数値を百万円単位で表示
    
    Args:
        value: フォーマットする数値
        decimals: 小数点以下の桁数（デフォルト: 0）
    
    Returns:
        フォーマットされた文字列（例: "1,234.56百万円"）
    """
    if value is None:
        return "N/A"
    try:
        val = float(value)
        if val == 0:
            return "0"
        abs_val = abs(val)
        sign = "-" if val < 0 else ""
        formatted = abs_val / 1000000
        return f"{sign}{formatted:,.{decimals}f}百万円"
    except (ValueError, TypeError):
        return "N/A"


def extract_fiscal_year_from_fy_end(fy_end: Optional[str]) -> str:
    """
    年度終了日から年度を抽出
    
    Args:
        fy_end: 年度終了日（YYYY-MM-DD形式またはYYYYMMDD形式）
    
    Returns:
        年度文字列（例: "2023年度"）
    """
    return _extract_fiscal_year_from_fy_end(fy_end)

