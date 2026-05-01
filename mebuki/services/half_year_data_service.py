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

from .edinet_fetcher import EdinetFetcher

logger = logging.getLogger(__name__)

_CACHE_VERSION = ".".join(__version__.split(".")[:2])


def _fy_end_key(value: object) -> str:
    return value.replace("-", "") if isinstance(value, str) else ""


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
    ) -> list[dict[str, Any]]:
        """H1/H2 の半期財務データを返す。"""
        cache_key = f"half_year_periods_{code}_{years}"
        if use_cache:
            cached = self.cache_manager.get(cache_key)
            if cached and cached.get("_cache_version") == _CACHE_VERSION:
                return cached["periods"]

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
            return base_periods

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

                # CFO/CFI（H1 = 2Q XBRL の current 値）
                h1_cfo_m = h1_cfi_m = None
                if cf_result:
                    cfo_raw = cf_result["cfo"].get("current")
                    cfi_raw = cf_result["cfi"].get("current")
                    if cfo_raw is not None:
                        h1_cfo_m = cfo_raw / MILLION_YEN
                        data["CFO"] = h1_cfo_m
                    if cfi_raw is not None:
                        h1_cfi_m = cfi_raw / MILLION_YEN
                        data["CFI"] = h1_cfi_m
                    if h1_cfo_m is not None and h1_cfi_m is not None:
                        data["FreeCF"] = h1_cfo_m + h1_cfi_m

                # ROIC (H1): NP_H1 / (Eq_2Q + IBD_2Q)
                ibd_result = edinet_q2.get("ibd")
                h1_ibd_m = ibd_result["current"] / MILLION_YEN if ibd_result and ibd_result.get("current") is not None else None
                q2_rec = q2_by_end.get(fy_end_8, {})
                h1_eq_raw = to_float(q2_rec.get("Eq"))
                h1_eq_m = h1_eq_raw / MILLION_YEN if h1_eq_raw is not None else None
                np_h1 = data.get("NP")
                if np_h1 is not None and h1_eq_m is not None and h1_ibd_m is not None and (h1_eq_m + h1_ibd_m) != 0:
                    data["ROIC"] = np_h1 / (h1_eq_m + h1_ibd_m) * 100

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
                if fy_cfi_m is not None and h1_cfi_m is not None:
                    data["CFI"] = fy_cfi_m - h1_cfi_m
                cfo = data.get("CFO")
                cfi = data.get("CFI")
                if cfo is not None and cfi is not None:
                    data["FreeCF"] = cfo + cfi

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

                # ROIC (H2): NP_H2 / (Eq_FY + IBD_FY)
                h2_ibd = ibd_by_year.get(fy_end_8)
                h2_ibd_m = h2_ibd["current"] / MILLION_YEN if h2_ibd and h2_ibd.get("current") is not None else None
                h2_eq_raw = to_float(fy_rec.get("Eq"))
                h2_eq_m = h2_eq_raw / MILLION_YEN if h2_eq_raw is not None else None
                np_h2 = data.get("NP")
                if np_h2 is not None and h2_eq_m is not None and h2_ibd_m is not None and (h2_eq_m + h2_ibd_m) != 0:
                    data["ROIC"] = np_h2 / (h2_eq_m + h2_ibd_m) * 100

            else:
                # FY のみ（2Q データなし）: EDINET FY GP を付与
                fy_gp_result = fy_gp.get(fy_end_8)
                if fy_gp_result and fy_gp_result.get("current") is not None:
                    gp_m = fy_gp_result["current"] / MILLION_YEN
                    sales = data.get("Sales")
                    data["GrossProfit"] = gp_m
                    data["GrossProfitMargin"] = gp_m / sales * 100 if sales else None

                # ROIC (FY): NP_FY / (Eq_FY + IBD_FY)
                fy_rec_data = fy_by_end.get(fy_end_8, {})
                fy_ibd = ibd_by_year.get(fy_end_8)
                fy_ibd_m = fy_ibd["current"] / MILLION_YEN if fy_ibd and fy_ibd.get("current") is not None else None
                fy_eq_raw = to_float(fy_rec_data.get("Eq"))
                fy_eq_m = fy_eq_raw / MILLION_YEN if fy_eq_raw is not None else None
                np_fy = data.get("NP")
                if np_fy is not None and fy_eq_m is not None and fy_ibd_m is not None and (fy_eq_m + fy_ibd_m) != 0:
                    data["ROIC"] = np_fy / (fy_eq_m + fy_ibd_m) * 100

        self.cache_manager.set(cache_key, {
            "_cache_version": _CACHE_VERSION,
            "periods": base_periods,
        })
        return base_periods
