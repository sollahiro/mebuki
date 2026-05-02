"""
半期財務データ構築サービス
"""

import asyncio
import logging
from typing import Any

from mebuki import __version__
from mebuki.constants.financial import MILLION_YEN
from mebuki.utils.cache import CacheManager
from mebuki.utils.converters import to_float
from mebuki.utils.financial_data import build_half_year_periods
from mebuki.utils.output_serializer import serialize_half_year_periods

from .edinet_fetcher import EdinetFetcher

logger = logging.getLogger(__name__)

_CACHE_VERSION = f"{'.'.join(__version__.split('.')[:2])}:metrics-v2"


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


class HalfYearDataService:
    """H1/H2 の半期財務データ構築と EDINET 補完を担当するサービス"""

    def __init__(self, api_client, edinet_client, cache_manager: CacheManager):
        self.api_client = api_client
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

        financial_data = await self.api_client.get_financial_summary(
            code=code,
            period_types=["FY", "2Q"],
            include_fields=None,
        )
        if not financial_data:
            return []

        base_periods = build_half_year_periods(financial_data, years=years)
        if not base_periods:
            return base_periods

        # EDINET からの補完（GrossProfit + CFO/CFI for H1）
        # 表示中の FY 数だけ 2Q EDINET を取得（26H1 等の extra 分も含む）
        unique_fy_ends = len(set(p["fy_end"] for p in base_periods))
        edinet_fetcher = EdinetFetcher(self.api_client, self.edinet_client)
        try:
            half_edinet, fy_gp, ibd_by_year = await asyncio.gather(
                edinet_fetcher.extract_half_year_edinet_data(code, financial_data, max_years=unique_fy_ends),
                edinet_fetcher.extract_gross_profit_by_year(code, financial_data, max_years=years),
                edinet_fetcher.extract_ibd_by_year(code, financial_data, max_years=years),
            )
        except Exception as e:
            logger.warning(f"[HALF] {code}: EDINET補完スキップ - {e}")
            return serialize_half_year_periods(base_periods, include_debug_fields=include_debug_fields)

        # FY J-Quants レコードを fy_end → record で引けるようにしておく
        fy_by_end: dict[str, dict] = {}
        for r in financial_data:
            if r.get("CurPerType") == "FY":
                fy_end_8 = _fy_end_key(r.get("CurFYEn"))
                if fy_end_8:
                    fy_by_end[fy_end_8] = r

        # 2Q J-Quants レコードを fy_end → record で引けるようにしておく
        q2_by_end: dict[str, dict] = {}
        for r in financial_data:
            if r.get("CurPerType") == "2Q":
                fy_end_8 = _fy_end_key(r.get("CurFYEn"))
                if fy_end_8:
                    q2_by_end[fy_end_8] = r

        # H1 期間で確定した EDINET CF 値を H2 計算に引き継ぐ
        h1_edinet_by_fy: dict[str, dict] = {}

        for period in base_periods:
            fy_end_8 = _fy_end_key(period.get("fy_end"))
            half = period["half"]
            data = period["data"]

            if half == "H1":
                edinet_q2 = half_edinet.get(fy_end_8, {})
                gp_result = edinet_q2.get("gp")
                cf_result = edinet_q2.get("cf")

                # GrossProfit（H1 = 2Q XBRL の current 値）
                h1_gp_m = None
                if gp_result and gp_result.get("current") is not None:
                    h1_gp_m = gp_result["current"] / MILLION_YEN
                    sales = data.get("Sales")
                    data["GrossProfit"] = h1_gp_m
                    data["GrossProfitMargin"] = h1_gp_m / sales * 100 if sales else None
                    data["DocID"] = gp_result.get("docID")
                    _set_metric_source(data, "GrossProfit", source="edinet", unit="million_yen", method=gp_result.get("method"), doc_id=gp_result.get("docID"))
                    _set_metric_source(data, "GrossProfitMargin", source="derived", unit="percent", method="GrossProfit / Sales")
                    _set_metric_source(data, "DocID", source="edinet", unit="id", doc_id=gp_result.get("docID"))

                # CFO/CFI（H1 = 2Q XBRL の current 値）
                h1_cfo_m = h1_cfi_m = None
                if cf_result:
                    cfo_raw = cf_result["cfo"].get("current")
                    cfi_raw = cf_result["cfi"].get("current")
                    if cfo_raw is not None:
                        h1_cfo_m = cfo_raw / MILLION_YEN
                        data["CFO"] = h1_cfo_m
                        _set_metric_source(data, "CFO", source="edinet", unit="million_yen", method=cf_result["cfo"].get("method"), doc_id=cf_result["cfo"].get("docID"))
                    if cfi_raw is not None:
                        h1_cfi_m = cfi_raw / MILLION_YEN
                        data["CFI"] = h1_cfi_m
                        _set_metric_source(data, "CFI", source="edinet", unit="million_yen", method=cf_result["cfi"].get("method"), doc_id=cf_result["cfi"].get("docID"))
                    if h1_cfo_m is not None and h1_cfi_m is not None:
                        data["CFC"] = h1_cfo_m + h1_cfi_m
                        data["FreeCF"] = data["CFC"]
                        _set_metric_source(data, "CFC", source="derived", unit="million_yen", method="CFO + CFI")
                        _set_metric_source(data, "FreeCF", source="derived", unit="million_yen", method="alias of CFC")

                # ROIC (H1): NP_H1 / (Eq_2Q + IBD_2Q)
                ibd_result = edinet_q2.get("ibd")
                h1_ibd_m = ibd_result["current"] / MILLION_YEN if ibd_result and ibd_result.get("current") is not None else None
                q2_rec = q2_by_end.get(fy_end_8, {})
                h1_eq_raw = to_float(q2_rec.get("Eq"))
                h1_eq_m = h1_eq_raw / MILLION_YEN if h1_eq_raw is not None else None
                np_h1 = data.get("NP")
                if np_h1 is not None and h1_eq_m is not None and h1_ibd_m is not None and (h1_eq_m + h1_ibd_m) != 0:
                    data["ROIC"] = np_h1 / (h1_eq_m + h1_ibd_m) * 100
                    _set_metric_source(data, "ROIC", source="derived", unit="percent", method="NP / (Eq + InterestBearingDebt)")

                h1_edinet_by_fy[fy_end_8] = {
                    "gp_m": h1_gp_m,
                    "cfo_m": h1_cfo_m,
                    "cfi_m": h1_cfi_m,
                }

            elif half == "H2":
                h1 = h1_edinet_by_fy.get(fy_end_8, {})
                fy_rec = fy_by_end.get(fy_end_8, {})

                # H2 CFO/CFI = FY（J-Quants）- H1（EDINET 2Q）
                fy_cfo = to_float(fy_rec.get("CFO"))
                fy_cfi = to_float(fy_rec.get("CFI"))
                fy_cfo_m = fy_cfo / MILLION_YEN if fy_cfo is not None else None
                fy_cfi_m = fy_cfi / MILLION_YEN if fy_cfi is not None else None

                h1_cfo_m = h1.get("cfo_m")
                h1_cfi_m = h1.get("cfi_m")

                if fy_cfo_m is not None and h1_cfo_m is not None:
                    data["CFO"] = fy_cfo_m - h1_cfo_m
                    _set_metric_source(data, "CFO", source="derived", unit="million_yen", method="FY J-QUANTS CFO - H1 EDINET CFO")
                if fy_cfi_m is not None and h1_cfi_m is not None:
                    data["CFI"] = fy_cfi_m - h1_cfi_m
                    _set_metric_source(data, "CFI", source="derived", unit="million_yen", method="FY J-QUANTS CFI - H1 EDINET CFI")
                cfo = data.get("CFO")
                cfi = data.get("CFI")
                if cfo is not None and cfi is not None:
                    data["CFC"] = cfo + cfi
                    data["FreeCF"] = data["CFC"]
                    _set_metric_source(data, "CFC", source="derived", unit="million_yen", method="CFO + CFI")
                    _set_metric_source(data, "FreeCF", source="derived", unit="million_yen", method="alias of CFC")

                # H2 GP = FY EDINET GP - H1 EDINET 2Q GP
                fy_gp_result = fy_gp.get(fy_end_8)
                h1_gp_m = h1.get("gp_m")
                if fy_gp_result and fy_gp_result.get("current") is not None:
                    fy_gp_m = fy_gp_result["current"] / MILLION_YEN
                    if h1_gp_m is not None:
                        h2_gp_m = fy_gp_m - h1_gp_m
                        sales = data.get("Sales")
                        data["GrossProfit"] = h2_gp_m
                        data["GrossProfitMargin"] = h2_gp_m / sales * 100 if sales else None
                        data["DocID"] = fy_gp_result.get("docID")
                        _set_metric_source(data, "GrossProfit", source="derived", unit="million_yen", method="FY EDINET GrossProfit - H1 EDINET GrossProfit", doc_id=fy_gp_result.get("docID"))
                        _set_metric_source(data, "GrossProfitMargin", source="derived", unit="percent", method="GrossProfit / Sales")
                        _set_metric_source(data, "DocID", source="edinet", unit="id", doc_id=fy_gp_result.get("docID"))

                # ROIC (H2): NP_H2 / (Eq_FY + IBD_FY)
                h2_ibd = ibd_by_year.get(fy_end_8)
                h2_ibd_m = h2_ibd["current"] / MILLION_YEN if h2_ibd and h2_ibd.get("current") is not None else None
                h2_eq_raw = to_float(fy_rec.get("Eq"))
                h2_eq_m = h2_eq_raw / MILLION_YEN if h2_eq_raw is not None else None
                np_h2 = data.get("NP")
                if np_h2 is not None and h2_eq_m is not None and h2_ibd_m is not None and (h2_eq_m + h2_ibd_m) != 0:
                    data["ROIC"] = np_h2 / (h2_eq_m + h2_ibd_m) * 100
                    _set_metric_source(data, "ROIC", source="derived", unit="percent", method="NP / (Eq + InterestBearingDebt)")

            else:
                # FY のみ（2Q データなし）: EDINET FY GP を付与
                fy_gp_result = fy_gp.get(fy_end_8)
                if fy_gp_result and fy_gp_result.get("current") is not None:
                    gp_m = fy_gp_result["current"] / MILLION_YEN
                    sales = data.get("Sales")
                    data["GrossProfit"] = gp_m
                    data["GrossProfitMargin"] = gp_m / sales * 100 if sales else None
                    _set_metric_source(data, "GrossProfit", source="edinet", unit="million_yen", method=fy_gp_result.get("method"), doc_id=fy_gp_result.get("docID"))
                    _set_metric_source(data, "GrossProfitMargin", source="derived", unit="percent", method="GrossProfit / Sales")

                # ROIC (FY): NP_FY / (Eq_FY + IBD_FY)
                fy_rec_data = fy_by_end.get(fy_end_8, {})
                fy_ibd = ibd_by_year.get(fy_end_8)
                fy_ibd_m = fy_ibd["current"] / MILLION_YEN if fy_ibd and fy_ibd.get("current") is not None else None
                fy_eq_raw = to_float(fy_rec_data.get("Eq"))
                fy_eq_m = fy_eq_raw / MILLION_YEN if fy_eq_raw is not None else None
                np_fy = data.get("NP")
                if np_fy is not None and fy_eq_m is not None and fy_ibd_m is not None and (fy_eq_m + fy_ibd_m) != 0:
                    data["ROIC"] = np_fy / (fy_eq_m + fy_ibd_m) * 100
                    _set_metric_source(data, "ROIC", source="derived", unit="percent", method="NP / (Eq + InterestBearingDebt)")

        self.cache_manager.set(cache_key, {
            "_cache_version": _CACHE_VERSION,
            "periods": base_periods,
        })
        return serialize_half_year_periods(base_periods, include_debug_fields=include_debug_fields)
