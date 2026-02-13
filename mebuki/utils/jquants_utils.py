"""
J-QUANTSデータ処理ユーティリティ

J-QUANTSの財務データを解析・変換するための共通ロジックを提供します。
"""

import logging
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime

from .fiscal_year import calculate_fiscal_year_from_start

logger = logging.getLogger(__name__)


def prepare_edinet_search_data(
    financial_data: List[Dict[str, Any]],
    max_records: int = 2
) -> Tuple[List[Dict[str, Any]], List[int]]:
    """
    J-QUANTS財務データからEDINET検索用データを準備
    
    Args:
        financial_data: J-QUANTS APIから取得した財務データのリスト
        max_records: 取得する最大レコード数
    
    Returns:
        (annual_data_for_edinet, years_list)
    """
    if not financial_data:
        return [], []
    
    # 有報・四半期・半期の各データを抽出（FY, 2Q, Q2に対応）
    target_records = [
        r for r in financial_data 
        if r.get("CurPerType") in ["FY", "2Q", "Q2"]
    ]
    
    # 期間ごと（年度×種別）にグループ化し、最も早い開示日（DiscDate）を持つレコードを採用する
    # これにより、訂正等でレコードが複数ある場合でも、最初の開示日を基準にEDINET検索を行い、
    # 検索開始日が遅くなることを防ぐ。
    period_groups: Dict[Tuple[int, str], List[Dict[str, Any]]] = {}
    
    for record in target_records:
        fy_st = record.get("CurFYSt", "")
        fiscal_year = calculate_fiscal_year_from_start(fy_st) if fy_st else None
        
        if not fiscal_year:
            continue
            
        ptype = record.get("CurPerType", "FY")
        # 2QとQ2を正規化
        if ptype == "Q2":
            ptype = "2Q"
            
        key = (fiscal_year, ptype)
        if key not in period_groups:
            period_groups[key] = []
        period_groups[key].append(record)
        
    # 各グループから代表レコード（DiscDateが最小のもの）を選択
    representatives = []
    for key, records in period_groups.items():
        # DiscDateで昇順ソート（早い順）
        records.sort(key=lambda x: x.get("DiscDate", ""))
        best_record = records[0]
        # 計算したfiscal_yearを付与しておく
        best_record["fiscal_year"] = key[0]
        # 正規化したptypeを使うか、元のままにするか。
        # 後続処理でCurPerTypeを使うので、元の辞書を使いつつfiscal_yearを追加してる。
        # ただしprepare_edinet_search_dataの戻り値の辞書作成時にCurPerTypeを入れている。
        # ここでは後でソートや抽出に使うためにリストに加える
        representatives.append(best_record)

    # 代表レコードを会計期間終了日で降順ソート（新しい順）
    # これにより、確定決算（FY）と四半期（2Q）が混在していても、より新しい期間の報告書を優先的に検索できる。
    representatives.sort(key=lambda x: x.get("CurPerEn", "") or x.get("CurFYEn", ""), reverse=True)
    
    latest_records = representatives[:max_records]
    
    annual_data_for_edinet = []
    for record in latest_records:
        # fiscal_yearは上で計算済みだが、念のため取得（辞書に入れたので）
        fiscal_year = record.get("fiscal_year")
        
        annual_data_for_edinet.append({
            "CurFYEn": record.get("CurFYEn", ""),
            "CurPerEn": record.get("CurPerEn", ""),
            "CurFYSt": record.get("CurFYSt", ""),
            "DiscDate": record.get("DiscDate", ""),
            "CurPerType": record.get("CurPerType", "FY"),
            "fiscal_year": fiscal_year
        })
    
    years_list = sorted(list(set(d.get("fiscal_year") for d in annual_data_for_edinet)), reverse=True)
    
    if not years_list:
        current_year = datetime.now().year
        years_list = [current_year, current_year - 1, current_year - 2]
        
    return annual_data_for_edinet, years_list
