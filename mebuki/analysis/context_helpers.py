"""
コンテキスト判定ユーティリティ

XBRL の contextRef 属性から連結/個別・当期/前期を判定する関数群。
Duration（損益計算書・CF）と Instant（貸借対照表）の両方を提供する。
"""

from mebuki.constants.xbrl import (
    DURATION_CONTEXT_PATTERNS,
    PRIOR_DURATION_CONTEXT_PATTERNS,
    INSTANT_CONTEXT_PATTERNS,
    PRIOR_INSTANT_CONTEXT_PATTERNS,
)


def _is_consolidated_duration(ctx: str) -> bool:
    """連結の当期損益コンテキストかどうか。"""
    return any(p in ctx for p in DURATION_CONTEXT_PATTERNS) and "_NonConsolidated" not in ctx


def _is_consolidated_prior_duration(ctx: str) -> bool:
    """連結の前期損益コンテキストかどうか。"""
    return any(p in ctx for p in PRIOR_DURATION_CONTEXT_PATTERNS) and "_NonConsolidated" not in ctx


def _is_nonconsolidated_duration(ctx: str) -> bool:
    """個別の当期損益コンテキストかどうか。"""
    return any(p in ctx for p in DURATION_CONTEXT_PATTERNS) and "_NonConsolidated" in ctx


def _is_nonconsolidated_prior_duration(ctx: str) -> bool:
    """個別の前期損益コンテキストかどうか。"""
    return any(p in ctx for p in PRIOR_DURATION_CONTEXT_PATTERNS) and "_NonConsolidated" in ctx


def _is_consolidated_instant(ctx: str) -> bool:
    """連結の期末残高コンテキストかどうか。"""
    return any(p in ctx for p in INSTANT_CONTEXT_PATTERNS) and "_NonConsolidated" not in ctx


def _is_consolidated_prior_instant(ctx: str) -> bool:
    """連結の前期末残高コンテキストかどうか。"""
    return any(p in ctx for p in PRIOR_INSTANT_CONTEXT_PATTERNS) and "_NonConsolidated" not in ctx


def _is_nonconsolidated_instant(ctx: str) -> bool:
    """個別の期末残高コンテキストかどうか。"""
    return any(p in ctx for p in INSTANT_CONTEXT_PATTERNS) and "_NonConsolidated" in ctx


def _is_nonconsolidated_prior_instant(ctx: str) -> bool:
    """個別の前期末残高コンテキストかどうか。"""
    return any(p in ctx for p in PRIOR_INSTANT_CONTEXT_PATTERNS) and "_NonConsolidated" in ctx
