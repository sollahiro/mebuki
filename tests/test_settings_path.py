import os
import unittest
from pathlib import Path

from mebuki.infrastructure.settings import SettingsStore


class TestSettingsPath(unittest.TestCase):
    def test_default_paths(self):
        """環境変数がない場合のデフォルトパスを確認"""
        if "MEBUKI_USER_DATA_PATH" in os.environ:
            del os.environ["MEBUKI_USER_DATA_PATH"]

        store = SettingsStore()
        expected_base = Path.home() / ".config" / "mebuki"
        self.assertEqual(store.cache_dir, str(expected_base / "analysis_cache"))
        self.assertEqual(store.get("dataDir"), str(expected_base / "data"))

    def test_custom_paths(self):
        """環境変数がある場合のカスタムパスを確認"""
        custom_path = "/tmp/mebuki_test_data"
        os.environ["MEBUKI_USER_DATA_PATH"] = custom_path

        store = SettingsStore()
        expected_cache = str(Path(custom_path) / "analysis_cache")
        expected_data = str(Path(custom_path) / "data")

        self.assertEqual(store.cache_dir, expected_cache)
        self.assertEqual(store.get("dataDir"), expected_data)

        del os.environ["MEBUKI_USER_DATA_PATH"]


if __name__ == "__main__":
    unittest.main()
