"""Tests for Indian-market / multi-currency support."""
from __future__ import annotations

import sys
import types
from dataclasses import replace

import pandas as pd
import pytest

from stockval.config import currency_symbol
from stockval.data import yahoo
from stockval.engine import derive_assumptions


def test_currency_symbol_mapping():
    assert currency_symbol("INR") == "₹"
    assert currency_symbol("USD") == "$"
    assert currency_symbol("EUR") == "€"
    assert currency_symbol("GBP") == "£"
    # Unknown codes fall back to "CODE ".
    assert currency_symbol("ZAR") == "ZAR "
    assert currency_symbol(None) == "$"


def test_derive_assumptions_inr_market(sample_company):
    inr = replace(sample_company, market=replace(sample_company.market, currency="INR"))
    a = derive_assumptions(inr)
    assert a.risk_free_rate == pytest.approx(0.068)
    assert a.equity_risk_premium == pytest.approx(0.07)


def test_derive_assumptions_usd_market(sample_company):
    a = derive_assumptions(sample_company)  # USD fixture
    assert a.risk_free_rate == pytest.approx(0.04)
    assert a.equity_risk_premium == pytest.approx(0.05)


class _FakeDomain:
    def __init__(self, symbols):
        self._symbols = symbols

    @property
    def top_companies(self):
        return pd.DataFrame({"name": list(self._symbols)}, index=self._symbols)


def test_discover_peers_filters_to_same_currency(monkeypatch, sample_company):
    target = replace(
        sample_company,
        market=replace(
            sample_company.market,
            ticker="TCS.NS",
            currency="INR",
            industry_key="information-technology-services",
            sector_key="technology",
        ),
    )

    # yfinance domain returns a mix of INR and USD symbols.
    fake = types.ModuleType("yfinance")
    fake.Industry = lambda key: _FakeDomain(["INFY.NS", "IBM", "WIPRO.NS", "ACN"])
    fake.Sector = lambda key: _FakeDomain(["HCLTECH.NS", "CTSH"])
    monkeypatch.setitem(sys.modules, "yfinance", fake)

    def fake_fetch(sym: str):
        ccy = "INR" if sym.endswith(".NS") else "USD"
        return replace(
            sample_company,
            market=replace(sample_company.market, ticker=sym, currency=ccy),
        )

    monkeypatch.setattr(yahoo, "fetch_company", fake_fetch)

    peers = yahoo.discover_peers(target, max_peers=6, same_currency_only=True)
    tickers = [p.market.ticker for p in peers]
    assert tickers and all(t.endswith(".NS") for t in tickers)
    assert "IBM" not in tickers and "ACN" not in tickers


def test_resolve_ticker_keeps_suffixed_symbol(monkeypatch):
    # A symbol that already has a suffix is returned untouched, no lookups.
    monkeypatch.setattr(yahoo, "_has_price", lambda t: pytest.fail("should not query"))
    assert yahoo.resolve_ticker("reliance.ns") == "RELIANCE.NS"


def test_resolve_ticker_appends_ns_for_indian(monkeypatch):
    # Bare symbol does not resolve directly but does with .NS.
    monkeypatch.setattr(yahoo, "_has_price", lambda t: t == "RELIANCE.NS")
    assert yahoo.resolve_ticker("RELIANCE") == "RELIANCE.NS"


def test_resolve_ticker_prefers_direct_match(monkeypatch):
    monkeypatch.setattr(yahoo, "_has_price", lambda t: t == "AAPL")
    assert yahoo.resolve_ticker("AAPL") == "AAPL"


def test_indian_curated_fallback_when_discovery_empty(monkeypatch, sample_company):
    target = replace(
        sample_company,
        market=replace(
            sample_company.market,
            ticker="TCS.NS",
            currency="INR",
            sector_key="technology",
            industry_key="information-technology-services",
        ),
    )

    # Yahoo's global lists return only US names (filtered out by currency).
    fake = types.ModuleType("yfinance")
    fake.Industry = lambda key: _FakeDomain(["IBM", "ACN"])
    fake.Sector = lambda key: _FakeDomain(["CTSH"])
    monkeypatch.setitem(sys.modules, "yfinance", fake)

    def fake_fetch(sym: str):
        ccy = "INR" if sym.endswith(".NS") else "USD"
        return replace(
            sample_company,
            market=replace(sample_company.market, ticker=sym, currency=ccy),
        )

    monkeypatch.setattr(yahoo, "fetch_company", fake_fetch)

    peers = yahoo.discover_peers(target, max_peers=4, same_currency_only=True)
    tickers = [p.market.ticker for p in peers]
    # Curated NSE technology peers (excluding the TCS target) should appear.
    assert tickers and all(t.endswith(".NS") for t in tickers)
    assert "TCS.NS" not in tickers
    assert "INFY.NS" in tickers

