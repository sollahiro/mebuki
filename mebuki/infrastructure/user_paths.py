import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)

USER_DATA_ENV = "BLUE_TICKER_USER_DATA_PATH"
LEGACY_USER_DATA_ENV = "MEBUKI_USER_DATA_PATH"
CONFIG_DIR_NAME = "blue-ticker"
LEGACY_CONFIG_DIR_NAME = "mebuki"


def _default_config_root() -> Path:
    return Path.home() / ".config"


def default_user_data_path() -> Path:
    """Return the BLUE TICKER user data path, migrating the old default path when safe."""
    if os.environ.get(USER_DATA_ENV):
        return Path(os.environ[USER_DATA_ENV])

    if os.environ.get(LEGACY_USER_DATA_ENV):
        return Path(os.environ[LEGACY_USER_DATA_ENV])

    config_root = _default_config_root()
    path = config_root / CONFIG_DIR_NAME
    legacy_path = config_root / LEGACY_CONFIG_DIR_NAME
    if legacy_path.exists() and not path.exists():
        try:
            legacy_path.rename(path)
            logger.info(f"Migrated user data directory from {legacy_path} to {path}.")
        except Exception as e:
            logger.warning(f"Failed to migrate user data directory from {legacy_path} to {path}: {e}")
            return legacy_path
    return path


def candidate_secret_paths() -> list[Path]:
    """Return secret file locations in preferred lookup order."""
    paths = [default_user_data_path() / "secrets.json"]
    legacy_path = _default_config_root() / LEGACY_CONFIG_DIR_NAME / "secrets.json"
    if legacy_path not in paths:
        paths.append(legacy_path)
    return paths
