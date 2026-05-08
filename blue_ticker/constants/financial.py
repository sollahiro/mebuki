"""財務計算単位定数"""

PERCENT     = 100        # 比率→パーセント変換乗数（ROE, ROIC, 配当性向等）
MILLION_YEN = 1_000_000  # 百万円換算

# 株式分割調整用。期末発行済株式数の細かな増減は自己株取得・消却等として扱い、
# 近年よく見られる分割比率に近い場合だけEPS/BPS調整へ反映する。
KNOWN_STOCK_SPLIT_MULTIPLIERS = (1.0, 1.05, 2.0, 3.0, 4.0, 5.0, 6.0, 10.0)
STOCK_SPLIT_SNAP_REL_TOLERANCE = 0.12
STOCK_SPLIT_NO_SPLIT_REL_TOLERANCE = 0.15

# WACC 計算用定数（暫定値）
WACC_MARKET_RISK_PREMIUM = 0.055   # 日本株MRP標準値 5.5%
WACC_DEFAULT_BETA        = 1.0     # 暫定β（市場平均）
WACC_RF_FALLBACK         = 0.010   # MOF CSV 取得失敗時フォールバック 1.0%
WACC_LABEL_TAX_RATE_OUT_OF_RANGE = "税率異常"
WACC_LABEL_COST_OF_DEBT_OUT_OF_RANGE = "負債コスト異常"
WACC_LABEL_MISSING_INPUT = "算出不可"
