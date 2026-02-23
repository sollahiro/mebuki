import logging
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from typing import Dict, Any, List, Optional
from backend.utils.boj_client import BOJClient
from .macro_series_mapping import (
    MONETARY_POLICY_SERIES, FX_SERIES,
    COST_MANUFACTURING_SERIES, COST_SERVICE_SERIES, COST_COMMON_SERIES,
)
from backend.services.data_service import data_service

logger = logging.getLogger(__name__)

# 製造業セクター一覧
MANUFACTURING_SECTORS = set(COST_MANUFACTURING_SERIES.keys())
# 非製造業セクター一覧
SERVICE_SECTORS = set(COST_SERVICE_SERIES.keys())

class MacroAnalyzer:
    """
    マクロ分析業務ロジッククラス（新API対応版）
    """
    def __init__(self):
        self.boj_client = BOJClient(cache=data_service.cache_manager)

    def get_monetary_policy_status(self, start_date: Optional[str] = None, end_date: Optional[str] = None) -> Dict[str, Any]:
        """金融政策の現状と時系列データを取得"""
        results = {}
        for key, info in MONETARY_POLICY_SERIES.items():
            db = info["db"]
            code = info["code"]
            results[key] = self.boj_client.get_time_series(db, code, start_date, end_date)
        
        return {
            "title": "金融政策 指標データ",
            "indicators": results,
            "description": "基準貸付利率、マネタリーベース、マネーストックM3の推移。"
        }

    def get_fx_environment(self, start_date: Optional[str] = None, end_date: Optional[str] = None) -> Dict[str, Any]:
        """為替環境のデータを取得"""
        results = {}
        for key, info in FX_SERIES.items():
            results[key] = self.boj_client.get_time_series(info["db"], info["code"], start_date, end_date)
            
        return {
            "title": "為替環境 指標データ",
            "indicators": results,
            "description": "ドル円スポットレート（17時）および実質実効為替レート。"
        }

    def get_cost_environment(
        self,
        sector: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        コスト分析: 業種別のコストプッシュ圧力を多角的に取得。

        Args:
            sector: 業種コード（英語キー。例: "transportation_equipment", "information_communication"）
            start_date: 開始月 (YYYYMM)。未指定時は直近13ヶ月。
            end_date: 終了月 (YYYYMM)。未指定時は最新月まで。
        """
        # --- sector 判定 ---
        sector = sector.strip().lower()
        if sector in MANUFACTURING_SECTORS:
            is_manufacturing = True
            price_info = COST_MANUFACTURING_SERIES[sector]
            spread_label = "販価 - 中間(財)"
        elif sector in SERVICE_SECTORS:
            is_manufacturing = False
            price_info = COST_SERVICE_SERIES[sector]
            spread_label = "販価 - 中間(ｻ)"
        else:
            all_sectors = list(MANUFACTURING_SECTORS) + list(SERVICE_SECTORS)
            raise ValueError(
                f"不明なsector: '{sector}'. 使用可能な値: {all_sectors}"
            )

        sector_label_ja = price_info["label_ja"]

        # --- 期間の確定（デフォルト: 直近13ヶ月）---
        if not start_date:
            dt_start = datetime.now() - relativedelta(months=13)
            start_date = dt_start.strftime("%Y%m")
        # end_date未指定はAPIに渡さない（最新まで）

        logger.info(
            f"get_cost_environment: sector={sector}, period={start_date}～{end_date or '最新'}"
        )

        # --- データ取得 ---
        # 1. 販価系列
        price_data = self.boj_client.get_time_series(
            price_info["db"], price_info["code"], start_date, end_date
        )

        # 2. 共通コスト指標
        common_data: Dict[str, List[Dict[str, Any]]] = {}
        for key, info in COST_COMMON_SERIES.items():
            common_data[key] = self.boj_client.get_time_series(
                info["db"], info["code"], start_date, end_date
            )

        # --- 月ごとのアライン（Dictマージ）---
        # 各系列を {date: value} の辞書に変換
        def to_dict(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
            return {str(r["date"])[:6]: r["value"] for r in rows if r.get("date")}

        price_dict    = to_dict(price_data)
        common_dicts  = {k: to_dict(v) for k, v in common_data.items()}

        # 全日付の和集合から月一覧を作成（降順）
        all_dates = sorted(
            set(price_dict.keys()).union(*[d.keys() for d in common_dicts.values()]),
            reverse=True
        )

        # --- テーブル構築 ---
        table_rows: List[Dict[str, Any]] = []
        for date in all_dates:
            selling_price = price_dict.get(date)
            inter_goods   = common_dicts["intermediate_goods"].get(date)
            inter_svc     = common_dicts["intermediate_services"].get(date)
            energy        = common_dicts["intermediate_energy"].get(date)
            labor         = common_dicts["high_labor_cost"].get(date)
            import_yen    = common_dicts["import_yen"].get(date)
            import_ccy    = common_dicts["import_contract"].get(date)

            # スプレッド計算（原指数差）
            if is_manufacturing:
                spread_base = inter_goods
            else:
                spread_base = inter_svc

            spread = None
            if selling_price is not None and spread_base is not None:
                spread = round(selling_price - spread_base, 2)

            table_rows.append({
                "month":              date,
                "selling_price":      selling_price,
                "intermediate_goods": inter_goods,
                "intermediate_svc":   inter_svc,
                "spread":             spread,
                "energy":             energy,
                "labor_proxy":        labor,
                "import_yen":         import_yen,
                "import_contract":    import_ccy,
            })

        # スプレッドの定義説明
        spread_note = (
            f"製造業では「販価 - 中間(財)」を主スプレッドとして採用。"
            if is_manufacturing
            else f"非製造業では「販価 - 中間(サービス)」を主スプレッドとして採用。"
        )

        return {
            "title": f"コスト分析：{sector_label_ja}（{sector}）",
            "sector": sector,
            "sector_label_ja": sector_label_ja,
            "is_manufacturing": is_manufacturing,
            "period": {"start": start_date, "end": end_date or "最新"},
            "spread_definition": spread_label,
            "spread_note": spread_note,
            "unit_note": "全指標は原指数（2020年=100）。スプレッドは販価指数 - コスト指数の差。",
            "columns": {
                "month":              "月",
                "selling_price":      "販価",
                "intermediate_goods": "中間(財)",
                "intermediate_svc":   "中間(ｻ)",
                "spread":             "ｽﾌﾟﾚｯﾄﾞ",
                "energy":             "ｴﾈﾙｷﾞｰ",
                "labor_proxy":        "人件費",
                "import_yen":         "輸入(円)",
                "import_contract":    "輸入(契)",
            },
            "data": table_rows,
        }


# シングルトン
macro_analyzer = MacroAnalyzer()
