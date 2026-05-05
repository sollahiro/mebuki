"""
EDINET書類発見ユーティリティ（J-Quants不要）

J-Quantsの DiscDate を使わずに EDINET 書類を発見するための関数群。
scan_for_fiscal_year_end() でEDINETをスキャンして会計期末パターンを発見し、
build_fiscal_year_periods() で edinet_client.search_documents() に渡す
期間レコードを生成する。
"""

import asyncio
import calendar
import logging
from datetime import date, datetime, timedelta
from typing import TYPE_CHECKING, Any

from .fiscal_year import parse_date_string

if TYPE_CHECKING:
    from ..api.edinet_client import EdinetAPIClient

logger = logging.getLogger(__name__)

_ANNUAL_REPORT_DOC_TYPE = "120"
_SCAN_BATCH_SIZE = 10


async def scan_for_fiscal_year_end(
    code: str,
    edinet_client: "EdinetAPIClient",
    scan_days: int = 480,
) -> tuple[int, int] | None:
    """
    EDINET をスキャンして直近の有価証券報告書を発見し、会計期末の (month, day) を返す。

    J-Quants なしで会計期末パターンを特定するためのブートストラップ処理。
    EDINET の /documents.json?date=X を直近 scan_days 日分さかのぼって検索する。
    日付ごとのレスポンスは EdinetAPIClient の内部キャッシュで保護されるため、
    2回目以降は高速。

    Args:
        code: 銘柄コード（4桁または5桁）
        edinet_client: EdinetAPIClient インスタンス
        scan_days: さかのぼる日数（デフォルト480日≒16ヶ月）

    Returns:
        (month, day) または None（見つからない場合）
    """
    code_4digit = code[:4] if len(code) >= 4 else code
    now = datetime.now()

    for batch_start in range(0, scan_days, _SCAN_BATCH_SIZE):
        batch_dates = [
            (now - timedelta(days=batch_start + j)).strftime("%Y-%m-%d")
            for j in range(_SCAN_BATCH_SIZE)
        ]

        results = await asyncio.gather(
            *[edinet_client._get_documents_for_date(d) for d in batch_dates],
            return_exceptions=True,
        )

        for result in results:
            if isinstance(result, BaseException):
                continue
            for doc in result:
                sec = str(doc.get("secCode", "")).strip()
                if not sec.startswith(code_4digit):
                    continue
                if doc.get("docTypeCode") != _ANNUAL_REPORT_DOC_TYPE:
                    continue
                desc = doc.get("docDescription", "")
                if "訂正" in desc or "補正" in desc:
                    continue

                period_end_str = doc.get("periodEnd", "")
                if period_end_str:
                    dt = parse_date_string(period_end_str)
                    if dt:
                        logger.info(
                            f"[EDINET Discovery] {code}: 会計期末パターン発見 "
                            f"periodEnd={period_end_str} → ({dt.month}, {dt.day})"
                        )
                        return (dt.month, dt.day)

    logger.warning(f"[EDINET Discovery] {code}: {scan_days}日間スキャンで有価証券報告書が見つかりませんでした")
    return None


def _fiscal_year_end_date(fy_end_month: int, fy_end_day: int, year: int) -> date:
    """月末日を安全に処理しつつ会計期末日を構築する。"""
    last_day = calendar.monthrange(year, fy_end_month)[1]
    return date(year, fy_end_month, min(fy_end_day, last_day))


def build_fiscal_year_periods(
    fy_end_month: int,
    fy_end_day: int,
    analysis_years: int,
) -> list[dict[str, Any]]:
    """
    会計期末パターン (month, day) から過去 analysis_years 年分の期間レコードを生成する。

    J-Quants の prepare_edinet_search_data() の代替。
    生成したレコードは edinet_client.search_documents(jquants_data=periods) に渡せる。
    DiscDate は空文字（_search_record は period_end_date を search_start として使う）。

    Args:
        fy_end_month: 会計期末月（例: 3 = 3月決算）
        fy_end_day:   会計期末日（例: 31）
        analysis_years: 取得する年数

    Returns:
        期間レコードのリスト（新しい年度順）
    """
    today = date.today()
    periods: list[dict[str, Any]] = []

    # 余裕を持って analysis_years + 3 年分を走査し、必要数だけ返す
    for year in range(today.year, today.year - analysis_years - 3, -1):
        fy_end = _fiscal_year_end_date(fy_end_month, fy_end_day, year)

        if fy_end >= today:
            continue  # 未確定期はスキップ

        prev_fy_end = _fiscal_year_end_date(fy_end_month, fy_end_day, year - 1)
        fy_start = prev_fy_end + timedelta(days=1)

        # 慣習: 年度 = 開始年（J-Quants の calculate_fiscal_year_from_start と同じ）
        fiscal_year = fy_start.year

        periods.append({
            "CurFYEn": fy_end.strftime("%Y-%m-%d"),
            "CurPerEn": "",
            "CurFYSt": fy_start.strftime("%Y-%m-%d"),
            "DiscDate": "",  # 不明 → _search_record が period_end_date を search_start として使用
            "CurPerType": "FY",
            "fiscal_year": fiscal_year,
        })

        if len(periods) >= analysis_years + 1:
            break

    return periods
