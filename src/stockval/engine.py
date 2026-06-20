"""Valuation orchestration.

Runs every engine against a :class:`CompanyData` snapshot given a single
set of assumptions and returns a consolidated summary.  This is the seam
the dashboard (and any future CLI/API) builds on.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Sequence

from .config import (
    DEFAULT_EQUITY_RISK_PREMIUM,
    DEFAULT_FORECAST_YEARS,
    DEFAULT_RISK_FREE_RATE,
    DEFAULT_TAX_RATE,
    DEFAULT_TERMINAL_GROWTH,
    EQUITY_RISK_PREMIUM_BY_CURRENCY,
    RISK_FREE_BY_CURRENCY,
)
from .models import CompanyData, ValuationResult
from .utils import mean
from .valuation import capm, comparables, dcf, ddm, multiples


@dataclass
class Assumptions:
    """All tunable inputs for a valuation run."""

    risk_free_rate: float = DEFAULT_RISK_FREE_RATE
    equity_risk_premium: float = DEFAULT_EQUITY_RISK_PREMIUM
    tax_rate: float = DEFAULT_TAX_RATE
    beta: float = 1.0
    growth_rate: float = 0.08
    terminal_growth: float = DEFAULT_TERMINAL_GROWTH
    forecast_years: int = DEFAULT_FORECAST_YEARS
    dividend_growth: float = 0.05
    pre_tax_cost_of_debt: float = 0.05
    target_pe: Optional[float] = None
    target_ev_ebitda: Optional[float] = None
    target_pb: Optional[float] = None


@dataclass
class ValuationSummary:
    company: CompanyData
    assumptions: Assumptions
    wacc: capm.WaccResult
    cost_of_equity: float
    results: list[ValuationResult] = field(default_factory=list)

    @property
    def current_price(self) -> Optional[float]:
        return self.company.market.price

    @property
    def fair_values(self) -> list[float]:
        return [
            r.fair_value_per_share
            for r in self.results
            if r.fair_value_per_share is not None
        ]

    @property
    def blended_fair_value(self) -> Optional[float]:
        return mean(self.fair_values)

    @property
    def blended_upside(self) -> Optional[float]:
        bfv = self.blended_fair_value
        if bfv is None or not self.current_price:
            return None
        return bfv / self.current_price - 1.0

    def recommendation(self) -> str:
        up = self.blended_upside
        if up is None:
            return "N/A"
        if up >= 0.15:
            return "BUY"
        if up <= -0.15:
            return "SELL"
        return "HOLD"


def derive_assumptions(company: CompanyData) -> Assumptions:
    """Seed assumptions from the company's own data where possible."""
    a = Assumptions()
    # Market-aware defaults keyed by the quoting currency (e.g. INR vs USD).
    ccy = (company.market.currency or "USD").upper()
    a.risk_free_rate = RISK_FREE_BY_CURRENCY.get(ccy, a.risk_free_rate)
    a.equity_risk_premium = EQUITY_RISK_PREMIUM_BY_CURRENCY.get(
        ccy, a.equity_risk_premium
    )
    if company.market.beta is not None:
        a.beta = company.market.beta
    if company.financials.tax_rate is not None:
        a.tax_rate = company.financials.tax_rate
    g = dcf.implied_growth_from_history(company)
    if g is not None:
        a.growth_rate = g
    kd = capm.implied_cost_of_debt(
        company.financials.interest_expense, company.financials.total_debt
    )
    if kd is not None and 0 < kd < 0.30:
        a.pre_tax_cost_of_debt = kd
    return a


def run_valuation(
    company: CompanyData,
    assumptions: Assumptions,
    peers: Optional[Sequence[CompanyData]] = None,
) -> ValuationSummary:
    """Run every applicable model and consolidate the results."""
    equity_value = company.market.equity_value or 0.0
    debt_value = company.financials.total_debt or 0.0

    wacc_res = capm.wacc(
        equity_value=equity_value,
        debt_value=debt_value,
        beta=assumptions.beta,
        pre_tax_cost_of_debt=assumptions.pre_tax_cost_of_debt,
        risk_free_rate=assumptions.risk_free_rate,
        equity_risk_premium=assumptions.equity_risk_premium,
        tax_rate=assumptions.tax_rate,
    )
    ke = wacc_res.cost_of_equity

    results: list[ValuationResult] = [
        dcf.fcff_dcf(
            company,
            wacc=wacc_res.wacc,
            growth_rate=assumptions.growth_rate,
            tax_rate=assumptions.tax_rate,
            terminal_growth=assumptions.terminal_growth,
            years=assumptions.forecast_years,
        ),
        dcf.fcfe_dcf(
            company,
            cost_of_equity=ke,
            growth_rate=assumptions.growth_rate,
            tax_rate=assumptions.tax_rate,
            terminal_growth=assumptions.terminal_growth,
            years=assumptions.forecast_years,
        ),
        ddm.gordon_ddm(company, cost_of_equity=ke, growth_rate=assumptions.dividend_growth),
    ]

    if company.market.dividend_per_share:
        results.append(
            ddm.multistage_ddm(
                current_dividend=company.market.dividend_per_share,
                cost_of_equity=ke,
                high_growth_rate=assumptions.dividend_growth,
                high_growth_years=assumptions.forecast_years,
                terminal_growth=assumptions.terminal_growth,
            )
        )

    # Peer-median multiples take priority; fall back to the company's own.
    target_pe = assumptions.target_pe
    target_ev_ebitda = assumptions.target_ev_ebitda
    target_pb = assumptions.target_pb
    if peers:
        bench = comparables.benchmark(list(peers))
        target_pe = target_pe or bench.median_pe
        target_ev_ebitda = target_ev_ebitda or bench.median_ev_ebitda
        target_pb = target_pb or bench.median_pb

    if target_pe:
        results.append(multiples.pe_valuation(company, target_pe))
    if target_ev_ebitda:
        results.append(multiples.ev_ebitda_valuation(company, target_ev_ebitda))
    if target_pb:
        results.append(multiples.pb_valuation(company, target_pb))

    return ValuationSummary(
        company=company,
        assumptions=assumptions,
        wacc=wacc_res,
        cost_of_equity=ke,
        results=results,
    )
