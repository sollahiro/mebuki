"""
共通変換・検証ユーティリティモジュール

型変換、値の検証、日付変換などの共通関数を提供します。
"""

import math
import logging
from typing import Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


# =============================================================================
# 型変換関数
# =============================================================================

def to_float(value: Any) -> Optional[float]:
    """
    値をfloatに変換
    
    Args:
        value: 変換する値（None、数値、文字列など）
        
    Returns:
        float値。変換できない場合はNone
    """
    if value is None:
        return None
    if isinstance(value, (int, float)):
        result = float(value)
        # NaNチェック
        if math.isnan(result):
            return None
        return result
    if isinstance(value, str):
        # 日本語のダッシュやカンマを除去
        value = value.replace(",", "").replace("－", "").replace("-", "-").strip()
        if not value:
            return None
        try:
            result = float(value)
            if math.isnan(result):
                return None
            return result
        except (ValueError, TypeError):
            return None
    return None


def to_int(value: Any) -> Optional[int]:
    """
    値をintに変換
    
    Args:
        value: 変換する値（None、数値、文字列など）
        
    Returns:
        int値。変換できない場合はNone
    """
    if value is None:
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        if math.isnan(value):
            return None
        return int(value)
    if isinstance(value, str):
        try:
            return int(float(value))
        except (ValueError, TypeError):
            return None
    return None


# =============================================================================
# 値の検証関数
# =============================================================================

def is_nan(value: Any) -> bool:
    """
    値がNaNかどうかを判定
    
    Args:
        value: 検証する値
        
    Returns:
        NaNの場合True
    """
    if value is None:
        return False
    
    # float型のNaNチェック
    try:
        if isinstance(value, float) and math.isnan(value):
            return True
    except (TypeError, ValueError):
        pass
    
    # pandasのNaNチェック
    try:
        import pandas as pd
        if pd.isna(value):
            return True
    except (ImportError, TypeError, AttributeError):
        pass
    
    # 文字列をfloatに変換してNaNチェック
    try:
        num_value = float(value)
        if math.isnan(num_value):
            return True
    except (ValueError, TypeError):
        pass
    
    return False


def is_valid_value(value: Any) -> bool:
    """
    値が有効かどうかを判定（None、NaN、空文字列、0は無効）
    
    主に財務データの有効性チェックに使用します。
    
    Args:
        value: 検証する値
        
    Returns:
        有効な場合True
    """
    if value is None:
        return False
    if value == "":
        return False
    if is_nan(value):
        return False
    
    # 数値に変換して0チェック
    try:
        num_value = float(value)
        if math.isnan(num_value):
            return False
        return num_value != 0
    except (ValueError, TypeError):
        return False


def is_valid_financial_record(record: dict) -> bool:
    """
    財務レコードが有効かどうかを判定
    
    EDINET検索に必要な年度情報（CurFYEn）があれば、財務データが欠けていても
    一旦有効と判定するように緩和（分析側で適宜チェックする）
    
    Args:
        record: 財務データのレコード（辞書型）
        
    Returns:
        有効なデータ、またはEDINET検索に必要なメタデータがあればTrue
    """
    # 財務データの存在チェック
    sales = record.get("Sales")
    op = record.get("OP")
    np_value = record.get("NP")
    eq = record.get("Eq")
    
    has_financial_data = (
        is_valid_value(sales) or
        is_valid_value(op) or
        is_valid_value(np_value) or
        is_valid_value(eq)
    )
    
    if has_financial_data:
        return True
        
    # 財務データがなくても、EDINET検索に必要な基本的な日付情報があれば有効とする
    fy_end = record.get("CurFYEn")
    disc_date = record.get("DiscDate")
    if fy_end and disc_date:
        return True
        
    return False


# =============================================================================
# 日付変換関数
# =============================================================================

def normalize_date(date_str: str) -> Optional[str]:
    """
    日付文字列をYYYY-MM-DD形式に正規化
    
    Args:
        date_str: 日付文字列（YYYYMMDD または YYYY-MM-DD形式）
        
    Returns:
        YYYY-MM-DD形式の文字列。変換できない場合はNone
    """
    if not date_str:
        return None
    
    date_str = date_str.strip()
    
    # 既にYYYY-MM-DD形式の場合
    if len(date_str) == 10 and date_str[4] == '-' and date_str[7] == '-':
        return date_str
    
    # YYYYMMDD形式の場合
    if len(date_str) == 8 and date_str.isdigit():
        return f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}"
    
    # その他の形式は変換を試みる
    try:
        dt = parse_date(date_str)
        if dt:
            return format_date(dt)
    except Exception:
        pass
    
    return None


def parse_date(date_str: str) -> Optional[datetime]:
    """
    日付文字列をdatetimeオブジェクトに変換
    
    Args:
        date_str: 日付文字列（YYYYMMDD、YYYY-MM-DD、YYYY/MM/DD形式など）
        
    Returns:
        datetimeオブジェクト。変換できない場合はNone
    """
    if not date_str:
        return None
    
    date_str = date_str.strip()
    
    # 複数の形式を試す
    formats = [
        "%Y-%m-%d",      # YYYY-MM-DD
        "%Y%m%d",        # YYYYMMDD
        "%Y/%m/%d",      # YYYY/MM/DD
        "%Y-%m-%dT%H:%M:%S",  # ISO形式
        "%Y-%m-%d %H:%M:%S",  # 日時形式
    ]
    
    for fmt in formats:
        try:
            return datetime.strptime(date_str[:len(date_str)], fmt)
        except (ValueError, TypeError):
            continue
    
    # 最初の10文字だけで再試行（タイムゾーン情報を除去）
    if len(date_str) > 10:
        try:
            return datetime.strptime(date_str[:10], "%Y-%m-%d")
        except (ValueError, TypeError):
            pass
    
    return None


def format_date(dt: datetime, fmt: str = "%Y-%m-%d") -> str:
    """
    datetimeオブジェクトを文字列に変換
    
    Args:
        dt: datetimeオブジェクト
        fmt: フォーマット文字列（デフォルト: YYYY-MM-DD）
        
    Returns:
        フォーマットされた日付文字列
    """
    return dt.strftime(fmt)


def extract_year_month(date_str: str) -> tuple[Optional[int], Optional[int]]:
    """
    日付文字列から年と月を抽出
    
    Args:
        date_str: 日付文字列（YYYYMMDD または YYYY-MM-DD形式）
        
    Returns:
        (年, 月) のタプル。抽出できない場合は (None, None)
    """
    if not date_str:
        return None, None
    
    date_str = date_str.strip()
    
    try:
        # YYYYMMDD形式
        if len(date_str) == 8 and date_str.isdigit():
            return int(date_str[:4]), int(date_str[4:6])
        
        # YYYY-MM-DD形式
        if len(date_str) >= 10 and date_str[4] == '-':
            return int(date_str[:4]), int(date_str[5:7])
        
        # その他の形式はparse_dateを使用
        dt = parse_date(date_str)
        if dt:
            return dt.year, dt.month
    except (ValueError, TypeError, IndexError):
        pass
    
    return None, None


def is_future_date(date_str: str, reference: Optional[datetime] = None) -> bool:
    """
    日付が未来かどうかを判定
    
    Args:
        date_str: 判定する日付文字列
        reference: 基準日（デフォルト: 現在日時）
        
    Returns:
        未来の日付の場合True
    """
    if not date_str:
        return False
    
    dt = parse_date(date_str)
    if not dt:
        return False
    
    if reference is None:
        reference = datetime.now()
    
    return dt > reference
