import pytest

from stockval.valuation import comparables, multiples


def test_pe_valuation(sample_company):
    res = multiples.pe_valuation(sample_company, target_pe=15.0)
    # EPS=8 -> 120
    assert res.fair_value_per_share == pytest.approx(120.0)


def test_ev_ebitda_valuation(sample_company):
    res = multiples.ev_ebitda_valuation(sample_company, target_ev_ebitda=10.0)
    # EV = 15M*10 = 150M; equity = 150M - net debt(15M) = 135M; /1M shares
    assert res.fair_value_per_share == pytest.approx(135.0)


def test_pb_valuation(sample_company):
    res = multiples.pb_valuation(sample_company, target_pb=3.0)
    # BVPS=40 -> 120
    assert res.fair_value_per_share == pytest.approx(120.0)


def test_current_pe_and_pb(sample_company):
    assert multiples.current_pe(sample_company) == pytest.approx(12.5)  # 100/8
    assert multiples.current_pb(sample_company) == pytest.approx(2.5)  # 100/40


def test_benchmark_medians(sample_company):
    from dataclasses import replace

    peer2 = replace(
        sample_company,
        market=replace(sample_company.market, ticker="P2"),
    )
    bench = comparables.benchmark([sample_company, peer2])
    assert bench.median_pe == pytest.approx(12.5)  # both have price/eps = 100/8
    assert len(bench.rows) == 2
