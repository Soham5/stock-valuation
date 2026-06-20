"""Probabilistic (Monte Carlo) DCF.

Point estimates hide the uncertainty in their inputs.  This module re-runs the
FCFF DCF across thousands of draws from distributions over the key
assumptions (growth, WACC, terminal growth) and returns the resulting
*distribution* of fair values: a mean, a standard deviation, percentile bands
and the probability of upside versus the current price.

The sampler is seeded for reproducibility (every run is auditable) and is
dependency-free (standard-library ``random``/``statistics`` only).
"""
from __future__ import annotations

import random
import statistics
from dataclasses import dataclass, field
from typing import Optional

from ..models import CompanyData
from .dcf import fcff_dcf


@dataclass(frozen=True)
class Triangular:
    """A triangular distribution defined by (low, mode, high)."""

    low: float
    mode: float
    high: float

    def clamp(self) -> "Triangular":
        lo, mo, hi = sorted((self.low, self.mode, self.high))
        return Triangular(lo, mo, hi)


@dataclass(frozen=True)
class MonteCarloResult:
    """Summary statistics of a Monte Carlo fair-value distribution."""

    samples: int
    mean: Optional[float]
    median: Optional[float]
    stdev: Optional[float]
    p5: Optional[float]
    p25: Optional[float]
    p75: Optional[float]
    p95: Optional[float]
    prob_upside: Optional[float]
    current_price: Optional[float]
    fair_values: list[float] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "samples": self.samples,
            "mean": self.mean,
            "median": self.median,
            "stdev": self.stdev,
            "p5": self.p5,
            "p25": self.p25,
            "p75": self.p75,
            "p95": self.p95,
            "prob_upside": self.prob_upside,
            "current_price": self.current_price,
        }


def _percentile(sorted_vals: list[float], pct: float) -> float:
    """Linear-interpolated percentile of an already-sorted list."""
    if not sorted_vals:
        raise ValueError("empty sequence")
    if len(sorted_vals) == 1:
        return sorted_vals[0]
    rank = (pct / 100.0) * (len(sorted_vals) - 1)
    lo = int(rank)
    hi = min(lo + 1, len(sorted_vals) - 1)
    frac = rank - lo
    return sorted_vals[lo] * (1.0 - frac) + sorted_vals[hi] * frac


def monte_carlo_dcf(
    company: CompanyData,
    tax_rate: float,
    growth: Triangular,
    wacc: Triangular,
    terminal_growth: Triangular,
    years: int = 5,
    iterations: int = 5000,
    seed: int = 12345,
    fade_to_terminal: bool = True,
) -> MonteCarloResult:
    """Run a Monte Carlo FCFF DCF and summarise the fair-value distribution.

    Each iteration draws growth, WACC and terminal growth from triangular
    distributions, enforces a positive WACC-minus-terminal-growth spread, and
    values the company.  Returns percentile bands and the probability that
    fair value exceeds the current price.
    """
    rng = random.Random(seed)
    g = growth.clamp()
    w = wacc.clamp()
    tg = terminal_growth.clamp()

    fair_values: list[float] = []
    for _ in range(max(1, iterations)):
        gi = rng.triangular(g.low, g.high, g.mode)
        wi = rng.triangular(w.low, w.high, w.mode)
        tgi = rng.triangular(tg.low, tg.high, tg.mode)
        # Keep the perpetuity well-defined: terminal growth must stay below WACC.
        tgi = min(tgi, wi - 0.005)
        res = fcff_dcf(
            company,
            wacc=wi,
            growth_rate=gi,
            tax_rate=tax_rate,
            terminal_growth=tgi,
            years=years,
            fade_to_terminal=fade_to_terminal,
        )
        fv = res.fair_value_per_share
        if fv is not None and fv == fv:  # not None / not NaN
            fair_values.append(fv)

    price = company.market.price
    if not fair_values:
        return MonteCarloResult(
            samples=0, mean=None, median=None, stdev=None,
            p5=None, p25=None, p75=None, p95=None,
            prob_upside=None, current_price=price, fair_values=[],
        )

    ordered = sorted(fair_values)
    n = len(ordered)
    prob_upside = (
        sum(1 for v in ordered if v > price) / n if price and price > 0 else None
    )
    return MonteCarloResult(
        samples=n,
        mean=statistics.fmean(ordered),
        median=statistics.median(ordered),
        stdev=statistics.pstdev(ordered) if n > 1 else 0.0,
        p5=_percentile(ordered, 5),
        p25=_percentile(ordered, 25),
        p75=_percentile(ordered, 75),
        p95=_percentile(ordered, 95),
        prob_upside=prob_upside,
        current_price=price,
        fair_values=ordered,
    )


def symmetric_band(mode: float, rel_spread: float) -> Triangular:
    """Convenience: a triangular band of +/- ``rel_spread`` around ``mode``."""
    return Triangular(mode * (1.0 - rel_spread), mode, mode * (1.0 + rel_spread))
