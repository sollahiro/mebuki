"""
キャッシュ管理モジュール

APIレスポンスのキャッシュ保存・読み込み機能を提供します。
"""

import json
import pickle
from datetime import datetime, date
from typing import Any, Optional, Dict
from pathlib import Path




class CacheManager:
    """
    キャッシュ管理クラス
    
    APIレスポンスをキャッシュし、日単位で有効期限を管理します。
    """
    
    def __init__(self, cache_dir: str = "cache", enabled: bool = True):
        """
        初期化
        
        Args:
            cache_dir: キャッシュディレクトリのパス
            enabled: キャッシュを有効にするか（デフォルト: True）
        """
        import logging
        logger = logging.getLogger(__name__)
        self.cache_dir = Path(cache_dir)
        self.enabled = enabled
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"CacheManager initialized. Dir: {self.cache_dir.absolute()} (enabled={self.enabled})")
    
    def _get_cache_file_path(self, key: str) -> Path:
        """キャッシュファイルのパスを取得"""
        # キーから安全なファイル名を生成（スペースやその他の特殊文字も置換）
        safe_key = key.replace("/", "_").replace("\\", "_").replace(" ", "_")
        return self.cache_dir / f"{safe_key}.pkl"
    
    def _get_metadata_file_path(self) -> Path:
        """メタデータファイルのパスを取得"""
        return self.cache_dir / "metadata.json"
    
    def _load_metadata(self) -> Dict[str, str]:
        """メタデータを読み込み"""
        metadata_path = self._get_metadata_file_path()
        if metadata_path.exists():
            try:
                with open(metadata_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                return {}
        return {}
    
    def _save_metadata(self, metadata: Dict[str, str]):
        """メタデータを保存"""
        metadata_path = self._get_metadata_file_path()
        with open(metadata_path, "w", encoding="utf-8") as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2)
    
    def get(self, key: str, skip_date_check: bool = False) -> Optional[Any]:
        """
        キャッシュからデータを取得
        
        Args:
            key: キャッシュキー
            skip_date_check: 日付チェックをスキップするか（履歴表示などで使用）
            
        Returns:
            キャッシュされたデータ。存在しないか期限切れの場合はNone
        """
        if not self.enabled:
            return None
        
        cache_file = self._get_cache_file_path(key)
        if not cache_file.exists():
            return None
        
        # メタデータを確認
        metadata = self._load_metadata()
        cache_date = metadata.get(key)
        
        # 日付チェックをスキップしない場合のみ、日付チェックを実行
        if not skip_date_check and cache_date:
            try:
                cache_datetime = datetime.fromisoformat(cache_date)
                cache_date_obj = cache_datetime.date()
                today = date.today()
                
                # 有効期限を7日間に緩和（以前は当日のみ有効だった）
                # 日次で無効化されると、毎日最初のアクセスが非常に重くなるため。
                if (today - cache_date_obj).days >= 7:
                    return None
            except (ValueError, TypeError):
                return None
        
        # キャッシュファイルを読み込み
        try:
            with open(cache_file, "rb") as f:
                return pickle.load(f)
        except (pickle.UnpicklingError, IOError):
            return None
    
    def set(self, key: str, value: Any):
        """
        キャッシュにデータを保存
        
        Args:
            key: キャッシュキー
            value: 保存するデータ
        """
        if not self.enabled:
            return
        
        cache_file = self._get_cache_file_path(key)
        
        # データを保存
        try:
            with open(cache_file, "wb") as f:
                pickle.dump(value, f)
        except (pickle.PicklingError, IOError) as e:
            # キャッシュ保存に失敗しても処理は続行
            print(f"警告: キャッシュの保存に失敗しました: {e}")
            return
        
        # メタデータを更新
        metadata = self._load_metadata()
        metadata[key] = datetime.now().isoformat()
        self._save_metadata(metadata)
    
    def clear(self, key: Optional[str] = None):
        """
        キャッシュをクリア
        
        Args:
            key: クリアするキャッシュキー。Noneの場合は全キャッシュをクリア
        """
        if key:
            cache_file = self._get_cache_file_path(key)
            if cache_file.exists():
                cache_file.unlink()
            
            # メタデータからも削除
            metadata = self._load_metadata()
            if key in metadata:
                del metadata[key]
                self._save_metadata(metadata)
        else:
            # 全キャッシュをクリア
            for cache_file in self.cache_dir.glob("*.pkl"):
                cache_file.unlink()
            
            # メタデータもクリア
            metadata_path = self._get_metadata_file_path()
            if metadata_path.exists():
                metadata_path.unlink()
    
    def get_by_code(self, code: str) -> Dict[str, Any]:
        """
        銘柄コードに関連するキャッシュを取得
        
        Args:
            code: 銘柄コード
            
        Returns:
            銘柄コードに関連するキャッシュの辞書（キー: キャッシュキー、値: キャッシュデータ）
        """
        result = {}
        metadata = self._load_metadata()
        
        # メタデータから銘柄コードを含むキーを検索
        for key in metadata.keys():
            # キャッシュキーに銘柄コードが含まれているかチェック
            # 一般的なパターン: "stock_{code}_*", "{code}_*", "*_{code}_*" など
            if code in key:
                cache_data = self.get(key)
                if cache_data is not None:
                    result[key] = cache_data
        
        return result
    
    def clear_by_code(self, code: str):
        """
        銘柄コードに関連するキャッシュを削除
        
        Args:
            code: 銘柄コード（4桁または5桁）
        """
        metadata = self._load_metadata()
        keys_to_delete = []
        
        # 4桁部分を取得（4桁と5桁の両方に対応するため）
        code_prefix = code[:4]
        
        # メタデータから銘柄コードを含むキーを検索
        for key in metadata.keys():
            # キャッシュキーに銘柄コードの4桁部分が含まれているかチェック
            if code_prefix in key:
                keys_to_delete.append(key)
        
        # 見つかったキーを削除
        for key in keys_to_delete:
            self.clear(key)










