"""Compatibility layer for legacy imports.

Deprecated: import from `mebuki.infrastructure.boj_client`.
"""

import warnings

warnings.warn(
    "backend.utils.boj_client is deprecated; use mebuki.infrastructure.boj_client",
    DeprecationWarning,
    stacklevel=2,
)

from mebuki.infrastructure.boj_client import BOJClient

__all__ = ["BOJClient"]
