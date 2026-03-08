"""Compatibility layer for legacy imports.

Deprecated: import from `mebuki.infrastructure.helpers`.
"""

import warnings

warnings.warn(
    "backend.utils.helpers is deprecated; use mebuki.infrastructure.helpers",
    DeprecationWarning,
    stacklevel=2,
)

from mebuki.infrastructure.helpers import validate_stock_code

__all__ = ["validate_stock_code"]
