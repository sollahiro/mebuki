"""Compatibility layer for legacy imports.

Deprecated: import from `mebuki.services.master_data`.
"""

import warnings

warnings.warn(
    "backend.services.master_data is deprecated; use mebuki.services.master_data",
    DeprecationWarning,
    stacklevel=2,
)

from mebuki.services.master_data import MasterDataManager, master_data_manager

__all__ = ["MasterDataManager", "master_data_manager"]
