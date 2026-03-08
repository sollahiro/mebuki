"""Compatibility layer for legacy imports.

Deprecated: import from `mebuki.services.analyzer`.
"""

import warnings

warnings.warn(
    "backend.services.analyzer is deprecated; use mebuki.services.analyzer",
    DeprecationWarning,
    stacklevel=2,
)

from mebuki.services.analyzer import IndividualAnalyzer

__all__ = ["IndividualAnalyzer"]
