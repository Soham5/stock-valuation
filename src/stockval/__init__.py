"""Stock-valuation system.

A modular toolkit for equity valuation:

* CAPM cost of equity and WACC
* Discounted Cash Flow (FCFF and FCFE)
* Dividend Discount Models (Gordon and multi-stage)
* Relative valuation via market multiples
* Peer / comparables benchmarking
* Sensitivity and scenario analysis

The valuation core is pure and side-effect free so it can be unit tested
offline.  Live market data is fetched through an isolated adapter
(:mod:`stockval.data.yahoo`).
"""

from . import valuation  # noqa: F401

__version__ = "0.1.0"
__all__ = ["valuation", "__version__"]
