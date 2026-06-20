import pytest

from stockval.valuation import ddm


def test_gordon_growth_formula():
    # D1=2.1, ke=10%, g=5% -> 2.1 / 0.05 = 42
    assert ddm.gordon_growth(2.1, 0.10, 0.05) == pytest.approx(42.0)


def test_gordon_ddm_uses_current_dps(sample_company):
    res = ddm.gordon_ddm(sample_company, cost_of_equity=0.10, growth_rate=0.05)
    # D0=2 -> D1=2.1 -> 2.1/0.05 = 42
    assert res.fair_value_per_share == pytest.approx(42.0)


def test_gordon_ddm_no_dividend(sample_company):
    from dataclasses import replace

    sample_company.market = replace(sample_company.market, dividend_per_share=None)
    res = ddm.gordon_ddm(sample_company, 0.10, 0.05)
    assert res.fair_value_per_share is None


def test_multistage_ddm_positive_and_bounded():
    res = ddm.multistage_ddm(
        current_dividend=2.0,
        cost_of_equity=0.10,
        high_growth_rate=0.08,
        high_growth_years=5,
        terminal_growth=0.03,
    )
    assert res.fair_value_per_share > 0
    assert len(res.detail["projected_dividends"]) == 5


def test_spread_floor_prevents_blowup():
    # g >= ke should not yield infinity due to the spread floor.
    value = ddm.gordon_growth(2.0, 0.05, 0.05)
    assert value < 1e9
