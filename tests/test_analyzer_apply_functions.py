"""
analyzer.py の _apply_* 関数ユニットテスト

各関数は IndividualAnalyzer に依存しない純粋なモジュール関数なので、
dict を直接組み立てて単体テストできる。
"""

import pytest
from mebuki.services.analyzer import (
    _apply_ibd,
    _apply_interest_expense,
    _apply_tax,
    _apply_gross_profit,
    _apply_operating_profit,
    _apply_net_revenue,
    _apply_employees,
    _apply_depreciation,
    _apply_wacc,
)
from mebuki.constants.financial import (
    MILLION_YEN,
    PERCENT,
    WACC_DEFAULT_BETA,
    WACC_LABEL_MISSING_INPUT,
    WACC_LABEL_TAX_RATE_OUT_OF_RANGE,
    WACC_MARKET_RISK_PREMIUM,
    WACC_RF_FALLBACK,
)


def _make_year(fy_end: str, **cd_fields) -> dict:
    return {
        "fy_end": fy_end,
        "CalculatedData": dict(cd_fields),
        "RawData": {},
    }


# ──────────────────────────────────────────────────────────────
# _apply_ibd
# ──────────────────────────────────────────────────────────────

class TestApplyIbd:
    def test_sets_ibd_fields(self):
        years = [_make_year("2024-03-31")]
        ibd_by_year = {
            "20240331": {
                "current": 500_000_000,
                "components": [
                    {"label": "短期借入金", "current": 200_000_000, "prior": 180_000_000},
                ],
                "accounting_standard": "J-GAAP",
            }
        }
        _apply_ibd(years, ibd_by_year, {})
        cd = years[0]["CalculatedData"]
        assert cd["InterestBearingDebt"] == pytest.approx(500_000_000 / MILLION_YEN)
        assert cd["IBDAccountingStandard"] == "J-GAAP"
        assert cd["MetricSources"]["InterestBearingDebt"]["source"] == "edinet"
        assert cd["MetricSources"]["InterestBearingDebt"]["unit"] == "million_yen"
        assert len(cd["IBDComponents"]) == 1
        assert cd["IBDComponents"][0]["label"] == "短期借入金"
        assert cd["IBDComponents"][0]["current"] == pytest.approx(200_000_000 / MILLION_YEN)
        assert cd["IBDComponents"][0]["prior"] == pytest.approx(180_000_000 / MILLION_YEN)

    def test_sets_doc_id(self):
        years = [_make_year("2024-03-31")]
        _apply_ibd(years, {}, {"20240331": "S100XXXX"})
        assert years[0]["CalculatedData"]["DocID"] == "S100XXXX"
        assert years[0]["CalculatedData"]["MetricSources"]["DocID"]["docID"] == "S100XXXX"

    def test_doc_id_independent_of_ibd(self):
        """IBDデータがなくてもDocIDはセットされる"""
        years = [_make_year("2024-03-31")]
        _apply_ibd(years, {}, {"20240331": "S100YYYY"})
        cd = years[0]["CalculatedData"]
        assert cd["DocID"] == "S100YYYY"
        assert "InterestBearingDebt" not in cd

    def test_calculates_roic(self):
        years = [_make_year("2024-03-31", NP=100.0, Eq=800.0)]
        ibd_by_year = {"20240331": {"current": 200_000_000, "components": [], "accounting_standard": "J-GAAP"}}
        _apply_ibd(years, ibd_by_year, {})
        cd = years[0]["CalculatedData"]
        ibd_m = 200_000_000 / MILLION_YEN
        expected = 100.0 / (800.0 + ibd_m) * PERCENT
        assert cd["ROIC"] == pytest.approx(expected)

    def test_skips_roic_when_np_missing(self):
        years = [_make_year("2024-03-31", Eq=800.0)]
        ibd_by_year = {"20240331": {"current": 200_000_000, "components": [], "accounting_standard": "J-GAAP"}}
        _apply_ibd(years, ibd_by_year, {})
        assert "ROIC" not in years[0]["CalculatedData"]

    def test_skips_when_no_ibd_entry(self):
        years = [_make_year("2024-03-31")]
        _apply_ibd(years, {}, {})
        assert "InterestBearingDebt" not in years[0]["CalculatedData"]

    def test_skips_when_current_is_none(self):
        years = [_make_year("2024-03-31")]
        ibd_by_year = {"20240331": {"current": None, "components": [], "accounting_standard": "J-GAAP"}}
        _apply_ibd(years, ibd_by_year, {})
        assert "InterestBearingDebt" not in years[0]["CalculatedData"]

    def test_component_with_none_prior(self):
        """prior が None のコンポーネントも None のまま保持される"""
        years = [_make_year("2024-03-31")]
        ibd_by_year = {
            "20240331": {
                "current": 100_000_000,
                "components": [{"label": "社債", "current": 100_000_000, "prior": None}],
                "accounting_standard": "IFRS",
            }
        }
        _apply_ibd(years, ibd_by_year, {})
        assert years[0]["CalculatedData"]["IBDComponents"][0]["prior"] is None


