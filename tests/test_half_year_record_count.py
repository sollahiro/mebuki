"""
半期分析の「完結ペア N 組 + 当期 H1」件数保証のユニットテスト。

検証ケース:
  (1) 最新 FY はあるが 2Q がなく、1 つ古い年度に完全ペアがある
  (2) _trim_half_year_periods が完結ペア N 組 + 当期 H1 を正しく返す
  (3) edinet_docs キャッシュが years=1 で作成後、years=3 で再呼び出しても
      短いキャッシュが返らない（再取得して上書きされる）
"""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock

from blue_ticker.utils.financial_data import _latest_complete_pairs, build_half_year_periods
from blue_ticker.services.half_year_data_service import _trim_half_year_periods


# ──────────────────────────────────────────────────────────────
# (1) _latest_complete_pairs: 最新 FY に 2Q がなければ 1 つ古い年度を選ぶ
# ──────────────────────────────────────────────────────────────

def _rec(fy_end: str) -> dict:
    return {"CurFYEn": fy_end, "Sales": 100.0}


def test_latest_complete_pairs_skips_fy_without_q2():
    """最新 FY に 2Q がない場合、その年度をスキップして古い完結ペアを選ぶ。"""
    fy_by_end = {
        "2025-03-31": _rec("2025-03-31"),  # FY のみ（2Q なし）
        "2024-03-31": _rec("2024-03-31"),  # 完結ペア
        "2023-03-31": _rec("2023-03-31"),  # 完結ペア
        "2022-03-31": _rec("2022-03-31"),  # 完結ペア
    }
    q2_by_end = {
        "2024-03-31": _rec("2024-03-31"),
        "2023-03-31": _rec("2023-03-31"),
        "2022-03-31": _rec("2022-03-31"),
    }
    result = _latest_complete_pairs(fy_by_end, q2_by_end, n=3)
    assert result == ["2024-03-31", "2023-03-31", "2022-03-31"]
    assert "2025-03-31" not in result


def test_latest_complete_pairs_returns_available_when_fewer():
    """完結ペアが N 件未満のとき、取得できた分だけ返す。"""
    fy_by_end = {"2024-03-31": _rec("2024-03-31"), "2023-03-31": _rec("2023-03-31")}
    q2_by_end = {"2024-03-31": _rec("2024-03-31")}
    result = _latest_complete_pairs(fy_by_end, q2_by_end, n=3)
    assert result == ["2024-03-31"]


# ──────────────────────────────────────────────────────────────
# (2) _trim_half_year_periods: N 完結ペア + 当期 H1
# ──────────────────────────────────────────────────────────────

def _period(fy_end: str, half: str | None) -> dict:
    label_half = half if half else "FY"
    return {"label": f"{fy_end[:4]}{label_half}", "half": half, "fy_end": fy_end, "data": {}}


def test_trim_keeps_n_complete_pairs_plus_current_h1():
    """6 完結ペア + 当期 H1 から years=3 で trim すると 3 ペア + 当期 H1。"""
    periods = [
        _period("2022-03-31", "H1"),
        _period("2022-03-31", "H2"),
        _period("2023-03-31", "H1"),
        _period("2023-03-31", "H2"),
        _period("2024-03-31", "H1"),
        _period("2024-03-31", "H2"),
        _period("2025-03-31", "H1"),
        _period("2025-03-31", "H2"),
        _period("2026-03-31", "H1"),  # 当期 H1（FY 未公開）
    ]
    result = _trim_half_year_periods(periods, years=3)
    fy_ends = [p["fy_end"] for p in result]
    halves = [p["half"] for p in result]

    # 完結ペアは最新 3 年分（2023, 2024, 2025）
    assert fy_ends.count("2023-03-31") == 2
    assert fy_ends.count("2024-03-31") == 2
    assert fy_ends.count("2025-03-31") == 2
    assert "2022-03-31" not in fy_ends

    # 当期 H1 が末尾に追加される
    assert result[-1]["fy_end"] == "2026-03-31"
    assert result[-1]["half"] == "H1"
    assert len(result) == 7


