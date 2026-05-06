"""
OS キーチェーン / 機密情報ストア（keyring ライブラリ不要）

- macOS : security(1) コマンド経由でシステムキーチェーンを使用
- その他 : BLUE TICKER のユーザーデータディレクトリに secrets.json（パーミッション 0600）で保管
"""

import json
import logging
import platform
import subprocess
from pathlib import Path
from mebuki.infrastructure.user_paths import candidate_secret_paths, default_user_data_path

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# macOS キーチェーン
# ---------------------------------------------------------------------------

def _mac_set(service: str, key: str, value: str) -> None:
    account = f"{service}.{key}"
    # 既存エントリを削除してから追加（二重登録を防ぐ）
    subprocess.run(
        ["security", "delete-generic-password", "-s", account, "-a", service],
        capture_output=True,
    )
    subprocess.run(
        ["security", "add-generic-password", "-s", account, "-a", service, "-w", value],
        check=True,
        capture_output=True,
    )


def _mac_delete(service: str, key: str) -> None:
    account = f"{service}.{key}"
    subprocess.run(
        ["security", "delete-generic-password", "-s", account, "-a", service],
        capture_output=True,
    )


def _mac_get_legacy(service: str, key: str) -> str | None:
    """keyring ライブラリが使っていた旧形式（-s service -a key）で検索する。"""
    result = subprocess.run(
        ["security", "find-generic-password", "-s", service, "-a", key, "-w"],
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        return result.stdout.strip() or None
    return None


def _mac_get(service: str, key: str) -> str | None:
    account = f"{service}.{key}"
    result = subprocess.run(
        ["security", "find-generic-password", "-s", account, "-a", service, "-w"],
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        return result.stdout.strip() or None

    # 旧形式（keyring ライブラリ互換）からの自動マイグレーション
    legacy_value = _mac_get_legacy(service, key)
    if legacy_value:
        logger.info(f"Migrating {key} from legacy keychain format to new format.")
        try:
            _mac_set(service, key, legacy_value)
            # 旧エントリを削除
            subprocess.run(
                ["security", "delete-generic-password", "-s", service, "-a", key],
                capture_output=True,
            )
        except Exception as e:
            logger.warning(f"Failed to migrate {key} in keychain: {e}")
        return legacy_value

    return None


# ---------------------------------------------------------------------------
# ファイルフォールバック（非 macOS）
# ---------------------------------------------------------------------------

def _secrets_path() -> Path:
    return default_user_data_path() / "secrets.json"


def _file_set(key: str, value: str) -> None:
    path = _secrets_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    data: dict = {}
    if path.exists():
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            data = {}
    data[key] = value
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f)
    path.chmod(0o600)


def _file_get(key: str) -> str | None:
    for path in candidate_secret_paths():
        if not path.exists():
            continue
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            value = data.get(key)
            if value:
                return value
        except Exception:
            continue
    return None


# ---------------------------------------------------------------------------
# 公開インターフェース（keyring 互換シグネチャ）
# ---------------------------------------------------------------------------

def set_password(service: str, key: str, value: str) -> None:
    """APIキーを OS キーチェーン（または設定ファイル）に保存する。"""
    if platform.system() == "Darwin":
        _mac_set(service, key, value)
    else:
        _file_set(key, value)


def get_password(service: str, key: str) -> str | None:
    """APIキーを OS キーチェーン（または設定ファイル）から取得する。"""
    if platform.system() == "Darwin":
        return _mac_get(service, key)
    return _file_get(key)


def delete_password(service: str, key: str) -> None:
    """APIキーを OS キーチェーンから削除する。非 macOS のファイル保存では何もしない。"""
    if platform.system() == "Darwin":
        _mac_delete(service, key)
