import pytest

from stockval.valuation import sensitivity


def test_linspace_endpoints():
    out = sensitivity.linspace(0.0, 1.0, 5)
    assert out[0] == 0.0
    assert out[-1] == 1.0
    assert len(out) == 5


def test_sensitivity_grid_shape(sample_company):
    wacc_axis = [0.08, 0.10, 0.12]
    tg_axis = [0.02, 0.03]
    grid = sensitivity.sensitivity_grid(
        sample_company, growth_rate=0.05, tax_rate=0.25,
        wacc_range=wacc_axis, terminal_growth_range=tg_axis,
    )
    assert len(grid["values"]) == 3
    assert all(len(row) == 2 for row in grid["values"])
    # Lower WACC (row 0) should give higher value than higher WACC (row 2).
    assert grid["values"][0][0] > grid["values"][2][0]


def test_default_scenarios_order():
    scs = sensitivity.default_scenarios(0.08, 0.10, 0.03)
    names = [s.name for s in scs]
    assert names == ["Bear", "Base", "Bull"]
    # Bull should assume higher growth and lower WACC than Bear.
    bear, _, bull = scs
    assert bull.growth_rate > bear.growth_rate
    assert bull.wacc < bear.wacc


def test_scenario_analysis_ranks_bull_above_bear(sample_company):
    scs = sensitivity.default_scenarios(0.05, 0.10, 0.03)
    outcomes = sensitivity.scenario_analysis(
        sample_company, scs, tax_rate=0.25, current_price=100.0
    )
    by_name = {o.name: o for o in outcomes}
    assert by_name["Bull"].fair_value_per_share > by_name["Bear"].fair_value_per_share


def test_one_way_sensitivity():
    pairs = sensitivity.one_way_sensitivity(lambda w: 100 / w, [0.10, 0.20])
    assert pairs == [(0.10, pytest.approx(1000.0)), (0.20, pytest.approx(500.0))]
