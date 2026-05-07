from mebuki.infrastructure.user_paths import default_user_data_path


def test_default_user_data_path_uses_env(monkeypatch, tmp_path) -> None:
    path = tmp_path / "custom-blue-ticker"
    monkeypatch.setenv("BLUE_TICKER_USER_DATA_PATH", str(path))

    assert default_user_data_path() == path


def test_settings_store_reads_blue_ticker_keychain_value(monkeypatch, tmp_path) -> None:
    from mebuki.infrastructure import settings as settings_module

    monkeypatch.setenv("BLUE_TICKER_USER_DATA_PATH", str(tmp_path))

    def fake_get_password(service: str, key: str) -> str | None:
        if service == settings_module.KEYCHAIN_SERVICE:
            return "blue-secret"
        return None

    monkeypatch.setattr(settings_module.keystore, "get_password", fake_get_password)

    store = settings_module.SettingsStore()

    assert store.edinet_api_key == "blue-secret"
