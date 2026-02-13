"""
業種関連ユーティリティ
"""

from typing import List, Dict, Any
from ..api.client import JQuantsAPIClient


def get_sector_list(api_client: JQuantsAPIClient) -> List[Dict[str, str]]:
    """
    33業種分類の一覧を取得
    
    Args:
        api_client: J-QUANTS APIクライアント
        
    Returns:
        業種コードと業種名のリスト
    """
    master_data = api_client.get_equity_master()
    
    if not master_data:
        return []
    
    # 業種コードと業種名の組み合わせを取得（重複除去）
    sectors = {}
    for stock in master_data:
        sector_code = stock.get("S33")
        sector_name = stock.get("S33Nm")
        
        if sector_code and sector_name:
            sectors[sector_code] = sector_name
    
    # リストに変換してソート
    sector_list = [
        {"code": code, "name": name}
        for code, name in sorted(sectors.items())
    ]
    
    return sector_list


def get_sector_name(api_client: JQuantsAPIClient, sector_code: str) -> str:
    """
    業種コードから業種名を取得
    
    Args:
        api_client: J-QUANTS APIクライアント
        sector_code: 業種コード
        
    Returns:
        業種名。見つからない場合は空文字列
    """
    sectors = get_sector_list(api_client)
    
    for sector in sectors:
        if sector["code"] == sector_code:
            return sector["name"]
    
    return ""










