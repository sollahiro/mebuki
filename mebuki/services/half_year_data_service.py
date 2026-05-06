"""
半期財務データ構築サービス
"""

import asyncio
import logging
from collections.abc import Mapping
from typing import Any

from mebuki import __version__
from mebuki.api.edinet_client import EdinetAPIClient
from mebuki.constants.financial import MILLION_YEN
from mebuki.utils.cache import CacheManager
from mebuki.utils.converters import to_float
from mebuki.utils.financial_data import build_half_year_periods
from mebuki.utils.operating_profit_change import (
    apply_operating_profit_change_to_periods,
    apply_operating_profit_change_to_periods_from_xbrl,
)
from mebuki.utils.output_serializer import serialize_half_year_periods
from mebuki.utils.xbrl_result_types import GrossProfitResult, HalfYearEdinetEntry

from .edinet_fetcher import EdinetFetcher

logger = logging.getLogger(__name__)

_CACHE_VERSION = ".".join(__version__.split(".")[:2])


def _fy_end_key(value: object) -> str:
    return value.replace("-", "") if isinstance(value, str) else ""


def _set_metric_source(
    data: dict[str, Any],
    metric: str,
    *,
    source: str,
    unit: str,
    method: str | None = None,
    doc_id: str | None = None,
    label: str | None = None,
) -> None:
    sources = data.setdefault("MetricSources", {})
    item: dict[str, str | None] = {"source": source, "unit": unit}
    if method is not None:
        item["method"] = method
    if doc_id is not None:
        item["docID"] = doc_id
    if label is not None:
        item["label"] = label
    sources[metric] = item


def _to_gross_profit_result(value: dict[str, Any] | None) -> GrossProfitResult | None:
    if value is None:
        return None

    required_keys = ("current", "prior", "method", "accounting_standard", "components")
    if not all(key in value for key in required_keys):
        return None

    result: GrossProfitResult = {
        "current": value.get("current"),
        "prior": value.get("prior"),
        "method": str(value["method"]),
        "accounting_standard": str(value["accounting_standard"]),
        "components": value["components"] if isinstance(value["components"], list) else [],
    }
    if isinstance(value.get("docID"), str):
        result["docID"] = value["docID"]
    if isinstance(value.get("reason"), str):
        result["reason"] = value["reason"]
    for key in ("current_sales", "prior_sales"):
        raw_value = value.get(key)
        if raw_value is None or isinstance(raw_value, (int, float)):
            result[key] = raw_value
    return result


def _apply_h1_edinet_data(
    data: dict[str, Any],
    edinet_q2: HalfYearEdinetEntry,
    q2_rec: dict[str, Any],
) -> tuple[float | None, float | None, float | None]:
    """H1期間のEDINET補完を適用。(gp_m, cfo_m, cfi_m) を返す（H2キャリーオーバー用）。"""
    gp_result = edinet_q2["gp"]
    cf_result = edinet_q2["cf"]
    ibd_result = edinet_q2["ibd"]

    h1_gp_m = None
    gp_current = gp_result.get("current")
    if gp_current is not None:
        h1_gp_m = gp_current / MILLION_YEN
        sales = data.get("Sales")
        data["GrossProfit"] = h1_gp_m
        data["GrossProfitMargin"] = h1_gp_m / sales * 100 if sales else None
        data["DocID"] = gp_result.get("docID")
        _set_metric_source(data, "GrossProfit", source="edinet", unit="million_yen", method=gp_result.get("method"), doc_id=gp_result.get("docID"))
        _set_metric_source(data, "GrossProfitMargin", source="derived", unit="percent", method="GrossProfit / Sales")
        _set_metric_source(data, "DocID", source="edinet", unit="id", doc_id=gp_result.get("docID"))

    h1_cfo_m = h1_cfi_m = None
    cfo_raw = cf_result["cfo"].get("current")
    cfi_raw = cf_result["cfi"].get("current")
    if cfo_raw is not None:
        h1_cfo_m = cfo_raw / MILLION_YEN
        data["CFO"] = h1_cfo_m
        _set_metric_source(data, "CFO", source="edinet", unit="million_yen")
    if cfi_raw is not None:
        h1_cfi_m = cfi_raw / MILLION_YEN
        data["CFI"] = h1_cfi_m
        _set_metric_source(data, "CFI", source="edinet", unit="million_yen")
    if h1_cfo_m is not None and h1_cfi_m is not None:
        data["CFC"] = h1_cfo_m + h1_cfi_m
        data["FreeCF"] = data["CFC"]
        _set_metric_source(data, "CFC", source="derived", unit="million_yen", method="CFO + CFI")
        _set_metric_source(data, "FreeCF", source="derived", unit="million_yen", method="alias of CFC")

    ibd_current = ibd_result.get("current")
    h1_ibd_m = ibd_current / MILLION_YEN if ibd_current is not None else None
    q2_eq_raw = to_float(q2_rec.get("Eq"))
    q2_eq_m = q2_eq_raw / MILLION_YEN if q2_eq_raw is not None else None
    np_h1 = data.get("NP")
    if np_h1 is not None and q2_eq_m is not None and h1_ibd_m is not None and (q2_eq_m + h1_ibd_m) != 0:
        data["ROIC"] = np_h1 / (q2_eq_m + h1_ibd_m) * 100
        _set_metric_source(data, "ROIC", source="derived", unit="percent", method="NP / (Eq + InterestBearingDebt)")

    return h1_gp_m, h1_cfo_m, h1_cfi_m


