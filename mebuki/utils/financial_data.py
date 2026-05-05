"""
財務データ処理と指標計算モジュール
"""

import logging
from typing import Any
from datetime import datetime

from .converters import to_float, is_valid_value, is_valid_financial_record, extract_year_month
from mebuki.utils.fiscal_year import parse_date_string
from mebuki.constants.financial import MILLION_YEN

logger = logging.getLogger(__name__)

_DedupKey = str | tuple[str, str]


def _is_mergeable_value(value: object) -> bool:
    return is_valid_value(value) or (isinstance(value, str) and value != "")


def _merge_record(
    seen: dict[_DedupKey, dict[str, Any]],
    field_dates: dict[_DedupKey, dict[str, str]],
    key: _DedupKey,
    record: dict[str, Any],
) -> None:
    """重複排除辞書にレコードをマージする。

    有効な値は、そのフィールドに対して最も新しい DiscDate の値を採用する。
    欠損・空・0 は有効値を上書きしない。DiscDate は常に最新値に更新する。
    """
    disc_date = str(record.get("DiscDate", ""))
    if key not in seen:
        seen[key] = record.copy()
        field_dates[key] = {
            field: disc_date
            for field, value in record.items()
            if _is_mergeable_value(value)
        }
        return

    existing = seen[key]
    dates = field_dates[key]

    if disc_date >= str(existing.get("DiscDate", "")):
        existing["DiscDate"] = record.get("DiscDate", existing.get("DiscDate"))

    for field, value in record.items():
        if field == "DiscDate" or not _is_mergeable_value(value):
            continue
        if field not in dates or disc_date >= dates[field]:
            existing[field] = value
            dates[field] = disc_date


def _period_sort_key(record: dict[str, Any]) -> tuple[str, int]:
    return (record.get("CurFYEn", ""), 0 if record.get("CurPerType") == "FY" else 1)


def _latest_by_fy_end(
    records: dict[str, dict[str, Any]],
    limit: int,
) -> list[str]:
    return sorted(records.keys(), reverse=True)[:limit]


def _latest_q2_only_ends(
    q2_by_end: dict[str, dict[str, Any]],
    newest_fy: str,
) -> list[str]:
    return [fy_end for fy_end in q2_by_end if fy_end > newest_fy]


def _upsert_latest_record(
    records_by_end: dict[str, dict[str, Any]],
    fy_end: str,
    record: dict[str, Any],
) -> None:
    existing = records_by_end.get(fy_end)
    if not existing or record.get("DiscDate", "") >= existing.get("DiscDate", ""):
        records_by_end[fy_end] = record


def extract_annual_data(
    quarterly_data: list[dict[str, Any]],
    include_2q: bool = False
) -> list[dict[str, Any]]:
    """
    四半期データから年度データを抽出（FYと2Qを取得可能）

    Args:
        quarterly_data: fin-summaryから取得した四半期データ
        include_2q: 2Qデータも含めるか（デフォルト: False、FYのみ）

    Returns:
        年度データ（CurPerType="FY"、またはinclude_2q=Trueの場合は"2Q"も含む）のリスト、
        年度終了日でソート（重複除去済み、未来の年度は除外）
    """
    today = datetime.now()

    def _should_include(record: dict[str, Any]) -> bool:
        fy_end = record.get("CurFYEn", "")
        disc_date = record.get("DiscDate", "")

        if disc_date:
            try:
                disc_dt = parse_date_string(disc_date)
                if disc_dt and disc_dt > today:
                    return False
            except (ValueError, TypeError):
                pass

        if fy_end:
            year, month = extract_year_month(fy_end)
            if year is None or month is None:
                return True
            try:
                fy_end_dt = parse_date_string(fy_end)
                if fy_end_dt and fy_end_dt > today:
                    return False
            except (ValueError, TypeError):
                if year > today.year or (year == today.year and month > today.month):
                    return False

        if not is_valid_financial_record(record):
            logger.warning(f"主要財務データが全てN/Aのため除外: fy_end={fy_end}")
            return False

        return True

    seen_years: dict[_DedupKey, dict[str, Any]] = {}
    field_dates: dict[_DedupKey, dict[str, str]] = {}
    for record in quarterly_data:
        period_type = record.get("CurPerType")
        if period_type != "FY" and not (include_2q and period_type == "2Q"):
            continue
        if not _should_include(record):
            continue

        fy_end = record.get("CurFYEn")
        if not fy_end:
            continue

        per_type = record.get("CurPerType", "FY")
        dedup_key = (fy_end, per_type) if include_2q else fy_end

        _merge_record(seen_years, field_dates, dedup_key, record)

    # マージ後のデータを新しい順（降順）に並べ替えて返す
    # 同一 CurFYEn では FY を 2Q より後（新しい側）に並べる
    unique_annual_data = list(seen_years.values())
    unique_annual_data.sort(key=_period_sort_key, reverse=True)

    return unique_annual_data