# ──────────────────────────────────────────────────────────────
# _apply_interest_expense
# ──────────────────────────────────────────────────────────────

class TestApplyInterestExpense:
    def test_sets_interest_expense(self):
        years = [_make_year("2024-03-31")]
        _apply_interest_expense(years, {"20240331": {"current": 1_000_000}})
        assert years[0]["CalculatedData"]["InterestExpense"] == pytest.approx(1_000_000 / MILLION_YEN)
        assert years[0]["CalculatedData"]["MetricSources"]["InterestExpense"]["source"] == "edinet"

    def test_skips_when_no_entry(self):
        years = [_make_year("2024-03-31")]
        _apply_interest_expense(years, {})
        assert "InterestExpense" not in years[0]["CalculatedData"]

    def test_skips_when_current_is_none(self):
        years = [_make_year("2024-03-31")]
        _apply_interest_expense(years, {"20240331": {"current": None}})
        assert "InterestExpense" not in years[0]["CalculatedData"]


class TestApplyDepreciation:
    def test_sets_depreciation_amortization(self):
        years = [_make_year("2024-03-31")]
        _apply_depreciation(years, {"20240331": {"current": 9_209_000_000}})
        assert years[0]["CalculatedData"]["DepreciationAmortization"] == pytest.approx(9_209_000_000 / MILLION_YEN)
        assert years[0]["CalculatedData"]["MetricSources"]["DepreciationAmortization"]["source"] == "edinet"

    def test_skips_when_no_entry(self):
        years = [_make_year("2024-03-31")]
        _apply_depreciation(years, {})
        assert "DepreciationAmortization" not in years[0]["CalculatedData"]

    def test_skips_when_current_is_none(self):
        years = [_make_year("2024-03-31")]
        _apply_depreciation(years, {"20240331": {"current": None}})
        assert "DepreciationAmortization" not in years[0]["CalculatedData"]


# ──────────────────────────────────────────────────────────────
# _apply_tax
# ──────────────────────────────────────────────────────────────

class TestApplyTax:
    def test_sets_tax_fields_computed(self):
        years = [_make_year("2024-03-31")]
        tax_by_year = {
            "20240331": {
                "method": "computed",
                "pretax_income": 50_000_000,
                "income_tax": 15_000_000,
                "effective_tax_rate": 0.30,
            }
        }
        _apply_tax(years, tax_by_year)
        cd = years[0]["CalculatedData"]
        assert cd["PretaxIncome"] == pytest.approx(50_000_000 / MILLION_YEN)
        assert cd["IncomeTax"] == pytest.approx(15_000_000 / MILLION_YEN)
        assert cd["EffectiveTaxRate"] == pytest.approx(0.30 * PERCENT)

    def test_sets_tax_fields_usgaap_html(self):
        years = [_make_year("2024-03-31")]
        tax_by_year = {
            "20240331": {
                "method": "usgaap_html",
                "pretax_income": 1_000_000,
                "income_tax": 300_000,
                "effective_tax_rate": 0.30,
            }
        }
        _apply_tax(years, tax_by_year)
        assert "PretaxIncome" in years[0]["CalculatedData"]

    def test_skips_unsupported_method(self):
        years = [_make_year("2024-03-31")]
        _apply_tax(years, {"20240331": {"method": "not_found", "pretax_income": 1_000_000}})
        assert "PretaxIncome" not in years[0]["CalculatedData"]

    def test_skips_when_no_entry(self):
        years = [_make_year("2024-03-31")]
        _apply_tax(years, {})
        assert "PretaxIncome" not in years[0]["CalculatedData"]

    def test_partial_fields_none_are_skipped(self):
        """pretax_income が None の場合はそのフィールドだけスキップ"""
        years = [_make_year("2024-03-31")]
        tax_by_year = {
            "20240331": {
                "method": "computed",
                "pretax_income": None,
                "income_tax": 15_000_000,
                "effective_tax_rate": 0.30,
            }
        }
        _apply_tax(years, tax_by_year)
        cd = years[0]["CalculatedData"]
        assert "PretaxIncome" not in cd
        assert cd["IncomeTax"] == pytest.approx(15_000_000 / MILLION_YEN)


