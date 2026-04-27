"""財務計算単位定数"""

PERCENT     = 100        # 比率→パーセント変換乗数（ROE, ROIC, 配当性向等）
MILLION_YEN = 1_000_000  # 百万円換算

# WACC 計算用定数（暫定値）
WACC_MARKET_RISK_PREMIUM = 0.055   # 日本株MRP標準値 5.5%
WACC_DEFAULT_BETA        = 1.0     # 暫定β（市場平均）
WACC_RF_FALLBACK         = 0.010   # MOF CSV 取得失敗時フォールバック 1.0%
