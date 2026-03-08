"""Compatibility layer for legacy imports.

Deprecated: import from `mebuki.services.macro_series_mapping`.
"""

import warnings

warnings.warn(
    "backend.services.macro_series_mapping is deprecated; use mebuki.services.macro_series_mapping",
    DeprecationWarning,
    stacklevel=2,
)

from mebuki.services.macro_series_mapping import (
    COST_COMMON_SERIES,
    COST_MANUFACTURING_SERIES,
    COST_SERVICE_SERIES,
    FX_SERIES,
    MONETARY_POLICY_SERIES,
)

__all__ = [
    "MONETARY_POLICY_SERIES",
    "FX_SERIES",
    "COST_MANUFACTURING_SERIES",
    "COST_SERVICE_SERIES",
    "COST_COMMON_SERIES",
]
