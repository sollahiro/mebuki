"""
コンテキスト判定ユーティリティ

XBRL の contextRef 属性から連結/個別・当期/前期を判定する関数群。
Duration（損益計算書・CF）と Instant（貸借対照表）の両方を提供する。
"""

from blue_ticker.constants.xbrl import (
    DURATION_CONTEXT_PATTERNS,
    PRIOR_DURATION_CONTEXT_PATTERNS,
    INSTANT_CONTEXT_PATTERNS,
    PRIOR_INSTANT_CONTEXT_PATTERNS,
)
from blue_ticker.utils.xbrl_result_types import XbrlTagElements


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


def _is_pure_context(ctx: str, patterns: list[str]) -> bool:
    """セグメント修飾のない完全一致コンテキストかどうか。"""
    return any(ctx == p for p in patterns)


def _is_pure_nonconsolidated_context(ctx: str, patterns: list[str]) -> bool:
    """個別財務諸表のセグメント修飾なしコンテキストかどうか。"""
    return any(
        ctx == f"{p}_NonConsolidatedMember" or ctx == f"{p}_NonConsolidated"
        for p in patterns
    )


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


def has_nonconsolidated_contexts(tag_elements: XbrlTagElements) -> bool:
    """連結財務諸表あり（＋個別財務諸表も添付）の書類かどうかを返す。

    True の場合、この書類は連結グループを持つため、単体フォールバックを抑止すべき。
    False の場合、単体のみ企業であり、単体フォールバックを使ってよい。

    判定条件: 同一タグに「純粋な連結コンテキスト（DURATION/INSTANT パターン完全一致）」と
    「_NonConsolidated コンテキスト」の両方が存在する場合のみ True。

    これにより、連結財務諸表なし・単体のみ申告で _NonConsolidatedMember コンテキストを
    使う企業（EDINET XBRL の一部）を誤って「連結グループあり」と判定しなくなる。
    """
    _pure_consolidated: frozenset[str] = (
        frozenset(DURATION_CONTEXT_PATTERNS) | frozenset(INSTANT_CONTEXT_PATTERNS)
    )
    for ctx_map in tag_elements.values():
        ctxs = set(ctx_map.keys())
        if any("_NonConsolidated" in c for c in ctxs) and any(c in _pure_consolidated for c in ctxs):
            return True
    return False
