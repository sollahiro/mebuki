import os
import logging
import keyring
from pathlib import Path
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)



class SettingsStore:
    """
    設定ストア（メモリ上で設定を保持）
    
    Electronアプリの起動時または設定変更時に、フロントエンドからAPIを通じて
    送られてくる設定値（APIキー等）を保持します。
    また、起動時にファイル（config.json）から以前の設定を読み込みます。
    """
    
    def __init__(self):
        # 環境変数に依存せず、常にデフォルト値で初期化します。
        # 設定値はElectron側からAPIを通じてアップデートされることを前提とします。
        
        user_data_path = os.environ.get("MEBUKI_USER_DATA_PATH")
        if not user_data_path:
            # macOS の標準的な Application Support パスを計算
            app_support = Path.home() / "Library" / "Application Support" / "mebuki"
            user_data_path = str(app_support)
            logger.info(f"MEBUKI_USER_DATA_PATH not set. Defaulting to: {user_data_path}")
        
        user_data_path_obj = Path(user_data_path)
        cache_dir = str(user_data_path_obj / "analysis_cache")
        data_dir = str(user_data_path_obj / "data")
        reports_dir = str(user_data_path_obj / "reports")
        
        user_data_path_obj.mkdir(parents=True, exist_ok=True)
        Path(cache_dir).mkdir(exist_ok=True)
        Path(data_dir).mkdir(exist_ok=True)
        Path(reports_dir).mkdir(exist_ok=True)
        
        logger.info(f"Using persistent storage at: {user_data_path}")

        self._settings: Dict[str, Any] = {
            "jquantsApiKey": "",
            "edinetApiKey": "",
            "analysisYears": 5,
            "jquantsPlan": "free",
            "cacheDir": cache_dir,
            "cacheEnabled": True,
            "dataDir": data_dir,
            "reportsDir": reports_dir,
            "mcpEnabled": True,
        }
        
        self.config_path = user_data_path_obj / "config.json"
        
        # ファイルから既存の設定をロード
        self._load_from_file(self.config_path)
        
        logger.info(f"Initialized SettingsStore with cache_dir: {cache_dir}, config: {self.config_path}")

    def _load_from_file(self, config_path: Path) -> None:
        """
        electron-store が作成する config.json から設定を読み込みます。
        """
        if not config_path.exists():
            logger.info(f"Config file not found at {config_path}. Using defaults.")
            return

        try:
            import json
            with open(config_path, 'r', encoding='utf-8') as f:
                config_data = json.load(f)
                
            # 各設定値をマッピング（electron-storeのキー名に合わせる）
            mapping = {
                "jquantsApiKey": "jquantsApiKey",
                "edinetApiKey": "edinetApiKey",
                "analysisYears": "analysisYears",
                "jquantsPlan": "jquantsPlan",
                "cacheEnabled": "cacheEnabled",
            }
            
            for store_key, settings_key in mapping.items():
                if store_key in config_data:
                    self._settings[settings_key] = config_data[store_key]
            
            logger.info(f"Loaded persistent settings from {config_path}")
        except Exception as e:
            logger.error(f"Failed to load settings from {config_path}: {e}")
    
    def update(self, settings: Dict[str, Any]) -> None:
        """
        設定を一括更新します。
        
        Args:
            settings: 更新する設定の辞書
        """
        self._settings.update(settings)
        self._settings["mcpEnabled"] = True
    
    def get(self, key: str, default: Any = None) -> Any:
        """
        指定されたキーの設定値を取得します。
        
        Args:
            key: 設定キー
            default: キーが存在しない場合のデフォルト値
            
        Returns:
            設定値
        """
        if key == "mcpEnabled":
            return True
            
        # APIキーの場合はキーチェーンから取得を試みる
        if key in ["jquantsApiKey", "edinetApiKey"]:
            val = keyring.get_password("mebuki", key)
            if val:
                return val
                
        return self._settings.get(key, default)
    
    def get_all(self) -> Dict[str, Any]:
        """
        全設定のコピーを取得します。
        
        Returns:
            全設定の辞書
        """
        settings = self._settings.copy()
        settings["mcpEnabled"] = True
        
        # キーチェーンから値を上書き
        for key in ["jquantsApiKey", "edinetApiKey"]:
            val = keyring.get_password("mebuki", key)
            if val:
                settings[key] = val
                
        return settings
    
    def get_masked(self) -> Dict[str, Any]:
        """
        APIキーなどの機密情報をマスクした状態で全設定を取得します。
        ログ出力やフロントエンドへの返却に使用します。
        
        Returns:
            マスク済みの設定辞書
        """
        all_settings = self.get_all()
        masked = {}
        for key, value in all_settings.items():
            if 'key' in key.lower() or 'api' in key.lower():
                if value and isinstance(value, str):
                    masked[key] = value[:4] + "****" + value[-4:] if len(value) > 8 else "****"
                else:
                    masked[key] = "****" if value else None
            else:
                masked[key] = value
        return masked
    
    @property
    def jquants_api_key(self) -> Optional[str]:
        """J-QUANTS APIキーを取得"""
        return keyring.get_password("mebuki", "jquantsApiKey") or self._settings.get("jquantsApiKey")
    
    @property
    def edinet_api_key(self) -> Optional[str]:
        """EDINET APIキーを取得"""
        return keyring.get_password("mebuki", "edinetApiKey") or self._settings.get("edinetApiKey")
    
    @property
    def analysis_years(self) -> Optional[int]:
        """分析年数を取得"""
        val = self._settings.get("analysisYears")
        try:
            return int(val) if val is not None else None
        except (ValueError, TypeError):
            return None

    @property
    def jquants_plan(self) -> str:
        """J-QUANTSプランを取得"""
        return self._settings.get("jquantsPlan", "free")

    def get_max_analysis_years(self) -> int:
        """プランに応じた最大分析年数を取得"""
        return 10 # 全プラン共通で10年に統一 (src/config.pyの仕様)

    @property
    def cache_dir(self) -> str:
        return self._settings.get("cacheDir", "cache")

    @property
    def cache_enabled(self) -> bool:
        return self._settings.get("cacheEnabled", True)

    @property
    def mcp_enabled(self) -> bool:
        return True


    @property
    def reports_dir(self) -> str:
        return self._settings.get("reportsDir", "reports")


# グローバル設定インスタンス
settings_store = SettingsStore()
