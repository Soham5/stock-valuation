"""Shared offline fixtures for the valuation test-suite."""
from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from stockval.models import CompanyData, Financials, MarketData  # noqa: E402


@pytest.fixture
def sample_company() -> CompanyData:
    """A self-consistent fictitious company used across tests."""
    market = MarketData(
        ticker="TEST",
        name="Test Corp",
        currency="USD",
        price=100.0,
        shares_outstanding=1_000_000.0,
        beta=1.2,
        market_cap=100_000_000.0,
        dividend_per_share=2.0,
        sector="Technology",
        industry="Software",
    )
    financials = Financials(
        revenue=50_000_000.0,
        ebit=12_000_000.0,
        ebitda=15_000_000.0,
        net_income=8_000_000.0,
        depreciation_amortization=3_000_000.0,
        capex=4_000_000.0,
        change_in_working_capital=500_000.0,
        interest_expense=1_000_000.0,
        total_debt=20_000_000.0,
        cash_and_equivalents=5_000_000.0,
        total_equity=40_000_000.0,
        tax_rate=0.25,
        free_cash_flow=None,
        eps=8.0,
        book_value_per_share=40.0,
    )
    return CompanyData(
        market=market,
        financials=financials,
        historical_revenue=[40_000_000.0, 44_000_000.0, 47_000_000.0, 50_000_000.0],
        historical_fcf=[6_000_000.0, 6_500_000.0, 7_000_000.0, 7_500_000.0],
        historical_total_debt=[14_000_000.0, 16_000_000.0, 18_000_000.0, 20_000_000.0],
        quarterly_revenue=[
            8_000_000.0, 11_000_000.0, 10_000_000.0, 16_000_000.0,
            9_000_000.0, 12_000_000.0, 11_000_000.0, 18_000_000.0,
        ],
        quarterly_revenue_periods=[1, 2, 3, 4, 1, 2, 3, 4],
    )
