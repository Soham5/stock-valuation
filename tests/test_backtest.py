from stockval.valuation import backtest as bt


def _obs(label, fv, p0, p1):
    return bt.Observation(label=label, fair_value=fv, price_at_signal=p0, price_forward=p1)


def test_signal_thresholds():
    assert _obs("a", 130, 100, 100).signal() == bt.BUY
    assert _obs("b", 80, 100, 100).signal() == bt.SELL
    assert _obs("c", 105, 100, 100).signal() == bt.HOLD


def test_perfect_predictor_has_full_hit_rate():
    obs = [
        _obs("up", 130, 100, 120),   # BUY, rose -> correct
        _obs("down", 70, 100, 80),   # SELL, fell -> correct
        _obs("up2", 140, 50, 60),    # BUY, rose -> correct
    ]
    report = bt.backtest(obs)
    assert report.directional_calls == 3
    assert report.hit_rate == 1.0
    assert report.avg_return_buy > 0


def test_information_coefficient_positive_when_aligned():
    obs = [
        _obs("a", 110, 100, 105),
        _obs("b", 120, 100, 115),
        _obs("c", 130, 100, 125),
        _obs("d", 90, 100, 95),
    ]
    report = bt.backtest(obs)
    assert report.information_coefficient is not None
    assert report.information_coefficient > 0.9


def test_empty_backtest():
    report = bt.backtest([])
    assert report.n == 0
    assert report.hit_rate is None
