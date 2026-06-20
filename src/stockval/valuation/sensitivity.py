"""Sensitivity and scenario analysis for the DCF engines.

* ``sensitivity_grid`` builds a 2-D table of fair values across a range of
  WACC and terminal-growth assumptions (the classic DCF "football field"
  driver).
* ``scenario_analysis`` evaluates discrete Bear / Base / Bull cases.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional, Sequence

from ..models import CompanyData
from .dcf import fcff_dcf


def linspace(start: float, stop: float, num: int) -> list[float]:
    """A tiny dependency-free linspace (inclusive of both ends)."""
    if num <= 1:
        return [start]
    step = (stop - start) / (num - 1)
    return [start + step * i for i in range(num)]


def sensitivity_grid(
    company: CompanyData,
    growth_rate: float,
    tax_rate: float,
    wacc_range: Sequence[float],
    terminal_growth_range: Sequence[float],
) -> dict:
    """Fair-value-per-share grid over (WACC x terminal growth).

    Returns a dict with ``wacc`` (rows), ``terminal_growth`` (cols) and a
    matrix ``values[row][col]`` of fair values (``None`` where infeasible).
    """
    matrix: list[list[Optional[float]]] = []
    for w in wacc_range:
        row: list[Optional[float]] = []
        for g in terminal_growth_range:
            res = fcff_dcf(
                company,
                wacc=w,
                growth_rate=growth_rate,
                tax_rate=tax_rate,
                terminal_growth=g,
            )
            row.append(res.fair_value_per_share)
        matrix.append(row)
    return {
        "wacc": list(wacc_range),
        "terminal_growth": list(terminal_growth_range),
        "values": matrix,
    }


@dataclass(frozen=True)
class Scenario:
    name: str
    growth_rate: float
    wacc: float
    terminal_growth: float


@dataclass(frozen=True)
class ScenarioOutcome:
    name: str
    fair_value_per_share: Optional[float]
    upside: Optional[float]


def default_scenarios(base_growth: float, base_wacc: float, base_tg: float) -> list[Scenario]:
    """Bear / Base / Bull cases anchored on the base assumptions."""
    return [
        Scenario("Bear", base_growth - 0.03, base_wacc + 0.015, base_tg - 0.005),
        Scenario("Base", base_growth, base_wacc, base_tg),
        Scenario("Bull", base_growth + 0.03, base_wacc - 0.015, base_tg + 0.005),
    ]


def scenario_analysis(
    company: CompanyData,
    scenarios: Sequence[Scenario],
    tax_rate: float,
    current_price: Optional[float] = None,
) -> list[ScenarioOutcome]:
    """Evaluate each scenario through the FCFF DCF engine."""
    outcomes: list[ScenarioOutcome] = []
    for sc in scenarios:
        res = fcff_dcf(
            company,
            wacc=sc.wacc,
            growth_rate=sc.growth_rate,
            tax_rate=tax_rate,
            terminal_growth=sc.terminal_growth,
        )
        outcomes.append(
            ScenarioOutcome(
                name=sc.name,
                fair_value_per_share=res.fair_value_per_share,
                upside=res.upside(current_price),
            )
        )
    return outcomes


def one_way_sensitivity(
    valuation_fn: Callable[[float], Optional[float]],
    values: Sequence[float],
) -> list[tuple[float, Optional[float]]]:
    """Generic one-variable sweep: pair each input with its fair value."""
    return [(v, valuation_fn(v)) for v in values]
