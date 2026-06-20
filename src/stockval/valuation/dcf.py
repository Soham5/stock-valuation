"""Discounted Cash Flow valuation: FCFF and FCFE.

FCFF (Free Cash Flow to the Firm) is discounted at the WACC to an
enterprise value, from which net debt is removed to reach equity value.

FCFE (Free Cash Flow to Equity) is discounted at the cost of equity
directly to an equity value.

    FCFF = EBIT*(1-t) + D&A - CapEx - dWC
    FCFE = FCFF - Interest*(1-t) + Net Borrowing
"""
from __future__ import annotations

from typing import Optional, Sequence

from ..config import DEFAULT_FORECAST_YEARS, DEFAULT_TERMINAL_GROWTH
from ..models import CompanyData, ValuationResult
from ..utils import gordon_terminal_value, present_value, safe_div


def project_cash_flows(
    base_cash_flow: float,
    growth_rate: float,
    years: int,
) -> list[float]:
    """Grow ``base_cash_flow`` at a constant ``growth_rate`` for ``years``."""
    flows: list[float] = []
    cf = base_cash_flow
    for _ in range(years):
        cf = cf * (1.0 + growth_rate)
        flows.append(cf)
    return flows


def discount_cash_flows(
    cash_flows: Sequence[float],
    discount_rate: float,
    terminal_growth: float,
) -> dict:
    """Discount explicit cash flows plus a Gordon terminal value.

    Returns a dict with the present value of the explicit phase, the present
    value of the terminal value and their sum.
    """
    pv_explicit = sum(
        present_value(cf, discount_rate, t + 1) for t, cf in enumerate(cash_flows)
    )
    terminal_value = gordon_terminal_value(
        cash_flows[-1], discount_rate, terminal_growth
    )
    pv_terminal = present_value(terminal_value, discount_rate, len(cash_flows))
    return {
        "pv_explicit": pv_explicit,
        "terminal_value": terminal_value,
        "pv_terminal": pv_terminal,
        "total": pv_explicit + pv_terminal,
    }


def compute_fcff(company: CompanyData, tax_rate: float) -> Optional[float]:
    """Latest-year FCFF, preferring a reported FCF if available."""
    fin = company.financials
    if fin.free_cash_flow is not None:
        return fin.free_cash_flow
    if fin.ebit is None:
        return None
    nopat = fin.ebit * (1.0 - tax_rate)
    da = fin.depreciation_amortization or 0.0
    capex = fin.capex or 0.0
    dwc = fin.change_in_working_capital or 0.0
    # capex is stored as a positive outflow magnitude
    return nopat + da - abs(capex) - dwc


def fcff_dcf(
    company: CompanyData,
    wacc: float,
    growth_rate: float,
    tax_rate: float,
    terminal_growth: float = DEFAULT_TERMINAL_GROWTH,
    years: int = DEFAULT_FORECAST_YEARS,
) -> ValuationResult:
    """Enterprise DCF on Free Cash Flow to the Firm."""
    base_fcff = compute_fcff(company, tax_rate)
    shares = company.market.shares_outstanding
    if base_fcff is None or not shares:
        return ValuationResult(
            method="DCF (FCFF)",
            fair_value_per_share=None,
            assumptions={"reason": "insufficient data (FCFF or shares missing)"},
        )

    flows = project_cash_flows(base_fcff, growth_rate, years)
    disc = discount_cash_flows(flows, wacc, terminal_growth)
    enterprise_value = disc["total"]
    net_debt = company.financials.net_debt or 0.0
    equity_value = enterprise_value - net_debt
    fair_value = equity_value / shares

    return ValuationResult(
        method="DCF (FCFF)",
        fair_value_per_share=fair_value,
        enterprise_value=enterprise_value,
        equity_value=equity_value,
        assumptions={
            "wacc": wacc,
            "growth_rate": growth_rate,
            "terminal_growth": terminal_growth,
            "years": years,
            "tax_rate": tax_rate,
        },
        detail={
            "base_fcff": base_fcff,
            "projected_fcff": flows,
            "net_debt": net_debt,
            **disc,
        },
    )


def compute_fcfe(company: CompanyData, tax_rate: float) -> Optional[float]:
    """Latest-year FCFE derived from FCFF, interest and net borrowing.

    Net borrowing is unobservable from a single snapshot, so it is assumed
    zero (a common simplifying assumption for steady-state firms).
    """
    fcff = compute_fcff(company, tax_rate)
    if fcff is None:
        return None
    interest = company.financials.interest_expense or 0.0
    after_tax_interest = interest * (1.0 - tax_rate)
    net_borrowing = 0.0
    return fcff - after_tax_interest + net_borrowing


def fcfe_dcf(
    company: CompanyData,
    cost_of_equity: float,
    growth_rate: float,
    tax_rate: float,
    terminal_growth: float = DEFAULT_TERMINAL_GROWTH,
    years: int = DEFAULT_FORECAST_YEARS,
) -> ValuationResult:
    """Equity DCF on Free Cash Flow to Equity."""
    base_fcfe = compute_fcfe(company, tax_rate)
    shares = company.market.shares_outstanding
    if base_fcfe is None or not shares:
        return ValuationResult(
            method="DCF (FCFE)",
            fair_value_per_share=None,
            assumptions={"reason": "insufficient data (FCFE or shares missing)"},
        )

    flows = project_cash_flows(base_fcfe, growth_rate, years)
    disc = discount_cash_flows(flows, cost_of_equity, terminal_growth)
    equity_value = disc["total"]
    fair_value = equity_value / shares

    return ValuationResult(
        method="DCF (FCFE)",
        fair_value_per_share=fair_value,
        equity_value=equity_value,
        assumptions={
            "cost_of_equity": cost_of_equity,
            "growth_rate": growth_rate,
            "terminal_growth": terminal_growth,
            "years": years,
            "tax_rate": tax_rate,
        },
        detail={
            "base_fcfe": base_fcfe,
            "projected_fcfe": flows,
            **disc,
        },
    )


def implied_growth_from_history(company: CompanyData) -> Optional[float]:
    """Best-effort revenue/FCF growth estimate from history, capped sanely."""
    from ..utils import cagr  # local import to avoid cycle at module load

    g = cagr(company.historical_fcf) or cagr(company.historical_revenue)
    if g is None:
        return None
    # Keep projections grounded: cap between -20% and +25%.
    return max(-0.20, min(0.25, g))


def equity_to_share(equity_value: Optional[float], shares: Optional[float]) -> Optional[float]:
    """Convenience: per-share value from an equity value."""
    return safe_div(equity_value, shares)
