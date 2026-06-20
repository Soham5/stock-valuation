"""Relative valuation via market multiples.

Apply a benchmark multiple (peer median or a target value) to the company's
own metric to derive an implied price.

    P/E       -> implied price = EPS * target_PE
    EV/EBITDA -> implied EV = EBITDA * target_multiple -> equity -> price
    P/B       -> implied price = BVPS * target_PB
"""
from __future__ import annotations

from typing import Optional

from ..models import CompanyData, ValuationResult
from ..utils import safe_div


def pe_valuation(company: CompanyData, target_pe: float) -> ValuationResult:
    """Price implied by a target price-to-earnings multiple."""
    eps = company.financials.eps
    if eps is None:
        return ValuationResult(
            method="Multiple (P/E)",
            fair_value_per_share=None,
            assumptions={"reason": "EPS unavailable"},
        )
    fair_value = eps * target_pe
    return ValuationResult(
        method="Multiple (P/E)",
        fair_value_per_share=fair_value,
        assumptions={"target_pe": target_pe, "eps": eps},
    )


def ev_ebitda_valuation(
    company: CompanyData, target_ev_ebitda: float
) -> ValuationResult:
    """Price implied by a target EV/EBITDA multiple."""
    fin = company.financials
    shares = company.market.shares_outstanding
    if fin.ebitda is None or not shares:
        return ValuationResult(
            method="Multiple (EV/EBITDA)",
            fair_value_per_share=None,
            assumptions={"reason": "EBITDA or shares unavailable"},
        )
    enterprise_value = fin.ebitda * target_ev_ebitda
    net_debt = fin.net_debt or 0.0
    equity_value = enterprise_value - net_debt
    fair_value = equity_value / shares
    return ValuationResult(
        method="Multiple (EV/EBITDA)",
        fair_value_per_share=fair_value,
        enterprise_value=enterprise_value,
        equity_value=equity_value,
        assumptions={"target_ev_ebitda": target_ev_ebitda, "ebitda": fin.ebitda},
        detail={"net_debt": net_debt},
    )


def pb_valuation(company: CompanyData, target_pb: float) -> ValuationResult:
    """Price implied by a target price-to-book multiple."""
    bvps = company.financials.book_value_per_share
    if bvps is None:
        return ValuationResult(
            method="Multiple (P/B)",
            fair_value_per_share=None,
            assumptions={"reason": "book value per share unavailable"},
        )
    fair_value = bvps * target_pb
    return ValuationResult(
        method="Multiple (P/B)",
        fair_value_per_share=fair_value,
        assumptions={"target_pb": target_pb, "bvps": bvps},
    )


def current_pe(company: CompanyData) -> Optional[float]:
    """The company's own trailing P/E, if computable."""
    return safe_div(company.market.price, company.financials.eps)


def current_pb(company: CompanyData) -> Optional[float]:
    """The company's own price-to-book, if computable."""
    return safe_div(company.market.price, company.financials.book_value_per_share)
