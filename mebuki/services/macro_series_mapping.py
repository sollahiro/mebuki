"""
日銀API系列コードマッピング（新API v1/getDataCode用）
"""

# 金融政策 (Monetary Policy)
MONETARY_POLICY_SERIES = {
    "policy_rate": {"db": "IR01", "code": "MADR1Z@D"},         # 基準割引率・基準貸付利率
    "monetary_base": {"db": "MD01", "code": "MABS1AN11"},      # マネタリーベース平均残高
    "money_stock_m3": {"db": "MD02", "code": "MAM1YAM3M3MO"},  # マネーストックM3（前年比）
}



# コスト分析 - PR01: 国内企業物価指数（製造業 業種別類別、2020年基準）
# sector 引数（英語キー）→ APIコード のマッピング
COST_MANUFACTURING_SERIES = {
    "foods":                  {"db": "PR01", "code": "PRCG20_1200120001", "label_ja": "飲食料品"},
    "textiles":               {"db": "PR01", "code": "PRCG20_1200220001", "label_ja": "繊維製品"},
    "lumber":                 {"db": "PR01", "code": "PRCG20_1200320001", "label_ja": "木材・木製品"},
    "pulp_paper":             {"db": "PR01", "code": "PRCG20_1200420001", "label_ja": "パルプ・紙・同製品"},
    "chemicals":              {"db": "PR01", "code": "PRCG20_1200520001", "label_ja": "化学製品"},
    "petroleum_coal":         {"db": "PR01", "code": "PRCG20_1200620001", "label_ja": "石油・石炭製品"},
    "plastics":               {"db": "PR01", "code": "PRCG20_1200720001", "label_ja": "プラスチック製品"},
    "ceramics":               {"db": "PR01", "code": "PRCG20_1200820001", "label_ja": "窯業・土石製品"},
    "steel":                  {"db": "PR01", "code": "PRCG20_1200920001", "label_ja": "鉄鋼"},
    "nonferrous_metals":      {"db": "PR01", "code": "PRCG20_1201020001", "label_ja": "非鉄金属"},
    "metal_products":         {"db": "PR01", "code": "PRCG20_1201120001", "label_ja": "金属製品"},
    "general_machinery":      {"db": "PR01", "code": "PRCG20_1201220001", "label_ja": "はん用機器"},
    "production_machinery":   {"db": "PR01", "code": "PRCG20_1201320001", "label_ja": "生産用機器"},
    "business_machinery":     {"db": "PR01", "code": "PRCG20_1201420001", "label_ja": "業務用機器"},
    "electronic_components":  {"db": "PR01", "code": "PRCG20_1201520001", "label_ja": "電子部品・デバイス"},
    "electrical_machinery":   {"db": "PR01", "code": "PRCG20_1201620001", "label_ja": "電気機器"},
    "ict_equipment":          {"db": "PR01", "code": "PRCG20_1201720001", "label_ja": "情報通信機器"},
    "transportation_equipment": {"db": "PR01", "code": "PRCG20_1201820001", "label_ja": "輸送用機器"},
}

# コスト分析 - PR02: 企業向けサービス価格指数（非製造業 大類別、2020年基準）
COST_SERVICE_SERIES = {
    "finance_insurance":      {"db": "PR02", "code": "PRCS20_4200010001", "label_ja": "金融・保険"},
    "real_estate":            {"db": "PR02", "code": "PRCS20_4200010002", "label_ja": "不動産"},
    "transportation_postal":  {"db": "PR02", "code": "PRCS20_4200010003", "label_ja": "運輸・郵便"},
    "information_communication": {"db": "PR02", "code": "PRCS20_4200010004", "label_ja": "情報通信"},
    "leasing_rental":         {"db": "PR02", "code": "PRCS20_4200010005", "label_ja": "リース・レンタル"},
    "advertising":            {"db": "PR02", "code": "PRCS20_4200010006", "label_ja": "広告"},
    "other_services":         {"db": "PR02", "code": "PRCS20_4200010007", "label_ja": "諸サービス"},
}

# コスト分析 - 共通コスト圧力指標（全セクター）
COST_COMMON_SERIES = {
    # PR04: FD-ID指数（ステージ2 = 中間需要相当）
    "intermediate_goods":     {"db": "PR04", "code": "PRFI20_1I2G00000",  "label_ja": "中間需要：財"},
    "intermediate_services":  {"db": "PR04", "code": "PRFI20_1I2SD0000",  "label_ja": "中間需要：サービス"},
    "intermediate_energy":    {"db": "PR04", "code": "PRFI20_1I2G00200",  "label_ja": "中間需要：エネルギー"},
    # PR01: 輸入物価（円ベース・契約通貨ベース）
    "import_yen":             {"db": "PR01", "code": "PRCG20_2600000000", "label_ja": "輸入物価（円ベース）"},
    "import_contract":        {"db": "PR01", "code": "PRCG20_2500000000", "label_ja": "輸入物価（契約通貨）"},
    # PR02: 高人件費率サービス（人件費Proxy）
    "high_labor_cost":        {"db": "PR02", "code": "PRCS20_42S0000002",  "label_ja": "高人件費率サービス"},
}

# 為替 (FX)
FX_SERIES = {
    "usd_jpy": {"db": "FM08", "code": "FXERD04"},        # 東京市場 ドル・円 スポット 17時
    "real_effective_fx": {"db": "FM09", "code": "FX180110002"}, # 実質実効為替レート指数
}
