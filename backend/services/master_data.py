"""
銘柄マスタ管理サービス
"""

import logging
import os
import pandas as pd
from typing import List, Dict, Any, Optional
from pathlib import Path
from backend.settings import settings_store

logger = logging.getLogger(__name__)

class MasterDataManager:
    """銘柄マスタ（CSV）の読み込み、保持、検索を行うクラス"""
    
    def __init__(self):
        self._master_data: List[Dict[str, Any]] = []
        self._is_loaded = False
        
    def load_if_needed(self) -> bool:
        """必要に応じてマスタデータをロード"""
        if not self._is_loaded:
            return self.reload()
        return True

    def reload(self) -> bool:
        """銘柄マスタを強制的に再読み込み"""
        # 1. パスの決定
        assets_dir = os.environ.get("MEBUKI_ASSETS_PATH")
        if assets_dir:
            csv_path = Path(assets_dir) / "data_j.csv"
        else:
            csv_path = Path("assets/data_j.csv")
            
        logger.info(f"銘柄マスタを読み込んでいます: {csv_path}")
        
        if not csv_path.exists():
            logger.warning(f"銘柄マスタが見つかりません: {csv_path}")
            return False
            
        try:
            # 2. CSV読み込み（全て文字列として扱いコードの0落ちを防ぐ）
            df = pd.read_csv(csv_path, dtype=str)
            
            # 3. 辞書リストに変換（iterrowsより高速）
            raw_data = df.to_dict('records')
            
            # 4. 検索用データの事前処理
            # 許可する市場区分（個別株のみ）
            allowed_markets = ["プライム", "スタンダード", "グロース"]
            processed_data = []
            
            for row in raw_data:
                market = row.get("市場・商品区分", "")
                # 許可された区分に含まれない（ETF, REIT, PRO Market等）場合は除外
                if not any(m in market for m in allowed_markets):
                    continue
                
                # 市場名のクリーンアップ（事前に行う）
                clean_market = market.split("（")[0].split("(")[0]
                
                processed_data.append({
                    "Code": row.get("コード", ""),
                    "CoName": row.get("銘柄名", ""),
                    "CoNameUpper": row.get("銘柄名", "").upper(), # 検索高速化用
                    "S33Nm": row.get("33業種区分", ""),
                    "MktNm": clean_market,
                    "S33": row.get("33業種コード", ""),
                    "S17Nm": row.get("17業種区分", ""),
                    "S17": row.get("17業種コード", ""),
                })
            
            self._master_data = processed_data
            self._is_loaded = True
            logger.info(f"銘柄マスタを更新しました: {len(self._master_data)} 件 (元データ {len(raw_data)} 件)")
            return True
            
        except Exception as e:
            logger.error(f"銘柄マスタの読み込みに失敗しました: {e}", exc_info=True)
            return False

    def search(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        """
        コードまたは名称で銘柄を検索
        """
        self.load_if_needed()
        
        if not query:
            return []
            
        query = query.strip().upper()
        results = []
        
        for item in self._master_data:
            code = item.get("Code", "")
            name_upper = item.get("CoNameUpper", "")
            
            # マッチング
            # 1. コード完全一致 または 4桁コード前方一致
            is_match = (query == code) or (code.startswith(query) and len(query) == 4)
            # 2. 名称部分一致（大文字小文字無視）
            if not is_match:
                is_match = query in name_upper
            
            if is_match:
                results.append({
                    "code": code,
                    "name": item.get("CoName", ""),
                    "sector": item.get("S33Nm", ""),
                    "market": item.get("MktNm", ""),
                })
                
                if len(results) >= limit:
                    break
                    
        return results

    def get_by_code(self, code: str) -> Optional[Dict[str, Any]]:
        """コード指定で銘柄情報を取得"""
        self.load_if_needed()
        
        # 5桁（末尾0）と4桁の両方に対応するための正規化
        target_code = code
        if len(code) == 4:
            # 4桁の場合は末尾0を補完して探す（CSVの形式に合わせる）
            # ただしCSVが4桁のみの場合もあるので両方チェック
            pass

        for item in self._master_data:
            c = item.get("Code", "")
            if c == target_code or (len(target_code) == 4 and c == target_code + "0"):
                return item
                
        return None

# シングルトン
master_data_manager = MasterDataManager()
