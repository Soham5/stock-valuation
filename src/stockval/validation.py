"""Data-quality validation — the "garbage-in" tripwire.

A single corrupted statement row (a sign flip, a restatement, a vendor glitch)
can silently distort every downstream valuation.  This module inspects a
:class:`~stockval.models.CompanyData` snapshot for internal inconsistencies and
out-of-range values *before* it reaches the engines, surfacing problems as
structured, severity-graded issues instead of letting them flow through
unnoticed.

Severities
----------
``ERROR``  Data is unusable or self-contradictory; treat results as unreliable.
``WARN``   Plausible but suspicious; worth an analyst's eye.
``INFO``   Notable but benign (e.g. a missing optional field).
"""
from __future__ import annotations

from dataclasses import dataclass

from .models import CompanyData, Financials, MarketData

ERROR = "ERROR"
WARN = "WARN"
INFO = "INFO"


@dataclass(frozen=True)
class DataQualityIssue:
    """A single validation finding."""

    severity: str
    field: str
    message: str

    def __str__(self) -> str:  # pragma: no cover - cosmetic
        return f"[{self.severity}] {self.field}: {self.message}"


@dataclass(frozen=True)
class DataQualityReport:
    """Collected findings for one company snapshot."""

    ticker: str
    issues: list[DataQualityIssue]

    @property
    def errors(self) -> list[DataQualityIssue]:
        return [i for i in self.issues if i.severity == ERROR]

    @property
    def warnings(self) -> list[DataQualityIssue]:
        return [i for i in self.issues if i.severity == WARN]

    @property
    def is_usable(self) -> bool:
        """True when no blocking errors were found."""
        return not self.errors

    @property
    def summary(self) -> str:
        return (
            f"{len(self.errors)} error(s), {len(self.warnings)} warning(s) "
            f"for {self.ticker}"
        )


def _check_market(mkt: MarketData, out: list[DataQualityIssue]) -> None:
    if mkt.price is not None and mkt.price <= 0:
        out.append(DataQualityIssue(ERROR, "market.price", "Price must be positive."))
    if mkt.shares_outstanding is not None and mkt.shares_outstanding <= 0:
        out.append(
            DataQualityIssue(
                ERROR, "market.shares_outstanding", "Shares outstanding must be positive."
            )
        )
    if mkt.beta is not None and not (-2.0 <= mkt.beta <= 5.0):
        out.append(
            DataQualityIssue(
                WARN, "market.beta", f"Beta {mkt.beta:.2f} is outside the plausible -2..5 range."
            )
        )
    # Cross-check reported market cap against price * shares (allow 10% drift
    # for timing/free-float differences).
    if (
        mkt.market_cap is not None
        and mkt.price is not None
        and mkt.shares_outstanding is not None
        and mkt.price > 0
        and mkt.shares_outstanding > 0
    ):
        implied = mkt.price * mkt.shares_outstanding
        if implied > 0 and abs(mkt.market_cap - implied) / implied > 0.10:
            out.append(
                DataQualityIssue(
                    WARN,
                    "market.market_cap",
                    "Reported market cap differs from price x shares by >10% "
                    f"({mkt.market_cap:,.0f} vs {implied:,.0f}).",
                )
            )
    if mkt.dividend_per_share is not None and mkt.dividend_per_share < 0:
        out.append(
            DataQualityIssue(ERROR, "market.dividend_per_share", "Dividend cannot be negative.")
        )


def _check_financials(fin: Financials, mkt: MarketData, out: list[DataQualityIssue]) -> None:
    if fin.revenue is not None and fin.revenue < 0:
        out.append(DataQualityIssue(ERROR, "financials.revenue", "Revenue is negative."))

    # EBITDA should not be below EBIT (D&A is non-negative).
    if fin.ebit is not None and fin.ebitda is not None and fin.ebitda < fin.ebit - 1e-6:
        out.append(
            DataQualityIssue(
                ERROR,
                "financials.ebitda",
                f"EBITDA ({fin.ebitda:,.0f}) is below EBIT ({fin.ebit:,.0f}); "
                "likely a sign or mapping error.",
            )
        )

    # Net income above revenue is almost always a data error.
    if (
        fin.revenue is not None
        and fin.revenue > 0
        and fin.net_income is not None
        and fin.net_income > fin.revenue
    ):
        out.append(
            DataQualityIssue(
                WARN,
                "financials.net_income",
                "Net income exceeds revenue; verify one-off items or data mapping.",
            )
        )

    if fin.tax_rate is not None and not (0.0 <= fin.tax_rate <= 0.6):
        out.append(
            DataQualityIssue(
                WARN, "financials.tax_rate", f"Effective tax rate {fin.tax_rate:.0%} is out of 0..60%."
            )
        )

    if fin.total_debt is not None and fin.total_debt < 0:
        out.append(DataQualityIssue(ERROR, "financials.total_debt", "Total debt is negative."))

    if fin.book_value_per_share is not None and fin.book_value_per_share < 0:
        out.append(
            DataQualityIssue(
                INFO,
                "financials.book_value_per_share",
                "Negative book value per share (possible accumulated deficit / buybacks).",
            )
        )

    # Depreciation is conventionally stored as a positive magnitude; a large
    # negative here usually signals a sign-convention mismatch.
    if fin.depreciation_amortization is not None and fin.depreciation_amortization < 0:
        out.append(
            DataQualityIssue(
                WARN,
                "financials.depreciation_amortization",
                "D&A is negative; expected a positive magnitude.",
            )
        )


def _check_history(company: CompanyData, out: list[DataQualityIssue]) -> None:
    for label, series in (
        ("historical_revenue", company.historical_revenue),
        ("historical_fcf", company.historical_fcf),
    ):
        if series and any(v != v for v in series):  # NaN check
            out.append(DataQualityIssue(ERROR, label, "History contains NaN values."))
    if company.historical_revenue and any(v < 0 for v in company.historical_revenue):
        out.append(
            DataQualityIssue(WARN, "historical_revenue", "History contains negative revenue.")
        )


def validate_company(company: CompanyData) -> DataQualityReport:
    """Run all checks and return a graded :class:`DataQualityReport`."""
    issues: list[DataQualityIssue] = []
    _check_market(company.market, issues)
    _check_financials(company.financials, company.market, issues)
    _check_history(company, issues)
    return DataQualityReport(ticker=company.market.ticker, issues=issues)
