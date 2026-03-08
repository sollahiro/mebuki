"""Compatibility layer for legacy imports.

Deprecated: import from `mebuki.services.data_service`.
"""

import warnings

warnings.warn(
    "backend.services.data_service is deprecated; use mebuki.services.data_service",
    DeprecationWarning,
    stacklevel=2,
)

from mebuki.services.data_service import DataService, data_service

__all__ = ["DataService", "data_service"]
