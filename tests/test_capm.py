from stockval.valuation import capm


def test_cost_of_equity_capm():
    # 4% + 1.2 * 5% = 10%
    assert capm.cost_of_equity(1.2, 0.04, 0.05) == 0.10


def test_after_tax_cost_of_debt():
    assert capm.after_tax_cost_of_debt(0.08, 0.25) == 0.06


def test_implied_cost_of_debt():
    assert capm.implied_cost_of_debt(1_000_000, 20_000_000) == 0.05
    assert capm.implied_cost_of_debt(None, 20_000_000) is None
    assert capm.implied_cost_of_debt(1_000_000, 0) is None


def test_wacc_weights_and_blend():
    res = capm.wacc(
        equity_value=80.0,
        debt_value=20.0,
        beta=1.0,
        pre_tax_cost_of_debt=0.10,
        risk_free_rate=0.04,
        equity_risk_premium=0.05,
        tax_rate=0.25,
    )
    assert res.equity_weight == 0.8
    assert res.debt_weight == 0.2
    # ke = 9%, kd_at = 7.5% -> 0.8*0.09 + 0.2*0.075 = 0.087
    assert abs(res.wacc - 0.087) < 1e-9


def test_wacc_all_equity_fallback():
    res = capm.wacc(0.0, 0.0, beta=1.0, pre_tax_cost_of_debt=0.05)
    assert res.equity_weight == 1.0
    assert res.debt_weight == 0.0
