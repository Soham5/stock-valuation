"""Peer comparables / benchmarking.

Build a tidy table of valuation multiples for a target plus its peers and
derive peer-median multiples that feed the relative-valuation engine.
"""
from __future__ import annotations

from dataclasses import dataclass
from statistics import median
from typing import Optional, Sequence

from ..models import CompanyData
from ..utils import safe_div


@dataclass(frozen=True)
class PeerMetrics:
    ticker: str
    name: str
    price: Optional[float]
    market_cap: Optional[float]
    pe: Optional[float]
    ev_ebitda: Optional[float]
    pb: Optional[float]


def _ev(company: CompanyData) -> Optional[float]:
    equity = company.market.equity_value
    net_debt = company.financials.net_debt
    if equity is None:
        return None
    return equity + (net_debt or 0.0)


def peer_metrics(company: CompanyData) -> PeerMetrics:
    """Extract comparison multiples for a single company."""
    fin = company.financials
    mkt = company.market
    ev = _ev(company)
    return PeerMetrics(
        ticker=mkt.ticker,
        name=mkt.name,
        price=mkt.price,
        market_cap=mkt.equity_value,
        pe=safe_div(mkt.price, fin.eps),
        ev_ebitda=safe_div(ev, fin.ebitda),
        pb=safe_div(mkt.price, fin.book_value_per_share),
    )


@dataclass(frozen=True)
class PeerBenchmark:
    rows: list[PeerMetrics]
    median_pe: Optional[float]
    median_ev_ebitda: Optional[float]
    median_pb: Optional[float]


def _median(values: Sequence[Optional[float]]) -> Optional[float]:
    clean = [v for v in values if v is not None and v > 0]
    if not clean:
        return None
    return median(clean)


def benchmark(peers: Sequence[CompanyData]) -> PeerBenchmark:
    """Compute per-peer metrics and peer-median multiples."""
    rows = [peer_metrics(p) for p in peers]
    return PeerBenchmark(
        rows=rows,
        median_pe=_median([r.pe for r in rows]),
        median_ev_ebitda=_median([r.ev_ebitda for r in rows]),
        median_pb=_median([r.pb for r in rows]),
    )
