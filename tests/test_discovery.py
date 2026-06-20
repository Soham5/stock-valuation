"""Tests for automatic peer discovery (no network — yfinance is faked)."""
from __future__ import annotations

import sys
import types

import pandas as pd
import pytest

from stockval.data import yahoo


class _FakeDomain:
    def __init__(self, symbols):
        self._symbols = symbols

    @property
    def top_companies(self):
        return pd.DataFrame({"name": list(self._symbols)}, index=self._symbols)


def _install_fake_yfinance(monkeypatch, industry_symbols, sector_symbols):
    fake = types.ModuleType("yfinance")
    fake.Industry = lambda key: _FakeDomain(industry_symbols)
    fake.Sector = lambda key: _FakeDomain(sector_symbols)
    monkeypatch.setitem(sys.modules, "yfinance", fake)


def test_discovery_excludes_target_and_dedupes(monkeypatch, sample_company):
    from dataclasses import replace

    sample_company.market = replace(
        sample_company.market,
        ticker="AAPL",
        industry_key="consumer-electronics",
        sector_key="technology",
    )
    _install_fake_yfinance(
        monkeypatch,
        industry_symbols=["AAPL", "SONO", "AXIL"],
        sector_symbols=["NVDA", "AAPL", "MSFT"],
    )
    peers = yahoo.discover_peer_tickers(sample_company, max_peers=6)
    assert "AAPL" not in peers  # target excluded
    assert peers[:2] == ["SONO", "AXIL"]  # industry first
    assert "NVDA" in peers and "MSFT" in peers  # sector supplements


def test_discovery_respects_max_peers(monkeypatch, sample_company):
    from dataclasses import replace

    sample_company.market = replace(
        sample_company.market, ticker="X", industry_key="ind", sector_key="sec"
    )
    _install_fake_yfinance(
        monkeypatch,
        industry_symbols=["A", "B", "C", "D", "E"],
        sector_symbols=["F", "G"],
    )
    peers = yahoo.discover_peer_tickers(sample_company, max_peers=3)
    assert peers == ["A", "B", "C"]


def test_discovery_without_keys_returns_empty(monkeypatch, sample_company):
    from dataclasses import replace

    sample_company.market = replace(
        sample_company.market, industry_key="", sector_key=""
    )
    _install_fake_yfinance(monkeypatch, industry_symbols=["A"], sector_symbols=["B"])
    assert yahoo.discover_peer_tickers(sample_company) == []