def _apply_h2_edinet_data(
    data: dict[str, Any],
    fy_rec: dict[str, Any],
    h1_carry: tuple[float | None, float | None, float | None],
    fy_gp_result: GrossProfitResult | None,
    ibd_by_year: dict[str, Any],
    fy_end_8: str,
) -> None:
    """H2期間の派生計算（FY - H1）と補完を適用。"""
    h1_gp_m, h1_cfo_m, h1_cfi_m = h1_carry

    fy_cfo = to_float(fy_rec.get("CFO"))
    fy_cfi = to_float(fy_rec.get("CFI"))
    fy_cfo_m = fy_cfo / MILLION_YEN if fy_cfo is not None else None
    fy_cfi_m = fy_cfi / MILLION_YEN if fy_cfi is not None else None
    fy_source = "EDINET" if fy_rec.get("_xbrl_source") else "EXTERNAL"

    if fy_cfo_m is not None and h1_cfo_m is not None:
        data["CFO"] = fy_cfo_m - h1_cfo_m
        _set_metric_source(data, "CFO", source="derived", unit="million_yen", method=f"FY {fy_source} CFO - H1 EDINET CFO")
    if fy_cfi_m is not None and h1_cfi_m is not None:
        data["CFI"] = fy_cfi_m - h1_cfi_m
        _set_metric_source(data, "CFI", source="derived", unit="million_yen", method=f"FY {fy_source} CFI - H1 EDINET CFI")
    cfo = data.get("CFO")
    cfi = data.get("CFI")
    if cfo is not None and cfi is not None:
        data["CFC"] = cfo + cfi
        data["FreeCF"] = data["CFC"]
        _set_metric_source(data, "CFC", source="derived", unit="million_yen", method="CFO + CFI")
        _set_metric_source(data, "FreeCF", source="derived", unit="million_yen", method="alias of CFC")

    fy_gp_current = fy_gp_result.get("current") if fy_gp_result is not None else None
    if fy_gp_result is not None and fy_gp_current is not None:
        fy_gp_m = fy_gp_current / MILLION_YEN
        if h1_gp_m is not None:
            h2_gp_m = fy_gp_m - h1_gp_m
            sales = data.get("Sales")
            data["GrossProfit"] = h2_gp_m
            data["GrossProfitMargin"] = h2_gp_m / sales * 100 if sales else None
            data["DocID"] = fy_gp_result.get("docID")
            _set_metric_source(data, "GrossProfit", source="derived", unit="million_yen", method="FY EDINET GrossProfit - H1 EDINET GrossProfit", doc_id=fy_gp_result.get("docID"))
            _set_metric_source(data, "GrossProfitMargin", source="derived", unit="percent", method="GrossProfit / Sales")
            _set_metric_source(data, "DocID", source="edinet", unit="id", doc_id=fy_gp_result.get("docID"))

    h2_ibd = ibd_by_year.get(fy_end_8)
    h2_ibd_m = h2_ibd["current"] / MILLION_YEN if h2_ibd and h2_ibd.get("current") is not None else None
    h2_eq_raw = to_float(fy_rec.get("Eq"))
    h2_eq_m = h2_eq_raw / MILLION_YEN if h2_eq_raw is not None else None
    np_h2 = data.get("NP")
    if np_h2 is not None and h2_eq_m is not None and h2_ibd_m is not None and (h2_eq_m + h2_ibd_m) != 0:
        data["ROIC"] = np_h2 / (h2_eq_m + h2_ibd_m) * 100
        _set_metric_source(data, "ROIC", source="derived", unit="percent", method="NP / (Eq + InterestBearingDebt)")


