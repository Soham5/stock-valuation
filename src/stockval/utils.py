"""Small numerical helpers used across valuation engines."""
from __future__ import annotations

from typing import Iterable, Optional, Sequence

from .config import MIN_SPREAD


def is_number(x) -> bool:
    """True for a finite real number (rejects None and NaN)."""
    try:
        return x is not None and float(x) == float(x) and abs(float(x)) != float("inf")
    except (TypeError, ValueError):
        return False


def safe_div(numerator: Optional[float], denominator: Optional[float]) -> Optional[float]:
    """Divide, returning ``None`` on missing data or zero denominator."""
    if not is_number(numerator) or not is_number(denominator) or denominator == 0:
        return None
    return numerator / denominator


def present_value(cash_flow: float, rate: float, period: float) -> float:
    """Discount a single cash flow ``period`` years into the future."""
    return cash_flow / (1.0 + rate) ** period


def gordon_terminal_value(
    final_cash_flow: float, discount_rate: float, growth_rate: float
) -> float:
    """Gordon-growth terminal value of a perpetuity that grows at ``growth_rate``.

    ``final_cash_flow`` is the last *explicit* cash flow; it is grown one
    period before being capitalised.  The discount-growth spread is floored
    to keep the result finite.
    """
    spread = max(discount_rate - growth_rate, MIN_SPREAD)
    return final_cash_flow * (1.0 + growth_rate) / spread


def cagr(series: Sequence[float]) -> Optional[float]:
    """Compound annual growth rate across an ordered series (oldest first)."""
    clean = [s for s in series if is_number(s)]
    if len(clean) < 2 or clean[0] <= 0 or clean[-1] <= 0:
        return None
    periods = len(clean) - 1
    return (clean[-1] / clean[0]) ** (1.0 / periods) - 1.0


def mean(values: Iterable[float]) -> Optional[float]:
    """Arithmetic mean of the finite numbers in ``values``."""
    clean = [float(v) for v in values if is_number(v)]
    if not clean:
        return None
    return sum(clean) / len(clean)


def clamp(value: float, low: float, high: float) -> float:
    """Constrain ``value`` to the inclusive ``[low, high]`` range."""
    return max(low, min(high, value))
