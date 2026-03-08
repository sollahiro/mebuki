"""Compatibility layer for legacy imports.

Deprecated: import from `mebuki.prompts`.
"""

import warnings

warnings.warn(
    "backend.prompts is deprecated; use mebuki.prompts",
    DeprecationWarning,
    stacklevel=2,
)

from mebuki.prompts import LLM_PROMPTS

__all__ = ["LLM_PROMPTS"]
