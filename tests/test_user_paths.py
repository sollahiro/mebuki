import json

from mebuki.infrastructure.user_paths import default_user_data_path


def test_default_user_data_path_prefers_blue_ticker_env(monkeypatch, tmp_path) -> None:
    path = tmp_path / "custom-blue-ticker"
    monkeypatch.setenv("BLUE_TICKER_USER_DATA_PATH", str(path))
    monkeypatch.setenv("MEBUKI_USER_DATA_PATH", str(tmp_path / "legacy"))

    assert default_user_data_path() == path


def test_default_user_data_path_falls_back_to_legacy_env(monkeypatch, tmp_path) -> None:
    path = tmp_path / "legacy"
    monkeypatch.delenv("BLUE_TICKER_USER_DATA_PATH", raising=False)
    monkeypatch.setenv("MEBUKI_USER_DATA_PATH", str(path))

    assert default_user_data_path() == path


def test_default_user_data_path_migrates_legacy_default(monkeypatch, tmp_path) -> None:
    monkeypatch.delenv("BLUE_TICKER_USER_DATA_PATH", raising=False)
    monkeypatch.delenv("MEBUKI_USER_DATA_PATH", raising=False)
    monkeypatch.setenv("HOME", str(tmp_path))
    legacy_path = tmp_path / ".config" / "mebuki"
    legacy_path.mkdir(parents=True)
    (legacy_path / "config.json").write_text(json.dumps({"analysisYears": 4}), encoding="utf-8")

    path = default_user_data_path()

    assert path == tmp_path / ".config" / "blue-ticker"
    assert path.exists()
    assert not legacy_path.exists()
    assert (path / "config.json").exists()


def test_settings_store_migrates_legacy_keychain_value(monkeypatch, tmp_path) -> None:
    from mebuki.infrastructure import settings as settings_module

    monkeypatch.setenv("BLUE_TICKER_USER_DATA_PATH", str(tmp_path))
    calls: list[tuple[str, str, str]] = []
    deleted: list[tuple[str, str]] = []

    def fake_get_password(service: str, key: str) -> str | None:
        if service == settings_module.KEYCHAIN_SERVICE:
            return None
        if service == settings_module.LEGACY_KEYCHAIN_SERVICE:
            return "legacy-secret"
        return None

    def fake_set_password(service: str, key: str, value: str) -> None:
        calls.append((service, key, value))

    def fake_delete_password(service: str, key: str) -> None:
        deleted.append((service, key))

    monkeypatch.setattr(settings_module.keystore, "get_password", fake_get_password)
    monkeypatch.setattr(settings_module.keystore, "set_password", fake_set_password)
    monkeypatch.setattr(settings_module.keystore, "delete_password", fake_delete_password)

    store = settings_module.SettingsStore()

    assert store.edinet_api_key == "legacy-secret"
    assert calls == [(settings_module.KEYCHAIN_SERVICE, "edinetApiKey", "legacy-secret")]
    assert deleted == [(settings_module.LEGACY_KEYCHAIN_SERVICE, "edinetApiKey")]
