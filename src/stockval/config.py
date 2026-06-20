"""Project-wide defaults and assumptions.

These are conservative, widely-used defaults.  Every consumer can override
them; they exist so the dashboard and library have sensible starting points.
"""
from __future__ import annotations

# --- Market assumptions ---------------------------------------------------
DEFAULT_RISK_FREE_RATE: float = 0.04
"""Annual risk-free rate (e.g. 10Y government bond yield)."""

DEFAULT_EQUITY_RISK_PREMIUM: float = 0.05
"""Expected market return over the risk-free rate."""

DEFAULT_TAX_RATE: float = 0.25
"""Marginal corporate tax rate used for after-tax cost of debt."""

# --- DCF assumptions ------------------------------------------------------
DEFAULT_FORECAST_YEARS: int = 5
"""Explicit forecast horizon for DCF models."""

DEFAULT_TERMINAL_GROWTH: float = 0.025
"""Perpetual growth rate after the explicit forecast (~ long-run GDP)."""

# --- Numerical guards -----------------------------------------------------
MIN_SPREAD: float = 1e-4
"""Minimum (discount rate - growth) spread to keep terminal values finite."""

CURRENCY_SYMBOL: str = "$"

# --- Market localisation ---------------------------------------------------
CURRENCY_SYMBOLS: dict[str, str] = {
    "USD": "$",
    "INR": "₹",
    "EUR": "€",
    "GBP": "£",
    "JPY": "¥",
    "HKD": "HK$",
    "CNY": "¥",
    "AUD": "A$",
    "CAD": "C$",
    "SGD": "S$",
}
"""ISO currency code -> display symbol."""

# Market-specific defaults keyed by currency (approximate, user-overridable).
RISK_FREE_BY_CURRENCY: dict[str, float] = {
    "USD": 0.04,
    "INR": 0.068,   # ~10Y Indian G-Sec
    "EUR": 0.025,
    "GBP": 0.04,
    "JPY": 0.01,
}

EQUITY_RISK_PREMIUM_BY_CURRENCY: dict[str, float] = {
    "USD": 0.05,
    "INR": 0.07,    # higher equity risk premium for India
    "EUR": 0.055,
    "GBP": 0.05,
    "JPY": 0.05,
}

# Yahoo Finance exchange suffixes tried when a bare symbol fails to resolve.
INDIA_EXCHANGE_SUFFIXES: tuple[str, ...] = (".NS", ".BO")

# Curated large-cap NSE peers per Yahoo sectorKey.  Used as a fallback for
# Indian (INR) targets because Yahoo's global industry/sector "top companies"
# lists are US-centric.  Symbols are bare; the ``.NS`` suffix is added at use.
INDIA_SECTOR_PEERS: dict[str, tuple[str, ...]] = {
    "technology": ("TCS", "INFY", "WIPRO", "HCLTECH", "TECHM", "LTIM"),
    "financial-services": (
        "HDFCBANK", "ICICIBANK", "SBIN", "KOTAKBANK", "AXISBANK", "BAJFINANCE",
    ),
    "healthcare": ("SUNPHARMA", "DRREDDY", "CIPLA", "DIVISLAB", "APOLLOHOSP"),
    "energy": ("RELIANCE", "ONGC", "IOC", "BPCL", "GAIL"),
    "consumer-cyclical": ("MARUTI", "TATAMOTORS", "TITAN", "BAJAJ-AUTO", "EICHERMOT"),
    "consumer-defensive": ("HINDUNILVR", "ITC", "NESTLEIND", "BRITANNIA", "DABUR"),
    "basic-materials": ("TATASTEEL", "JSWSTEEL", "HINDALCO", "ULTRACEMCO", "GRASIM"),
    "industrials": ("LT", "SIEMENS", "ABB", "BEL", "HAL"),
    "communication-services": ("BHARTIARTL", "IDEA", "INDUSTOWER"),
    "utilities": ("NTPC", "POWERGRID", "TATAPOWER", "ADANIGREEN"),
    "real-estate": ("DLF", "GODREJPROP", "OBEROIRLTY", "PHOENIXLTD"),
}


def currency_symbol(code: str | None) -> str:
    """Return a display symbol for an ISO currency code (falls back to code)."""
    if not code:
        return CURRENCY_SYMBOL
    return CURRENCY_SYMBOLS.get(code.upper(), f"{code.upper()} ")

