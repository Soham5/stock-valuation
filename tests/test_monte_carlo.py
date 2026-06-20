from stockval.valuation import monte_carlo as mc


def test_monte_carlo_is_reproducible(sample_company):
    growth = mc.symmetric_band(0.05, 0.4)
    wacc = mc.symmetric_band(0.10, 0.2)
    tg = mc.Triangular(0.015, 0.025, 0.035)

    r1 = mc.monte_carlo_dcf(sample_company, 0.25, growth, wacc, tg, iterations=500)
    r2 = mc.monte_carlo_dcf(sample_company, 0.25, growth, wacc, tg, iterations=500)
    assert r1.mean == r2.mean
    assert r1.p5 == r2.p5
    assert r1.p95 == r2.p95


def test_monte_carlo_percentiles_ordered(sample_company):
    growth = mc.symmetric_band(0.05, 0.4)
    wacc = mc.symmetric_band(0.10, 0.2)
    tg = mc.Triangular(0.015, 0.025, 0.035)
    res = mc.monte_carlo_dcf(sample_company, 0.25, growth, wacc, tg, iterations=1000)
    assert res.samples > 0
    assert res.p5 <= res.p25 <= res.median <= res.p75 <= res.p95
    assert 0.0 <= res.prob_upside <= 1.0


def test_monte_carlo_handles_missing_data(sample_company):
    from dataclasses import replace

    sample_company.market = replace(sample_company.market, shares_outstanding=None)
    res = mc.monte_carlo_dcf(
        sample_company, 0.25,
        mc.symmetric_band(0.05, 0.3),
        mc.symmetric_band(0.10, 0.2),
        mc.Triangular(0.02, 0.025, 0.03),
        iterations=100,
    )
    assert res.samples == 0
    assert res.mean is None
