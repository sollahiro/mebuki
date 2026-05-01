"""
XBRL 抽出結果の TypedDict 定義
"""

from typing import NotRequired, TypedDict


class MetricComponent(TypedDict):
    label: str
    tag: str | None
    current: float | None
    prior: float | None


class GrossProfitResult(TypedDict):
    current: float | None
    prior: float | None
    method: str
    accounting_standard: str
    components: list[MetricComponent]
    reason: NotRequired[str]


class OperatingProfitResult(TypedDict):
    current: float | None
    prior: float | None
    method: str
    label: str
    accounting_standard: str
    reason: NotRequired[str]
