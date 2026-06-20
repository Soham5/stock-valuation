import pytest

from stockval.utils import gordon_terminal_value, present_value
from stockval.valuation import dcf


def test_project_cash_flows_growth():
    flows = dcf.project_cash_flows(100.0, 0.10, 3)
    assert flows == pytest.approx([110.0, 121.0, 133.1])


def test_compute_fcff_from_components(sample_company):
    # NOPAT = 12M*0.75 = 9M; +3M D&A -4M capex -0.5M dWC = 7.5M
    fcff = dcf.compute_fcff(sample_company, tax_rate=0.25)
    assert fcff == pytest.approx(7_500_000.0)


def test_compute_fcff_prefers_reported_fcf(sample_company):
    sample_company.financials.__dict__  # ensure attribute access works
    from dataclasses import replace

    fin = replace(sample_company.financials, free_cash_flow=9_000_000.0)
    sample_company.financials = fin
    assert dcf.compute_fcff(sample_company, 0.25) == 9_000_000.0


def test_discount_cash_flows_matches_manual():
    flows = [100.0, 110.0]
    out = dcf.discount_cash_flows(flows, discount_rate=0.10, terminal_growth=0.02)
    pv1 = present_value(100.0, 0.10, 1)
    pv2 = present_value(110.0, 0.10, 2)
    tv = gordon_terminal_value(110.0, 0.10, 0.02)
    pv_tv = present_value(tv, 0.10, 2)
    assert out["pv_explicit"] == pytest.approx(pv1 + pv2)
    assert out["total"] == pytest.approx(pv1 + pv2 + pv_tv)


def test_fcff_dcf_produces_positive_value(sample_company):
    res = dcf.fcff_dcf(sample_company, wacc=0.10, growth_rate=0.05, tax_rate=0.25)
    assert res.fair_value_per_share is not None
    assert res.enterprise_value > 0
    # equity value = EV - net debt (20M - 5M = 15M)
    assert res.equity_value == pytest.approx(res.enterprise_value - 15_000_000.0)


def test_fcff_dcf_handles_missing_shares(sample_company):
    from dataclasses import replace

    sample_company.market = replace(sample_company.market, shares_outstanding=None)
    res = dcf.fcff_dcf(sample_company, wacc=0.10, growth_rate=0.05, tax_rate=0.25)
    assert res.fair_value_per_share is None


def test_lower_wacc_increases_value(sample_company):
    low = dcf.fcff_dcf(sample_company, wacc=0.08, growth_rate=0.05, tax_rate=0.25)
    high = dcf.fcff_dcf(sample_company, wacc=0.12, growth_rate=0.05, tax_rate=0.25)
    assert low.fair_value_per_share > high.fair_value_per_share
