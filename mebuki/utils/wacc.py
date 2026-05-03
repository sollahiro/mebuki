"""
WACC 計算ユーティリティ

財務省公表の10年国債利回りCSVをRfとして使い、CAPM + WACC を計算する。
β=1.0、MRP=5.5% は暫定固定値。
"""

import csv
import io
import logging
import re
import urllib.request
from datetime import date, timedelta

from mebuki.constants.financial import (
    PERCENT,
    WACC_DEFAULT_BETA,
    WACC_LABEL_COST_OF_DEBT_OUT_OF_RANGE,
    WACC_LABEL_MISSING_INPUT,
    WACC_LABEL_TAX_RATE_OUT_OF_RANGE,
    WACC_MARKET_RISK_PREMIUM,
    WACC_RF_FALLBACK,
)

logger = logging.getLogger(__name__)

_MOF_JGB_CACHE_KEY = "mof_rf_rates"
_MOF_JGB_CACHE_TTL_DAYS = 1


def _parse_mof_date(date_str: str) -> str | None:
    """和暦日付 (R8.4.23, H31.3.31, S49.9.24) → YYYY-MM-DD。解析失敗時は None。"""
    m = re.match(r'^([SRHT])(\d+)\.(\d+)\.(\d+)$', date_str.strip())
    if not m:
        return None
    era, yr, mo, dy = m.group(1), int(m.group(2)), int(m.group(3)), int(m.group(4))
    offsets = {'S': 1925, 'H': 1988, 'R': 2018, 'T': 1911}
    return f"{yr + offsets[era]:04d}-{mo:02d}-{dy:02d}"


def _fetch_csv_rates(url: str) -> dict[str, float]:
    """MOF CSV URL から {YYYY-MM-DD: 10年利回り(小数)} を返す。"""
    with urllib.request.urlopen(url, timeout=15) as resp:
        raw = resp.read()
    for enc in ("utf-8-sig", "shift-jis", "cp932"):
        try:
            text = raw.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    else:
        raise ValueError("encoding unknown")

    reader = csv.reader(io.StringIO(text))
    next(reader)  # 1行目はタイトル行（例: 国債金利情報...）スキップ
    header = next(reader)
    col_idx = next((i for i, h in enumerate(header) if "10年" in h), None)
    if col_idx is None:
        raise ValueError("10年列未発見")

    rates: dict[str, float] = {}
    for row in reader:
        date_str = _parse_mof_date(row[0]) if row else None
        if date_str and len(row) > col_idx and row[col_idx].strip():
            try:
                rates[date_str] = float(row[col_idx]) / 100
            except ValueError:
                pass
    return rates


def load_rf_rates(cache_dir: str) -> dict[str, float]:
    """MOF CSV から {YYYY-MM-DD: 10年利回り(小数)} の全履歴を返す（1日キャッシュ）。
    jgbcm_all.csv（前月末まで）と jgbcm.csv（当月分）をマージして返す。
    両方失敗した場合は空 dict を返す。
    """
    from mebuki import __version__
    from mebuki.utils.cache import CacheManager
    from mebuki.constants.api import MOF_JGB_ALL_CSV_URL, MOF_JGB_CURRENT_CSV_URL

    _CACHE_VERSION = ".".join(__version__.split(".")[:2])
    cache = CacheManager(cache_dir=cache_dir, ttl_days=_MOF_JGB_CACHE_TTL_DAYS)
    cached = cache.get(_MOF_JGB_CACHE_KEY)
    if cached and cached.get("_cache_version") == _CACHE_VERSION:
        return cached["rates"]

    rates: dict[str, float] = {}
    try:
        rates.update(_fetch_csv_rates(MOF_JGB_ALL_CSV_URL))
    except Exception as e:
        logger.warning(f"MOF jgbcm_all.csv 取得失敗: {e}")
    try:
        rates.update(_fetch_csv_rates(MOF_JGB_CURRENT_CSV_URL))
    except Exception as e:
        logger.warning(f"MOF jgbcm.csv 取得失敗: {e}")

    if rates:
        cache.set(_MOF_JGB_CACHE_KEY, {"_cache_version": _CACHE_VERSION, "rates": rates})
    return rates


def resolve_rf_for_date(rates: dict[str, float], fy_end: str) -> tuple[float, str]:
    """FY終了日に対応するRfと出所を返す。
    その日が休日等で存在しなければ最大14日遡って直前値を探す。
    見つからなければ WACC_RF_FALLBACK と "fallback" を返す。
    """
    if fy_end in rates:
        return rates[fy_end], "mof"
    try:
        target = date.fromisoformat(fy_end)
    except ValueError:
        return WACC_RF_FALLBACK, "fallback"
    for days_back in range(1, 15):
        candidate = (target - timedelta(days=days_back)).isoformat()
        if candidate in rates:
            return rates[candidate], "mof"
    return WACC_RF_FALLBACK, "fallback"


def get_rf_for_date(rates: dict[str, float], fy_end: str) -> float:
    """FY終了日（YYYY-MM-DD）に対応するRfを返す。"""
    rf, _ = resolve_rf_for_date(rates, fy_end)
    return rf


def calculate_wacc(
    eq: float | None,
    ibd: float | None,
    ie: float | None,
    tc_pct: float | None,
    rf: float,
) -> dict[str, float | str | None]:
    """WACC・CostOfEquity・CostOfDebt を計算して dict で返す。

    Args:
        eq: 純資産（百万円）
        ibd: 有利子負債（百万円）
        ie: 支払利息（百万円）
        tc_pct: 実効税率（%単位、例: 25.4）
        rf: リスクフリーレート（小数、例: 0.024）

    Returns:
        {"CostOfEquity": float | None, "CostOfDebt": float | None, "WACC": float | None, "WACCLabel": str | None}
        各値は % 単位。
    """
    re_ = rf + WACC_DEFAULT_BETA * WACC_MARKET_RISK_PREMIUM
    result: dict[str, float | str | None] = {
        "CostOfEquity": re_ * PERCENT,
        "CostOfDebt": None,
        "WACC": None,
        "WACCLabel": None,
    }
    if eq is None:
        return result
    d = ibd if ibd is not None else 0.0
    v = eq + d
    if v == 0:
        return result
    if d == 0:
        result["WACC"] = re_ * PERCENT
    elif ie is not None:
        rd = ie / d
        if rd <= 1.0:
            result["CostOfDebt"] = rd * PERCENT
        if result["CostOfDebt"] is None:
            result["WACCLabel"] = WACC_LABEL_COST_OF_DEBT_OUT_OF_RANGE
            return result
        if tc_pct is None:
            result["WACCLabel"] = WACC_LABEL_MISSING_INPUT
            return result
        if not (0 <= tc_pct <= 100):
            result["WACCLabel"] = WACC_LABEL_TAX_RATE_OUT_OF_RANGE
            return result
        tc = tc_pct / PERCENT
        result["WACC"] = ((eq / v) * re_ + (d / v) * rd * (1 - tc)) * PERCENT
    else:
        result["WACCLabel"] = WACC_LABEL_MISSING_INPUT
    return result
