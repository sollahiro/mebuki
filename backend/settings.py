"""Compatibility layer for legacy imports.

Deprecated: import from `mebuki.infrastructure.settings`.
"""

import warnings

warnings.warn(
    "backend.settings is deprecated; use mebuki.infrastructure.settings",
    DeprecationWarning,
    stacklevel=2,
)

from mebuki.infrastructure.settings import SettingsStore, settings_store

__all__ = ["SettingsStore", "settings_store"]