# ──────────────────────────────────────────────────────────────
# _apply_gross_profit
# ──────────────────────────────────────────────────────────────

class TestApplyGrossProfit:
    def test_inserts_after_sales(self):
        years = [_make_year("2024-03-31", Sales=1000.0, OP=100.0)]
        gp_by_year = {"20240331": {"current": 400_000_000, "method": "direct"}}
        _apply_gross_profit(years, gp_by_year)
        keys = list(years[0]["CalculatedData"].keys())
        assert "GrossProfit" in keys
        assert keys.index("GrossProfit") == keys.index("Sales") + 1

    def test_calculates_margin(self):
        years = [_make_year("2024-03-31", Sales=1000.0)]
        gp_by_year = {"20240331": {"current": 400_000_000, "method": "direct"}}
        _apply_gross_profit(years, gp_by_year)
        cd = years[0]["CalculatedData"]
        gp_m = 400_000_000 / MILLION_YEN
        assert cd["GrossProfitMargin"] == pytest.approx(gp_m / 1000.0 * PERCENT)
        assert cd["MetricSources"]["GrossProfit"]["method"] == "direct"
        assert cd["MetricSources"]["GrossProfitMargin"]["source"] == "derived"

    def test_no_sales_margin_is_none(self):
        """Salesがない場合、GrossProfitはセットされるがMarginはNone"""
        years = [_make_year("2024-03-31")]
        gp_by_year = {"20240331": {"current": 400_000_000, "method": "direct"}}
        _apply_gross_profit(years, gp_by_year)
        cd = years[0]["CalculatedData"]
        assert cd["GrossProfit"] == pytest.approx(400_000_000 / MILLION_YEN)
        assert cd["GrossProfitMargin"] is None

    def test_sets_method(self):
        years = [_make_year("2024-03-31", Sales=1000.0)]
        gp_by_year = {"20240331": {"current": 300_000_000, "method": "computed"}}
        _apply_gross_profit(years, gp_by_year)
        assert years[0]["CalculatedData"]["GrossProfitMethod"] == "computed"

    def test_skips_when_no_entry(self):
        years = [_make_year("2024-03-31", Sales=1000.0)]
        _apply_gross_profit(years, {})
        assert "GrossProfit" not in years[0]["CalculatedData"]

    def test_skips_when_current_is_none(self):
        years = [_make_year("2024-03-31", Sales=1000.0)]
        _apply_gross_profit(years, {"20240331": {"current": None, "method": "direct"}})
        assert "GrossProfit" not in years[0]["CalculatedData"]


# ──────────────────────────────────────────────────────────────
# _apply_operating_profit
# ──────────────────────────────────────────────────────────────

class TestApplyOperatingProfit:
    def test_sets_op_and_margin(self):
        years = [_make_year("2024-03-31", Sales=1000.0)]
        op_by_year = {"20240331": {"current": 100_000_000, "label": "営業利益"}}
        _apply_operating_profit(years, op_by_year)
        cd = years[0]["CalculatedData"]
        op_m = 100_000_000 / MILLION_YEN
        assert cd["OP"] == pytest.approx(op_m)
        assert cd["OperatingMargin"] == pytest.approx(op_m / 1000.0 * PERCENT)

    def test_skips_if_op_already_set(self):
        years = [_make_year("2024-03-31", OP=50.0, Sales=1000.0)]
        op_by_year = {"20240331": {"current": 999_999_999, "label": "営業利益"}}
        _apply_operating_profit(years, op_by_year)
        assert years[0]["CalculatedData"]["OP"] == 50.0

    def test_sets_op_label_keijou(self):
        years = [_make_year("2024-03-31")]
        op_by_year = {"20240331": {"current": 100_000_000, "label": "経常利益"}}
        _apply_operating_profit(years, op_by_year)
        assert years[0]["CalculatedData"]["OPLabel"] == "経常利益"

    def test_no_label_no_op_label_key(self):
        years = [_make_year("2024-03-31")]
        op_by_year = {"20240331": {"current": 100_000_000, "label": "営業利益"}}
        _apply_operating_profit(years, op_by_year)
        assert "OPLabel" not in years[0]["CalculatedData"]

    def test_no_sales_no_margin(self):
        years = [_make_year("2024-03-31")]
        op_by_year = {"20240331": {"current": 100_000_000, "label": "営業利益"}}
        _apply_operating_profit(years, op_by_year)
        assert "OperatingMargin" not in years[0]["CalculatedData"]

    def test_skips_when_no_entry(self):
        years = [_make_year("2024-03-31", Sales=1000.0)]
        _apply_operating_profit(years, {})
        assert "OP" not in years[0]["CalculatedData"]


