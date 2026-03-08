"""Compatibility layer for legacy imports.

Deprecated: import from `mebuki.services.macro_analyzer`.
"""

import warnings

warnings.warn(
    "backend.services.macro_analyzer is deprecated; use mebuki.services.macro_analyzer",
    DeprecationWarning,
    stacklevel=2,
)

from mebuki.services.macro_analyzer import MacroAnalyzer, macro_analyzer

__all__ = ["MacroAnalyzer", "macro_analyzer"]
