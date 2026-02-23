"""
日銀API系列コードマッピング（新API v1/getDataCode用）
"""

# 金融政策 (Monetary Policy)
MONETARY_POLICY_SERIES = {
    "policy_rate": {"db": "IR01", "code": "MADR1Z@D"},         # 基準割引率・基準貸付利率
    "monetary_base": {"db": "MD01", "code": "MABS1AN11"},      # マネタリーベース平均残高
    "money_stock_m3": {"db": "MD02", "code": "MAM1YAM3M3MO"},  # マネーストックM3（前年比）
}


# 為替 (FX)
FX_SERIES = {
    "usd_jpy": {"db": "FM08", "code": "FXERD04"},        # 東京市場 ドル・円 スポット 17時
    "real_effective_fx": {"db": "FM09", "code": "FX180110002"}, # 実質実効為替レート指数
}