# ──────────────────────────────────────────────────────────────
# _apply_net_revenue
# ──────────────────────────────────────────────────────────────

class TestApplyNetRevenue:
    def test_sets_sales_when_none(self):
        years = [_make_year("2024-03-31")]
        nr_by_year = {"20240331": {"found": True, "net_revenue": 2_000_000_000, "business_profit": None}}
        _apply_net_revenue(years, nr_by_year)
        cd = years[0]["CalculatedData"]
        assert cd["Sales"] == pytest.approx(2_000_000_000 / MILLION_YEN)
        assert cd["SalesLabel"] == "純収益"
        assert cd["MetricSources"]["Sales"]["label"] == "純収益"

    def test_does_not_overwrite_existing_sales(self):
        years = [_make_year("2024-03-31", Sales=999.0)]
        nr_by_year = {"20240331": {"found": True, "net_revenue": 2_000_000_000, "business_profit": None}}
        _apply_net_revenue(years, nr_by_year)
        assert years[0]["CalculatedData"]["Sales"] == 999.0

    def test_recalculates_gp_margin_after_sales(self):
        years = [_make_year("2024-03-31", GrossProfit=500.0)]
        nr_by_year = {"20240331": {"found": True, "net_revenue": 2_000_000_000, "business_profit": None}}
        _apply_net_revenue(years, nr_by_year)
        cd = years[0]["CalculatedData"]
        nr_m = 2_000_000_000 / MILLION_YEN
        assert cd["GrossProfitMargin"] == pytest.approx(500.0 / nr_m * PERCENT)

    def test_sets_op_from_business_profit(self):
        years = [_make_year("2024-03-31", Sales=2000.0)]
        nr_by_year = {"20240331": {"found": True, "net_revenue": None, "business_profit": 300_000_000}}
        _apply_net_revenue(years, nr_by_year)
        cd = years[0]["CalculatedData"]
        bp_m = 300_000_000 / MILLION_YEN
        assert cd["OP"] == pytest.approx(bp_m)
        assert cd["OPLabel"] == "事業利益"
        assert cd["OperatingMargin"] == pytest.approx(bp_m / 2000.0 * PERCENT)

    def test_does_not_overwrite_existing_op(self):
        years = [_make_year("2024-03-31", OP=100.0, Sales=2000.0)]
        nr_by_year = {"20240331": {"found": True, "net_revenue": None, "business_profit": 999_999_999}}
        _apply_net_revenue(years, nr_by_year)
        assert years[0]["CalculatedData"]["OP"] == 100.0

    def test_skips_when_not_found(self):
        years = [_make_year("2024-03-31")]
        nr_by_year = {"20240331": {"found": False, "net_revenue": 2_000_000_000, "business_profit": None}}
        _apply_net_revenue(years, nr_by_year)
        assert "Sales" not in years[0]["CalculatedData"]

    def test_skips_when_no_entry(self):
        years = [_make_year("2024-03-31")]
        _apply_net_revenue(years, {})
        assert "Sales" not in years[0]["CalculatedData"]

    def test_sets_raw_data_sales(self):
        years = [_make_year("2024-03-31")]
        nr_by_year = {"20240331": {"found": True, "net_revenue": 2_000_000_000, "business_profit": None}}
        _apply_net_revenue(years, nr_by_year)
        assert years[0]["RawData"]["Sales"] == 2_000_000_000


# ──────────────────────────────────────────────────────────────
# _apply_employees
# ──────────────────────────────────────────────────────────────