def _apply_fy_only_edinet_data(
    data: dict[str, Any],
    fy_gp_result: GrossProfitResult | None,
    fy_rec: dict[str, Any],
    ibd_by_year: dict[str, Any],
    fy_end_8: str,
) -> None:
    """FY-onlyエントリ（2Qデータなし）にFY EDINET GP + ROIC を補完。"""
    fy_gp_current = fy_gp_result.get("current") if fy_gp_result is not None else None
    if fy_gp_result is not None and fy_gp_current is not None:
        gp_m = fy_gp_current / MILLION_YEN
        sales = data.get("Sales")
        data["GrossProfit"] = gp_m
        data["GrossProfitMargin"] = gp_m / sales * 100 if sales else None
        _set_metric_source(data, "GrossProfit", source="edinet", unit="million_yen", method=fy_gp_result.get("method"), doc_id=fy_gp_result.get("docID"))
        _set_metric_source(data, "GrossProfitMargin", source="derived", unit="percent", method="GrossProfit / Sales")

    fy_ibd = ibd_by_year.get(fy_end_8)
    fy_ibd_m = fy_ibd["current"] / MILLION_YEN if fy_ibd and fy_ibd.get("current") is not None else None
    fy_eq_raw = to_float(fy_rec.get("Eq"))
    fy_eq_m = fy_eq_raw / MILLION_YEN if fy_eq_raw is not None else None
    np_fy = data.get("NP")
    if np_fy is not None and fy_eq_m is not None and fy_ibd_m is not None and (fy_eq_m + fy_ibd_m) != 0:
        data["ROIC"] = np_fy / (fy_eq_m + fy_ibd_m) * 100
        _set_metric_source(data, "ROIC", source="derived", unit="percent", method="NP / (Eq + InterestBearingDebt)")


