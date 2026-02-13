"""
バックエンド共通ユーティリティ
"""

from fastapi import HTTPException

def validate_stock_code(code: str) -> str:
    """
    銘柄コードのバリデーションと正規化（4桁から5桁への変換）を行う
    
    Args:
        code: 銘柄コード（4桁または5桁）
        
    Returns:
        正規化された5桁の銘柄コード
        
    Raises:
        HTTPException: バリデーションエラー時
    """
    if not code or len(code) < 4:
        raise HTTPException(status_code=400, detail="銘柄コードは4桁以上で入力してください")
    
    # 4桁の場合は0を追加して5桁にする
    if len(code) == 4:
        return code + "0"
    
    return code
