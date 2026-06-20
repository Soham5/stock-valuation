"""Dividend Discount Models: Gordon growth and multi-stage.

    Gordon:        V = D1 / (ke - g)
    Two/Multi:     V = sum( Dt / (1+ke)^t ) + TV / (1+ke)^N
"""
from __future__ import annotations

from typing import Optional, Sequence

from ..config import DEFAULT_TERMINAL_GROWTH
from ..models import CompanyData, ValuationResult
from ..utils import gordon_terminal_value, present_value
from ..config import MIN_SPREAD


def gordon_growth(
    next_dividend: float,
    cost_of_equity: float,
    growth_rate: float,
) -> float:
    """Single-stage Gordon growth value: ``D1 / (ke - g)``."""
    spread = max(cost_of_equity - growth_rate, MIN_SPREAD)
    return next_dividend / spread


def gordon_ddm(
    company: CompanyData,
    cost_of_equity: float,
    growth_rate: float,
) -> ValuationResult:
    """Gordon constant-growth dividend discount valuation."""
    dps = company.market.dividend_per_share
    if not dps:
        return ValuationResult(
            method="DDM (Gordon)",
            fair_value_per_share=None,
            assumptions={"reason": "no dividend per share available"},
        )
    next_div = dps * (1.0 + growth_rate)
    fair_value = gordon_growth(next_div, cost_of_equity, growth_rate)
    return ValuationResult(
        method="DDM (Gordon)",
        fair_value_per_share=fair_value,
        assumptions={
            "cost_of_equity": cost_of_equity,
            "growth_rate": growth_rate,
            "current_dps": dps,
        },
        detail={"next_dividend": next_div},
    )


def multistage_ddm(
    current_dividend: float,
    cost_of_equity: float,
    high_growth_rate: float,
    high_growth_years: int,
    terminal_growth: float = DEFAULT_TERMINAL_GROWTH,
) -> ValuationResult:
    """Two-stage DDM: a high-growth phase then a Gordon terminal value.

    Parameters
    ----------
    current_dividend:
        Most recent dividend per share (D0).
    high_growth_rate:
        Dividend growth during the explicit high-growth phase.
    high_growth_years:
        Length of the high-growth phase in years.
    terminal_growth:
        Perpetual growth applied after the high-growth phase.
    """
    dividends: list[float] = []
    d = current_dividend
    for _ in range(high_growth_years):
        d = d * (1.0 + high_growth_rate)
        dividends.append(d)

    pv_explicit = sum(
        present_value(div, cost_of_equity, t + 1) for t, div in enumerate(dividends)
    )
    terminal_value = gordon_terminal_value(
        dividends[-1], cost_of_equity, terminal_growth
    )
    pv_terminal = present_value(terminal_value, cost_of_equity, high_growth_years)
    fair_value = pv_explicit + pv_terminal

    return ValuationResult(
        method="DDM (Multi-stage)",
        fair_value_per_share=fair_value,
        assumptions={
            "cost_of_equity": cost_of_equity,
            "high_growth_rate": high_growth_rate,
            "high_growth_years": high_growth_years,
            "terminal_growth": terminal_growth,
            "current_dividend": current_dividend,
        },
        detail={
            "projected_dividends": dividends,
            "pv_explicit": pv_explicit,
            "terminal_value": terminal_value,
            "pv_terminal": pv_terminal,
        },
    )