class HalfYearDataService:
    """H1/H2 の半期財務データ構築と EDINET 補完を担当するサービス"""

    def __init__(self, edinet_client: EdinetAPIClient, cache_manager: CacheManager) -> None:
        self.edinet_client = edinet_client
        self.cache_manager = cache_manager

    async def get_half_year_periods(
        self,
        code: str,
        years: int = 3,
        use_cache: bool = True,
        include_debug_fields: bool = False,
    ) -> list[dict[str, Any]]:
        """H1/H2 の半期財務データを返す。"""
        cache_key = f"half_year_periods_{code}_{years}"
        if use_cache:
            cached = self.cache_manager.get(cache_key)
            if cached and cached.get("_cache_version") == _CACHE_VERSION:
                return serialize_half_year_periods(cached["periods"], include_debug_fields=include_debug_fields)

        edinet_fetcher = EdinetFetcher(
            self.edinet_client,
            cache_manager=self.cache_manager,
        )
        try:
            fy_records, q2_records = await asyncio.gather(
                edinet_fetcher.build_xbrl_annual_records(code, years),
                edinet_fetcher.build_xbrl_half_year_records(code, years + 1),
            )
            financial_data = fy_records + q2_records
        except Exception as e:
            logger.warning(f"[HALF] {code}: EDINET-only財務データ構築スキップ - {e}")
            return []

        base_periods = build_half_year_periods(financial_data, years=years)
        if not base_periods:
            return base_periods

        # EDINET からの補完（GrossProfit + CFO/CFI for H1）
        # 表示中の FY 数だけ 2Q EDINET を取得（26H1 等の extra 分も含む）
        unique_fy_ends = len(set(p["fy_end"] for p in base_periods))
        try:
            half_edinet, fy_gp, ibd_by_year, fy_op = await asyncio.gather(
                edinet_fetcher.extract_half_year_edinet_data(code, financial_data, max_years=unique_fy_ends),
                edinet_fetcher.extract_gross_profit_by_year(code, financial_data, max_years=years),
                edinet_fetcher.extract_ibd_by_year(code, financial_data, max_years=years),
                edinet_fetcher.extract_operating_profit_by_year(code, financial_data, max_years=years),
            )
        except Exception as e:
            logger.warning(f"[HALF] {code}: EDINET補完スキップ - {e}")
            return serialize_half_year_periods(base_periods, include_debug_fields=include_debug_fields)

        fy_gp_by_end: dict[str, GrossProfitResult] = {}
        for fy_end, result in fy_gp.items():
            if not isinstance(result, dict):
                continue
            gp_result = _to_gross_profit_result(result)
            if gp_result is not None:
                fy_gp_by_end[fy_end] = gp_result

        half_gp_by_end: dict[str, Mapping[str, Any]] = {}
        half_op_by_end: dict[str, Mapping[str, Any]] = {}
        for fy_end, entry in half_edinet.items():
            if not isinstance(entry, dict):
                continue
            gp = entry.get("gp")
            op = entry.get("op")
            if isinstance(gp, dict):
                half_gp_by_end[fy_end] = gp
            if isinstance(op, dict):
                half_op_by_end[fy_end] = op

        fy_op_by_end: dict[str, Mapping[str, Any]] = {}
        for fy_end, result in fy_op.items():
            if isinstance(result, dict):
                fy_op_by_end[fy_end] = result

        # FY レコードを fy_end → record で引けるようにしておく
        fy_by_end: dict[str, dict[str, Any]] = {}
        for r in financial_data:
            if r.get("CurPerType") == "FY":
                fy_end_8 = _fy_end_key(r.get("CurFYEn"))
                if fy_end_8:
                    fy_by_end[fy_end_8] = r

        # 2Q レコードを fy_end → record で引けるようにしておく
        q2_by_end: dict[str, dict[str, Any]] = {}
        for r in financial_data:
            if r.get("CurPerType") == "2Q":
                fy_end_8 = _fy_end_key(r.get("CurFYEn"))
                if fy_end_8:
                    q2_by_end[fy_end_8] = r

        # H1 期間で確定した EDINET CF 値を H2 計算に引き継ぐ
        h1_edinet_by_fy: dict[str, tuple[float | None, float | None, float | None]] = {}

        for period in base_periods:
            fy_end_8 = _fy_end_key(period.get("fy_end"))
            half = period["half"]
            data = period["data"]
            edinet_q2 = half_edinet.get(fy_end_8)

            if half == "H1":
                if edinet_q2 is not None:
                    h1_edinet_by_fy[fy_end_8] = _apply_h1_edinet_data(data, edinet_q2, q2_by_end.get(fy_end_8, {}))
            elif half == "H2":
                _apply_h2_edinet_data(
                    data,
                    fy_by_end.get(fy_end_8, {}),
                    h1_edinet_by_fy.get(fy_end_8, (None, None, None)),
                    fy_gp_by_end.get(fy_end_8),
                    ibd_by_year,
                    fy_end_8,
                )
            else:
                _apply_fy_only_edinet_data(data, fy_gp_by_end.get(fy_end_8), fy_by_end.get(fy_end_8, {}), ibd_by_year, fy_end_8)

        apply_operating_profit_change_to_periods_from_xbrl(
            base_periods,
            half_gp_by_end,
            half_op_by_end,
            fy_gp_by_end,
            fy_op_by_end,
        )
        apply_operating_profit_change_to_periods(base_periods)
        self.cache_manager.set(cache_key, {
            "_cache_version": _CACHE_VERSION,
            "periods": base_periods,
        })
        return serialize_half_year_periods(base_periods, include_debug_fields=include_debug_fields)
