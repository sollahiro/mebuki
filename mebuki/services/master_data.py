"""
銘柄マスタ管理サービス
"""

import logging
import os
import pandas as pd
import unicodedata
from typing import List, Dict, Any, Optional
from pathlib import Path
from mebuki.infrastructure.settings import settings_store

logger = logging.getLogger(__name__)

class MasterDataManager:
    """銘柄マスタ（CSV）の読み込み、保持、検索を行うクラス"""
    
    def __init__(self):
        self._is_loaded = False
        
    def _normalize_name(self, name: str) -> str:
        """
        検索用の名称正規化
        1. NFKC正規化（全角英数を半角に、半角カナを全角に）
        2. 大文字化
        3. 中点（・, ･）の除去
        4. スペース（全角・半角）の除去
        """
        if not name:
            return ""
        # 1. NFKC + Upper
        normalized = unicodedata.normalize('NFKC', name).upper()
        # 2. 中点の除去
        normalized = normalized.replace('・', '').replace('･', '')
        # 3. スペースの除去
        normalized = "".join(normalized.split())
        return normalized

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
            # 探索候補
            candidates = [
                Path("assets/data_j.csv"),
                Path(__file__).parent.parent.parent / "assets" / "data_j.csv",
                # インストール環境を想定
                Path(settings_store.user_data_path) / "assets" / "data_j.csv",
            ]
            csv_path = None
            for p in candidates:
                if p.exists():
                    csv_path = p
                    break
            
            if not csv_path:
                csv_path = Path("assets/data_j.csv") # デフォルト
            
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
                
                # 検索用正規化名称
                normalized_name = self._normalize_name(row.get("銘柄名", ""))
                
                processed_data.append({
                    "Code": row.get("コード", ""),
                    "CoName": row.get("銘柄名", ""),
                    "CoNameUpper": row.get("銘柄名", "").upper(), # 互換性維持のため残すが、基本はNormalizedを使用
                    "CoNameNormalized": normalized_name, # 正規化済み名称
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
            
        query_normalized = self._normalize_name(query)
        results = []
        
        for item in self._master_data:
            code = item.get("Code", "")
            name_upper = item.get("CoNameUpper", "")
            name_normalized = item.get("CoNameNormalized", "")
            
            # マッチング
            # 1. コード完全一致 または 4桁コード前方一致
            query_upper = query.strip().upper() # コード比較用には単純なUpperを使用
            is_match = (query_upper == code) or (code.startswith(query_upper) and len(query_upper) == 4)
            # 2. 名称部分一致（正規化済み名称で比較）
            if not is_match:
                is_match = (query_normalized in name_normalized)
            
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
        
        if not code:
            return None
            
        target_code = str(code).strip()
        
        # 1. 直接一致
        for item in self._master_data:
            c = item.get("Code", "")
            if c == target_code:
                return item
                
        # 2. 5桁（末尾0）から4桁への正規化一致を試す
        if len(target_code) == 5 and target_code.endswith("0"):
            normalized = target_code[:4]
            for item in self._master_data:
                if item.get("Code") == normalized:
                    return item
        
        # 3. 4桁から5桁（CSV側が5桁の場合）
        if len(target_code) == 4:
            normalized = target_code + "0"
            for item in self._master_data:
                if item.get("Code") == normalized:
                    return item
                    
        return None

# シングルトン
master_data_manager = MasterDataManager()
