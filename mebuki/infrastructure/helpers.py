"""
バックエンド共通ユーティリティ
"""

def validate_stock_code(code: str) -> str:
    """
    銘柄コードのバリデーションと正規化（4桁から5桁への変換）を行う
    
    Args:
        code: 銘柄コード（4桁または5桁）
        
    Returns:
        正規化された5桁の銘柄コード
        
    Raises:
        ValueError: バリデーションエラー時
    """
    if not code or not code.isalnum():
        raise ValueError("銘柄コードは英数字のみで入力してください")
    if len(code) < 4:
        raise ValueError("銘柄コードは4桁以上で入力してください")
    
    # 4桁の場合は0を追加して5桁にする
    if len(code) == 4:
        return code + "0"
    
    return code
