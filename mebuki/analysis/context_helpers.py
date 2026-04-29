"""
Duration コンテキスト判定ユーティリティ

損益計算書・CF計算書（Duration）の contextRef 属性から
連結/個別・当期/前期を判定する関数群。
"""

from mebuki.constants.xbrl import DURATION_CONTEXT_PATTERNS, PRIOR_DURATION_CONTEXT_PATTERNS


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
