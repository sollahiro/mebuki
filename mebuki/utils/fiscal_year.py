"""
年度計算ユーティリティ

年度終了日から年度を抽出する共通ロジックを提供します。
"""

from datetime import datetime
from typing import Optional, Tuple


def normalize_date_format(date_str: Optional[str]) -> Optional[str]:
    """
    日付文字列をYYYY-MM-DD形式に正規化
    
    Args:
        date_str: 日付文字列（YYYY-MM-DD、YYYYMMDD、またはその他の形式）
    
    Returns:
        YYYY-MM-DD形式の日付文字列。パースできない場合はNone
    """
    if not date_str:
        return None
    
    try:
        # YYYYMMDD形式
        if len(date_str) == 8 and date_str.isdigit():
            return f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}"
        # YYYY-MM-DD形式
        elif len(date_str) >= 10:
            # 最初の10文字を取得
            date_part = date_str[:10]
            datetime.strptime(date_part, "%Y-%m-%d")
            return date_part
        # YYYY形式のみ
        elif len(date_str) == 4 and date_str.isdigit():
            return None  # 日付として不完全
    except (ValueError, TypeError):
        pass
    
    return None


def calculate_fiscal_year(fy_end: Optional[str], fy_start: Optional[str] = None) -> Optional[int]:
    """
    年度を計算。ユーザー指定により、CurFYSt（年度開始日）の年を年度とする。
    CurFYStが提供されない場合は、fy_endから推測（fy_endの年を基本とする）。
    
    Args:
        fy_end: 年度終了日（YYYY-MM-DD形式またはYYYYMMDD形式）
        fy_start: 年度開始日（YYYY-MM-DD形式またはYYYYMMDD形式）
    
    Returns:
        年度（数値）。計算できない場合はNone
    """
    if fy_start:
        normalized_start = normalize_date_format(fy_start)
        if normalized_start:
            return int(normalized_start[:4])

    if not fy_end:
        return None
    
    try:
        normalized_date = normalize_date_format(fy_end)
        if not normalized_date:
            return None
        
        # 従来の「3月決算はマイナス1年」ロジックは廃止し、開始年が不明なら終了年or実績ベースとする
        # ただし互換性のためJ-Quantsの慣習（fy_endの月に関わらず、fy_startの年が年度）に従う
        # 3月決算なら通常fy_startは前年4月なので、fy_end.year - 1 と同等になる
        period_date = datetime.strptime(normalized_date, "%Y-%m-%d")
        if period_date.month < 12:
            return period_date.year - 1
        else:
            return period_date.year
    except (ValueError, TypeError):
        pass
    
    return None


def calculate_fiscal_year_from_start(fy_start: str) -> Optional[int]:
    """
    年度開始日から年度を計算（単純に開始日の年を返す）
    """
    normalized = normalize_date_format(fy_start)
    if normalized:
        return int(normalized[:4])
    return None


def extract_fiscal_year_from_fy_end(fy_end: Optional[str]) -> str:
    """
    年度終了日から年度を抽出（文字列形式）
    
    Args:
        fy_end: 年度終了日（YYYY-MM-DD形式またはYYYYMMDD形式）
    
    Returns:
        年度文字列（例: "2023年度"）。抽出できない場合は空文字列
    """
    fiscal_year = calculate_fiscal_year(fy_end)
    if fiscal_year is not None:
        return f"{fiscal_year}年度"
    return ""


def extract_fiscal_year_number(fy_end: Optional[str]) -> Optional[int]:
    """
    年度終了日から年度を抽出（数値形式）
    
    Args:
        fy_end: 年度終了日（YYYY-MM-DD形式またはYYYYMMDD形式）
    
    Returns:
        年度（数値）。抽出できない場合はNone
    """
    return calculate_fiscal_year(fy_end)


def parse_date_string(date_str: Optional[str]) -> Optional[datetime]:
    """
    日付文字列をdatetimeオブジェクトに変換
    
    Args:
        date_str: 日付文字列（YYYY-MM-DD、YYYYMMDD、またはその他の形式）
    
    Returns:
        datetimeオブジェクト。パースできない場合はNone
    """
    if not date_str:
        return None
    
    try:
        # YYYYMMDD形式
        if len(date_str) == 8 and date_str.isdigit():
            return datetime.strptime(date_str, "%Y%m%d")
        # YYYY-MM-DD形式
        elif len(date_str) >= 10:
            return datetime.strptime(date_str[:10], "%Y-%m-%d")
    except (ValueError, TypeError):
        pass
    
    return None


def format_date_for_display(date_str: Optional[str]) -> str:
    """
    日付文字列を表示用にフォーマット
    
    Args:
        date_str: 日付文字列（YYYY-MM-DD、YYYYMMDD、またはその他の形式）
    
    Returns:
        フォーマットされた日付文字列（YYYY-MM-DD形式）。フォーマットできない場合は空文字列
    """
    normalized = normalize_date_format(date_str)
    return normalized if normalized else ""
