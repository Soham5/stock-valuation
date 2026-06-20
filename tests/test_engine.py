from stockval.engine import Assumptions, derive_assumptions, run_valuation


def test_derive_assumptions_from_company(sample_company):
    a = derive_assumptions(sample_company)
    assert a.beta == 1.2
    assert a.tax_rate == 0.25
    # implied cost of debt = 1M / 20M = 5%
    assert a.pre_tax_cost_of_debt == 0.05


def test_run_valuation_produces_results(sample_company):
    summary = run_valuation(sample_company, Assumptions(beta=1.2, growth_rate=0.05))
    methods = {r.method for r in summary.results}
    assert "DCF (FCFF)" in methods
    assert "DCF (FCFE)" in methods
    assert "DDM (Gordon)" in methods
    assert summary.blended_fair_value is not None


def test_recommendation_buckets(sample_company):
    summary = run_valuation(sample_company, Assumptions(beta=1.2, growth_rate=0.05))
    assert summary.recommendation() in {"BUY", "HOLD", "SELL", "N/A"}


def test_peer_multiples_feed_engine(sample_company):
    from dataclasses import replace

    peer = replace(sample_company, market=replace(sample_company.market, ticker="PEER"))
    summary = run_valuation(sample_company, Assumptions(), peers=[peer])
    methods = {r.method for r in summary.results}
    assert "Multiple (P/E)" in methods
