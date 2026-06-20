"""Cost of capital: CAPM cost of equity and the WACC.

References the standard Financial Management treatment:

    Cost of equity (CAPM)  ke = rf + beta * (ERP)
    After-tax cost of debt kd = r_debt * (1 - tax)
    WACC = (E/V) * ke + (D/V) * kd_after_tax
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from ..config import (
    DEFAULT_EQUITY_RISK_PREMIUM,
    DEFAULT_RISK_FREE_RATE,
    DEFAULT_TAX_RATE,
)
from ..utils import safe_div


def cost_of_equity(
    beta: float,
    risk_free_rate: float = DEFAULT_RISK_FREE_RATE,
    equity_risk_premium: float = DEFAULT_EQUITY_RISK_PREMIUM,
) -> float:
    """CAPM cost of equity: ``rf + beta * ERP``."""
    return risk_free_rate + beta * equity_risk_premium


def after_tax_cost_of_debt(pre_tax_cost_of_debt: float, tax_rate: float) -> float:
    """After-tax cost of debt: ``kd * (1 - tax)``."""
    return pre_tax_cost_of_debt * (1.0 - tax_rate)


def implied_cost_of_debt(
    interest_expense: Optional[float], total_debt: Optional[float]
) -> Optional[float]:
    """Approximate the pre-tax cost of debt as interest / total debt."""
    return safe_div(interest_expense, total_debt)


@dataclass(frozen=True)
class WaccResult:
    wacc: float
    cost_of_equity: float
    cost_of_debt_after_tax: float
    equity_weight: float
    debt_weight: float

    def as_dict(self) -> dict:
        return {
            "wacc": self.wacc,
            "cost_of_equity": self.cost_of_equity,
            "cost_of_debt_after_tax": self.cost_of_debt_after_tax,
            "equity_weight": self.equity_weight,
            "debt_weight": self.debt_weight,
        }


def wacc(
    equity_value: float,
    debt_value: float,
    beta: float,
    pre_tax_cost_of_debt: float,
    risk_free_rate: float = DEFAULT_RISK_FREE_RATE,
    equity_risk_premium: float = DEFAULT_EQUITY_RISK_PREMIUM,
    tax_rate: float = DEFAULT_TAX_RATE,
) -> WaccResult:
    """Weighted Average Cost of Capital using market-value weights.

    Parameters
    ----------
    equity_value, debt_value:
        Market value of equity and (book proxy of) debt.  If both are zero
        the function falls back to a 100% equity structure.
    """
    total = equity_value + debt_value
    if total <= 0:
        equity_weight, debt_weight = 1.0, 0.0
    else:
        equity_weight = equity_value / total
        debt_weight = debt_value / total

    ke = cost_of_equity(beta, risk_free_rate, equity_risk_premium)
    kd = after_tax_cost_of_debt(pre_tax_cost_of_debt, tax_rate)
    blended = equity_weight * ke + debt_weight * kd
    return WaccResult(
        wacc=blended,
        cost_of_equity=ke,
        cost_of_debt_after_tax=kd,
        equity_weight=equity_weight,
        debt_weight=debt_weight,
    )