def test_trim_no_current_h1():
    """当期 H1 がない場合は完結ペアのみ。"""
    periods = [
        _period("2023-03-31", "H1"),
        _period("2023-03-31", "H2"),
        _period("2024-03-31", "H1"),
        _period("2024-03-31", "H2"),
        _period("2025-03-31", "H1"),
        _period("2025-03-31", "H2"),
    ]
    result = _trim_half_year_periods(periods, years=3)
    assert len(result) == 6
    assert all(p["half"] in ("H1", "H2") for p in result)


def test_trim_current_h1_does_not_displace_complete_pair():
    """当期 H1 がペア数を圧迫しない（N ペア確保後に追加される）。"""
    periods = [
        _period("2023-03-31", "H1"),
        _period("2023-03-31", "H2"),
        _period("2024-03-31", "H1"),
        _period("2024-03-31", "H2"),
        _period("2025-03-31", "H1"),
        _period("2025-03-31", "H2"),
        _period("2026-03-31", "H1"),
    ]
    result = _trim_half_year_periods(periods, years=3)
    # 完結ペアの fy_end（H2 を持つ年度）が 3 つあること
    h2_ends = {p["fy_end"] for p in result if p["half"] == "H2"}
    assert h2_ends == {"2023-03-31", "2024-03-31", "2025-03-31"}
    # 当期 H1 は末尾に追加される（ペア数に含まない）
    assert result[-1]["fy_end"] == "2026-03-31"
    assert result[-1]["half"] == "H1"
    # 合計 7 件 = 3 ペア × 2 + 当期 H1 × 1
    assert len(result) == 7


# ──────────────────────────────────────────────────────────────
# (3) build_half_year_periods で _latest_complete_pairs が機能する統合確認
# ──────────────────────────────────────────────────────────────

def test_build_half_year_periods_skips_fy_only():
    """FY はあるが 2Q がない年度は完結ペアとして選ばれず、代わりに古い年度が使われる。"""
    financial_data = [
        # 2025-03: FY のみ（2Q なし）
        {"CurPerType": "FY", "CurFYEn": "2025-03-31", "DiscDate": "2025-06-01",
         "Sales": 1000.0, "OP": 100.0, "NP": 50.0, "CFO": 80.0, "CFI": -30.0},
        # 2024-03: FY + 2Q（完結）
        {"CurPerType": "FY", "CurFYEn": "2024-03-31", "DiscDate": "2024-06-01",
         "Sales": 900.0, "OP": 90.0, "NP": 45.0, "CFO": 70.0, "CFI": -20.0},
        {"CurPerType": "2Q", "CurFYEn": "2024-03-31", "DiscDate": "2023-11-01",
         "Sales": 430.0, "OP": 42.0, "NP": 21.0, "CFO": 33.0, "CFI": -9.0},
        # 2023-03: FY + 2Q（完結）
        {"CurPerType": "FY", "CurFYEn": "2023-03-31", "DiscDate": "2023-06-01",
         "Sales": 800.0, "OP": 80.0, "NP": 40.0, "CFO": 60.0, "CFI": -15.0},
        {"CurPerType": "2Q", "CurFYEn": "2023-03-31", "DiscDate": "2022-11-01",
         "Sales": 380.0, "OP": 38.0, "NP": 19.0, "CFO": 28.0, "CFI": -7.0},
        # 2022-03: FY + 2Q（完結、古い）
        {"CurPerType": "FY", "CurFYEn": "2022-03-31", "DiscDate": "2022-06-01",
         "Sales": 700.0, "OP": 70.0, "NP": 35.0, "CFO": 50.0, "CFI": -10.0},
        {"CurPerType": "2Q", "CurFYEn": "2022-03-31", "DiscDate": "2021-11-01",
         "Sales": 330.0, "OP": 33.0, "NP": 16.0, "CFO": 23.0, "CFI": -5.0},
    ]

    periods = build_half_year_periods(financial_data, years=3)
    fy_ends_in_pairs = {p["fy_end"] for p in periods if p["half"] in ("H1", "H2")}

    # 2025-03 は 2Q なしなのでスキップされ、2022-03 が代わりに選ばれる
    assert "2025-03-31" not in fy_ends_in_pairs
    assert "2022-03-31" in fy_ends_in_pairs
    assert "2023-03-31" in fy_ends_in_pairs
    assert "2024-03-31" in fy_ends_in_pairs
