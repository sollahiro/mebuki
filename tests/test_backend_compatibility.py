from backend.services.data_service import DataService as BackendDataService
from backend.services.data_service import data_service as backend_data_service
from backend.settings import SettingsStore as BackendSettingsStore
from backend.settings import settings_store as backend_settings_store
from mebuki.infrastructure.settings import SettingsStore
from mebuki.infrastructure.settings import settings_store
from mebuki.services.data_service import DataService
from mebuki.services.data_service import data_service


def test_backend_service_reexport_identity():
    assert BackendDataService is DataService
    assert backend_data_service is data_service


def test_backend_settings_reexport_identity():
    assert BackendSettingsStore is SettingsStore
    assert backend_settings_store is settings_store
