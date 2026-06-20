import pytest

from stockval.valuation import dcf
from stockval.valuation.ai_analyst import AIAnalyst


def test_estimate_net_borrowing_from_debt_history(sample_company):
    # Debt rose 14M -> 20M over 3 steps => +2M/yr average.
    nb = dcf.estimate_net_borrowing(sample_company)
    assert nb == pytest.approx(2_000_000.0)


def test_net_borrowing_zero_without_history(sample_company):
    sample_company.historical_total_debt = []
    assert dcf.estimate_net_borrowing(sample_company) == 0.0


def test_fcfe_uses_modelled_net_borrowing(sample_company):
    # FCFF = 7.5M; after-tax interest = 1M*0.75 = 0.75M; net borrowing = +2M.
    fcfe = dcf.compute_fcfe(sample_company, tax_rate=0.25)
    assert fcfe == pytest.approx(7_500_000.0 - 750_000.0 + 2_000_000.0)


def test_fcfe_explicit_net_borrowing_override(sample_company):
    fcfe = dcf.compute_fcfe(sample_company, tax_rate=0.25, net_borrowing=0.0)
    assert fcfe == pytest.approx(7_500_000.0 - 750_000.0)


def test_faded_growth_between_bounds():
    flows = dcf.project_faded_cash_flows(100.0, 0.20, 0.02, 5)
    assert len(flows) == 5
    # First step grows near start rate, last step near terminal rate.
    assert flows[0] == pytest.approx(120.0)
    assert flows[-1] / flows[-2] - 1 == pytest.approx(0.02)


def test_fade_lowers_value_vs_constant_high_growth(sample_company):
    constant = dcf.fcff_dcf(sample_company, wacc=0.10, growth_rate=0.20, tax_rate=0.25)
    faded = dcf.fcff_dcf(
        sample_company, wacc=0.10, growth_rate=0.20, tax_rate=0.25, fade_to_terminal=True
    )
    assert faded.fair_value_per_share < constant.fair_value_per_share


def test_seasonality_detected_from_quarterly(sample_company):
    season = AIAnalyst(sample_company).detect_seasonality()
    assert season.is_seasonal
    assert 4 in season.peak_quarters


def test_seasonality_requires_quarterly_data(sample_company):
    sample_company.quarterly_revenue = []
    sample_company.quarterly_revenue_periods = []
    season = AIAnalyst(sample_company).detect_seasonality()
    assert not season.is_seasonal
    assert "quarterly" in season.reasoning.lower()