class TestApplyEmployees:
    def test_sets_employees(self):
        years = [_make_year("2024-03-31")]
        _apply_employees(years, {"20240331": {"current": 5000}})
        assert years[0]["CalculatedData"]["Employees"] == 5000

    def test_skips_when_no_entry(self):
        years = [_make_year("2024-03-31")]
        _apply_employees(years, {})
        assert "Employees" not in years[0]["CalculatedData"]

    def test_skips_when_current_is_none(self):
        years = [_make_year("2024-03-31")]
        _apply_employees(years, {"20240331": {"current": None}})
        assert "Employees" not in years[0]["CalculatedData"]


# ──────────────────────────────────────────────────────────────
# _apply_wacc
# ──────────────────────────────────────────────────────────────

class TestApplyWacc:
    # rf_rates={} → get_rf_for_date がフォールバック値 WACC_RF_FALLBACK を使う
    _RF = WACC_RF_FALLBACK
    _RE = (_RF + WACC_DEFAULT_BETA * WACC_MARKET_RISK_PREMIUM) * PERCENT

    def test_sets_cost_of_equity(self):
        years = [_make_year("2024-03-31", Eq=800.0)]
        _apply_wacc(years, {})
        cd = years[0]["CalculatedData"]
        assert cd["CostOfEquity"] == pytest.approx(self._RE)
        assert cd["MetricSources"]["CostOfEquity"]["rf"] == WACC_RF_FALLBACK
        assert cd["MetricSources"]["CostOfEquity"]["rf_source"] == "fallback"

    def test_sets_mof_rf_source(self):
        years = [_make_year("2024-03-31", Eq=800.0)]
        _apply_wacc(years, {"2024-03-31": 0.01})
        cd = years[0]["CalculatedData"]
        assert cd["CostOfEquity"] == pytest.approx(self._RE)
        assert cd["MetricSources"]["CostOfEquity"]["rf"] == 0.01
        assert cd["MetricSources"]["CostOfEquity"]["rf_source"] == "mof"

    def test_no_ibd_wacc_equals_cost_of_equity(self):
        """無借金: WACC = CostOfEquity"""
        years = [_make_year("2024-03-31", Eq=800.0)]
        _apply_wacc(years, {})
        cd = years[0]["CalculatedData"]
        assert cd["WACC"] == pytest.approx(self._RE)

    def test_full_wacc_calculation(self):
        """IBD・IE・ETRが揃っている場合のWACC"""
        years = [_make_year("2024-03-31", Eq=800.0, InterestBearingDebt=200.0, InterestExpense=5.0, EffectiveTaxRate=30.0)]
        _apply_wacc(years, {})
        cd = years[0]["CalculatedData"]
        rf = self._RF
        re_ = rf + WACC_DEFAULT_BETA * WACC_MARKET_RISK_PREMIUM
        rd = 5.0 / 200.0
        tc = 30.0 / PERCENT
        v = 800.0 + 200.0
        expected_wacc = (800.0 / v * re_ + 200.0 / v * rd * (1 - tc)) * PERCENT
        assert cd["WACC"] == pytest.approx(expected_wacc)
        assert cd["MetricSources"]["WACC"]["source"] == "derived"

    def test_wacc_none_when_ie_missing(self):
        """IE がなければ WACC = None（CostOfEquity はセットされる）"""
        years = [_make_year("2024-03-31", Eq=800.0, InterestBearingDebt=200.0, EffectiveTaxRate=30.0)]
        _apply_wacc(years, {})
        cd = years[0]["CalculatedData"]
        assert cd["WACC"] is None
        assert cd["WACCLabel"] == WACC_LABEL_MISSING_INPUT
        assert cd["CostOfEquity"] == pytest.approx(self._RE)

    def test_cost_of_debt_is_set_when_tax_rate_is_out_of_range(self):
        """異常税率では WACC は出さないが、負債コストは IE / IBD で出す"""
        years = [
            _make_year(
                "2024-03-31",
                Eq=800.0,
                InterestBearingDebt=200.0,
                InterestExpense=5.0,
                EffectiveTaxRate=249.0,
            )
        ]
        _apply_wacc(years, {})
        cd = years[0]["CalculatedData"]
        assert cd["CostOfDebt"] == pytest.approx(2.5)
        assert cd["WACC"] is None
        assert cd["WACCLabel"] == WACC_LABEL_TAX_RATE_OUT_OF_RANGE

    def test_applies_to_multiple_years(self):
        years = [_make_year("2024-03-31", Eq=800.0), _make_year("2023-03-31", Eq=700.0)]
        _apply_wacc(years, {})
        assert "CostOfEquity" in years[0]["CalculatedData"]
        assert "CostOfEquity" in years[1]["CalculatedData"]
