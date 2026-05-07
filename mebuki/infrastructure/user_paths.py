import os
from pathlib import Path

USER_DATA_ENV = "BLUE_TICKER_USER_DATA_PATH"
CONFIG_DIR_NAME = "blue-ticker"


def _default_config_root() -> Path:
    return Path.home() / ".config"


def default_user_data_path() -> Path:
    """Return the BLUE TICKER user data path."""
    if os.environ.get(USER_DATA_ENV):
        return Path(os.environ[USER_DATA_ENV])
    return _default_config_root() / CONFIG_DIR_NAME


def candidate_secret_paths() -> list[Path]:
    """Return secret file locations in preferred lookup order."""
    return [default_user_data_path() / "secrets.json"]
