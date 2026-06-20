"""Backtesting harness for valuation signals.

A valuation model is only credible if its calls have predictive power.  This
module scores historical observations \u2014 each pairing a model's fair value and
the price at signal time with the realised price some horizon later \u2014 and
reports the metrics a research desk actually cares about:

* **Hit rate** \u2014 share of directional calls (BUY/SELL) that were right.
* **Average forward return by signal bucket** (BUY / HOLD / SELL).
* **Information coefficient (IC)** \u2014 Spearman rank correlation between
  predicted upside and realised forward return.

It operates on plain data points, so it is fully offline and testable; the
caller is responsible for sourcing point-in-time snapshots (avoiding
look-ahead bias).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Sequence

BUY = "BUY"
HOLD = "HOLD"
SELL = "SELL"


@dataclass(frozen=True)
class Observation:
    """One backtest data point.

    Parameters
    ----------
    label:
        Identifier (e.g. ``"AAPL@2022-01"``) for traceability.
    fair_value:
        Model fair value per share at signal time.
    price_at_signal:
        Market price when the signal was generated.
    price_forward:
        Realised market price after the holding horizon.
    """

    label: str
    fair_value: float
    price_at_signal: float
    price_forward: float

    @property
    def predicted_upside(self) -> Optional[float]:
        if self.price_at_signal <= 0:
            return None
        return self.fair_value / self.price_at_signal - 1.0

    @property
    def realised_return(self) -> Optional[float]:
        if self.price_at_signal <= 0:
            return None
        return self.price_forward / self.price_at_signal - 1.0

    def signal(self, threshold: float = 0.15) -> str:
        up = self.predicted_upside
        if up is None:
            return HOLD
        if up >= threshold:
            return BUY
        if up <= -threshold:
            return SELL
        return HOLD


@dataclass(frozen=True)
class BacktestReport:
    n: int
    hit_rate: Optional[float]
    avg_return_buy: Optional[float]
    avg_return_hold: Optional[float]
    avg_return_sell: Optional[float]
    information_coefficient: Optional[float]
    directional_calls: int

    def as_dict(self) -> dict:
        return {
            "n": self.n,
            "hit_rate": self.hit_rate,
            "avg_return_buy": self.avg_return_buy,
            "avg_return_hold": self.avg_return_hold,
            "avg_return_sell": self.avg_return_sell,
            "information_coefficient": self.information_coefficient,
            "directional_calls": self.directional_calls,
        }


def _mean(values: Sequence[float]) -> Optional[float]:
    return sum(values) / len(values) if values else None


def _rank(values: Sequence[float]) -> list[float]:
    """Average ranks (ties shared), as needed for Spearman correlation."""
    order = sorted(range(len(values)), key=lambda i: values[i])
    ranks = [0.0] * len(values)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and values[order[j + 1]] == values[order[i]]:
            j += 1
        avg_rank = (i + j) / 2.0 + 1.0
        for k in range(i, j + 1):
            ranks[order[k]] = avg_rank
        i = j + 1
    return ranks


def _pearson(xs: Sequence[float], ys: Sequence[float]) -> Optional[float]:
    n = len(xs)
    if n < 2:
        return None
    mx = sum(xs) / n
    my = sum(ys) / n
    sxx = sum((x - mx) ** 2 for x in xs)
    syy = sum((y - my) ** 2 for y in ys)
    if sxx == 0 or syy == 0:
        return None
    sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    return sxy / (sxx ** 0.5 * syy ** 0.5)


def spearman_ic(xs: Sequence[float], ys: Sequence[float]) -> Optional[float]:
    """Spearman rank correlation between predicted upside and realised return."""
    if len(xs) != len(ys) or len(xs) < 2:
        return None
    return _pearson(_rank(xs), _rank(ys))


def backtest(
    observations: Sequence[Observation],
    threshold: float = 0.15,
) -> BacktestReport:
    """Score a set of observations into a :class:`BacktestReport`."""
    valid = [
        o
        for o in observations
        if o.predicted_upside is not None and o.realised_return is not None
    ]
    if not valid:
        return BacktestReport(0, None, None, None, None, None, 0)

    buys, holds, sells = [], [], []
    correct = 0
    directional = 0
    for o in valid:
        sig = o.signal(threshold)
        ret = o.realised_return  # not None for valid
        if sig == BUY:
            buys.append(ret)
            directional += 1
            correct += 1 if ret > 0 else 0
        elif sig == SELL:
            sells.append(ret)
            directional += 1
            correct += 1 if ret < 0 else 0
        else:
            holds.append(ret)

    hit_rate = correct / directional if directional else None
    ic = spearman_ic(
        [o.predicted_upside for o in valid],
        [o.realised_return for o in valid],
    )
    return BacktestReport(
        n=len(valid),
        hit_rate=hit_rate,
        avg_return_buy=_mean(buys),
        avg_return_hold=_mean(holds),
        avg_return_sell=_mean(sells),
        information_coefficient=ic,
        directional_calls=directional,
    )