def build_half_year_periods(
    financial_data: list[dict[str, Any]],
    years: int = 3,
) -> list[dict[str, Any]]:
    """
    FY と 2Q レコードを対応付けて H1/H2 の半期データリストを返す。

    - H1 = 2Q レコードのフロー値（上半期累計）
    - H2 = FY レコード − 2Q レコード（下半期単独）
    - 2Q データのない年は FY のみ（half=None, label="NNfy"）

    Args:
        financial_data: FY/2Q の財務レコードリスト
        years: 対象 FY 件数（デフォルト 3）

    Returns:
        古い順に並んだ半期データリスト。各要素::

            {
                "label": "24H1",       # 列ヘッダー用
                "half": "H1",          # "H1" / "H2" / None (FY のみ)
                "fy_end": "20240331",
                "data": {
                    "Sales": float | None,          # 百万円
                    "OP": float | None,
                    "OperatingMargin": float | None, # %
                    "NP": float | None,
                    "CFO": float | None,
                    "CFI": float | None,
                    "CFC": float | None,
                    "FreeCF": float | None,          # 互換名
                }
            }
    """
    today = datetime.now()

    fy_by_end: dict[str, dict[str, Any]] = {}
    q2_by_end: dict[str, dict[str, Any]] = {}

    for record in financial_data:
        per_type = record.get("CurPerType")
        fy_end = record.get("CurFYEn", "")
        if not fy_end:
            continue

        disc_date = record.get("DiscDate", "")
        if disc_date:
            try:
                disc_dt = parse_date_string(disc_date)
                if disc_dt and disc_dt > today:
                    continue
            except (ValueError, TypeError):
                pass

        try:
            fy_end_dt = parse_date_string(fy_end)
            if fy_end_dt and fy_end_dt > today:
                continue
        except (ValueError, TypeError):
            pass

        if per_type == "FY":
            _upsert_latest_record(fy_by_end, fy_end, record)
        elif per_type == "2Q":
            _upsert_latest_record(q2_by_end, fy_end, record)

    # FY レコードが存在する期間を最新 years 件取得
    fy_ends_with_fy = _latest_by_fy_end(fy_by_end, years)

    # FY 未開示だが 2Q が存在する最新期間を追加（例: 当期 FY 開示前の H1）
    newest_fy = fy_ends_with_fy[0] if fy_ends_with_fy else ""
    extra_q2_only = _latest_q2_only_ends(q2_by_end, newest_fy)

    fy_ends_selected = sorted(set(fy_ends_with_fy) | set(extra_q2_only), reverse=True)

    def _m(value: str | float | int | None) -> float | None:
        v = to_float(value)
        return v / MILLION_YEN if v is not None else None

    def _diff_m(fy_rec: dict[str, Any], q2_rec: dict[str, Any], field: str) -> float | None:
        fy_v = to_float(fy_rec.get(field))
        q2_v = to_float(q2_rec.get(field))
        if fy_v is None or q2_v is None:
            return None
        return (fy_v - q2_v) / MILLION_YEN

    def _record_source(record: dict[str, Any] | None) -> str:
        return "edinet" if record and record.get("_xbrl_source") else "external"

    def _make_data(
        sales: float | None,
        op: float | None,
        np_: float | None,
        cfo: float | None,
        cfi: float | None,
        *,
        source: str,
        flow_method: str | None = None,
    ) -> dict[str, Any]:
        cfc = (cfo + cfi) if cfo is not None and cfi is not None else None
        metric_source = {"source": source, "unit": "million_yen"}
        flow_source = {"source": source, "unit": "million_yen"}
        if flow_method is not None:
            flow_source = {"source": "derived", "unit": "million_yen", "method": flow_method}
        return {
            "Sales": sales,
            "OP": op,
            "OperatingMargin": op / sales * 100 if op is not None and sales else None,
            "NP": np_,
            "CFO": cfo,
            "CFI": cfi,
            "CFC": cfc,
            "FreeCF": cfc,
            "MetricSources": {
                "Sales": metric_source.copy(),
                "OP": metric_source.copy(),
                "OperatingMargin": {"source": "derived", "method": "OP / Sales", "unit": "percent"},
                "NP": metric_source.copy(),
                "CFO": flow_source.copy(),
                "CFI": flow_source.copy(),
                "CFC": {"source": "derived", "method": "CFO + CFI", "unit": "million_yen"},
                "FreeCF": {"source": "derived", "method": "alias of CFC", "unit": "million_yen"},
            },
        }

    def _label_year(fy_end: str) -> str:
        s = fy_end.replace("-", "")
        return s[2:4] if len(s) >= 4 else s[:2]

    periods: list[dict[str, Any]] = []
    for fy_end in sorted(fy_ends_selected):  # 古い順
        fy_rec = fy_by_end.get(fy_end)
        q2_rec = q2_by_end.get(fy_end)
        yr = _label_year(fy_end)

        # FY レコード未開示（当期進行中）: H1 のみ表示
        if fy_rec is None:
            if q2_rec and is_valid_financial_record(q2_rec):
                periods.append({
                    "label": f"{yr}H1",
                    "half": "H1",
                    "fy_end": fy_end,
                    "data": _make_data(
                        _m(q2_rec.get("Sales")),
                        _m(q2_rec.get("OP")),
                        _m(q2_rec.get("NP")),
                        _m(q2_rec.get("CFO")),
                        _m(q2_rec.get("CFI")),
                        source=_record_source(q2_rec),
                    ),
                })
            continue

        if q2_rec and is_valid_financial_record(q2_rec):
            h2_method_source = "EDINET" if _record_source(fy_rec) == "edinet" and _record_source(q2_rec) == "edinet" else "external"
            periods.append({
                "label": f"{yr}H1",
                "half": "H1",
                "fy_end": fy_end,
                "data": _make_data(
                    _m(q2_rec.get("Sales")),
                    _m(q2_rec.get("OP")),
                    _m(q2_rec.get("NP")),
                    _m(q2_rec.get("CFO")),
                    _m(q2_rec.get("CFI")),
                    source=_record_source(q2_rec),
                ),
            })
            periods.append({
                "label": f"{yr}H2",
                "half": "H2",
                "fy_end": fy_end,
                "data": _make_data(
                    _diff_m(fy_rec, q2_rec, "Sales"),
                    _diff_m(fy_rec, q2_rec, "OP"),
                    _diff_m(fy_rec, q2_rec, "NP"),
                    _diff_m(fy_rec, q2_rec, "CFO"),
                    _diff_m(fy_rec, q2_rec, "CFI"),
                    source="derived",
                    flow_method=f"FY {h2_method_source} - H1 {h2_method_source}",
                ),
            })
        else:
            periods.append({
                "label": f"{yr}FY",
                "half": None,
                "fy_end": fy_end,
                "data": _make_data(
                    _m(fy_rec.get("Sales")),
                    _m(fy_rec.get("OP")),
                    _m(fy_rec.get("NP")),
                    _m(fy_rec.get("CFO")),
                    _m(fy_rec.get("CFI")),
                    source=_record_source(fy_rec),
                ),
            })

    return periods
