"""Domain models shared across the valuation system.

These dataclasses form the contract between the data layer (which may pull
from Yahoo Finance or be hand-built in tests) and the valuation engines.
Keeping them plain and dependency-free makes the whole core unit-testable
without any network access.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass(frozen=True)
class DataProvenance:
    """Lineage metadata for an assembled snapshot (audit trail).

    Records *where* the data came from and *when* it was retrieved so a
    valuation can be reproduced and traced — a baseline requirement for
    auditable, point-in-time-aware analysis.
    """

    source: str
    ticker: str
    retrieved_at: str  # ISO-8601 UTC timestamp
    notes: str = ""


@dataclass(frozen=True)
class MarketData:
    """Live market snapshot for a single security."""

    ticker: str
    name: str = ""
    currency: str = "USD"
    price: Optional[float] = None
    shares_outstanding: Optional[float] = None
    beta: Optional[float] = None
    market_cap: Optional[float] = None
    dividend_per_share: Optional[float] = None
    sector: str = ""
    industry: str = ""
    sector_key: str = ""
    industry_key: str = ""

    @property
    def equity_value(self) -> Optional[float]:
        """Market capitalisation, preferring an explicit value."""
        if self.market_cap is not None:
            return self.market_cap
        if self.price is not None and self.shares_outstanding is not None:
            return self.price * self.shares_outstanding
        return None


@dataclass(frozen=True)
class Financials:
    """Key figures distilled from the financial statements.

    All monetary values are expressed in the reporting currency and in
    absolute units (not millions).  ``None`` means "unavailable".
    """

    revenue: Optional[float] = None
    ebit: Optional[float] = None
    ebitda: Optional[float] = None
    net_income: Optional[float] = None
    depreciation_amortization: Optional[float] = None
    capex: Optional[float] = None
    change_in_working_capital: Optional[float] = None
    interest_expense: Optional[float] = None
    total_debt: Optional[float] = None
    cash_and_equivalents: Optional[float] = None
    total_equity: Optional[float] = None
    tax_rate: Optional[float] = None
    free_cash_flow: Optional[float] = None
    eps: Optional[float] = None
    book_value_per_share: Optional[float] = None

    @property
    def net_debt(self) -> Optional[float]:
        if self.total_debt is None and self.cash_and_equivalents is None:
            return None
        debt = self.total_debt or 0.0
        cash = self.cash_and_equivalents or 0.0
        return debt - cash


@dataclass
class CompanyData:
    """Everything the valuation engines need about one company."""

    market: MarketData
    financials: Financials
    historical_revenue: list[float] = field(default_factory=list)
    historical_fcf: list[float] = field(default_factory=list)
    historical_dividends: list[float] = field(default_factory=list)
    # Oldest-first total-debt history, used to model net borrowing in FCFE.
    historical_total_debt: list[float] = field(default_factory=list)
    # Oldest-first quarterly revenue with aligned calendar-quarter labels
    # (1-4), used for statistically sound seasonality detection.
    quarterly_revenue: list[float] = field(default_factory=list)
    quarterly_revenue_periods: list[int] = field(default_factory=list)
    # Lineage and data-quality findings attached at assembly/validation time.
    provenance: Optional[DataProvenance] = None
    quality_issues: list[Any] = field(default_factory=list)

    @property
    def ticker(self) -> str:
        return self.market.ticker


@dataclass(frozen=True)
class ValuationResult:
    """Standard output envelope for every valuation model."""

    method: str
    fair_value_per_share: Optional[float]
    enterprise_value: Optional[float] = None
    equity_value: Optional[float] = None
    assumptions: dict = field(default_factory=dict)
    detail: dict = field(default_factory=dict)

    def upside(self, current_price: Optional[float]) -> Optional[float]:
        """Fractional up/down-side vs. the current price."""
        if (
            self.fair_value_per_share is None
            or current_price is None
            or current_price == 0
        ):
            return None
        return self.fair_value_per_share / current_price - 1.0
