"""Yahoo Finance adapter.

Translates the raw :mod:`yfinance` payloads into the system's domain models
(:class:`stockval.models.CompanyData`).  All Yahoo-specific quirks (field
names, statement orientation, sign conventions) are absorbed here so the
rest of the codebase never imports yfinance.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from ..config import INDIA_EXCHANGE_SUFFIXES, INDIA_SECTOR_PEERS
from ..logging_config import get_logger
from ..models import CompanyData, DataProvenance, Financials, MarketData
from ..validation import validate_company

_log = get_logger("data.yahoo")


class DataUnavailableError(RuntimeError):
    """Raised when a ticker cannot be resolved or has no usable data."""


def _safe_get(mapping, key, default=None):
    try:
        value = mapping.get(key, default)
    except AttributeError:
        return default
    if value is None:
        return default
    return value


def _row(stmt, *candidates) -> Optional[float]:
    """Return the most recent value for the first matching statement row.

    yfinance statements are DataFrames with line items as the index and
    period-end dates as columns (most recent first).
    """
    if stmt is None or getattr(stmt, "empty", True):
        return None
    for name in candidates:
        if name in stmt.index:
            series = stmt.loc[name].dropna()
            if not series.empty:
                try:
                    return float(series.iloc[0])
                except (TypeError, ValueError):
                    continue
    return None


def _history(stmt, *candidates) -> list[float]:
    """Oldest-first history for the first matching statement row."""
    if stmt is None or getattr(stmt, "empty", True):
        return []
    for name in candidates:
        if name in stmt.index:
            series = stmt.loc[name].dropna()
            if not series.empty:
                # Columns are most-recent-first; reverse to oldest-first.
                return [float(v) for v in reversed(series.tolist())]
    return []


def _quarterly_history(stmt, *candidates) -> tuple[list[float], list[int]]:
    """Oldest-first quarterly values with aligned calendar-quarter labels.

    Returns ``(values, quarters)`` where ``quarters`` holds the calendar
    quarter (1-4) derived from each column's period-end date.  Used for
    statistically sound seasonality detection.
    """
    if stmt is None or getattr(stmt, "empty", True):
        return [], []
    for name in candidates:
        if name in stmt.index:
            series = stmt.loc[name].dropna()
            if series.empty:
                continue
            values: list[float] = []
            quarters: list[int] = []
            # Columns are most-recent-first; reverse to oldest-first.
            for period, value in reversed(list(series.items())):
                try:
                    values.append(float(value))
                except (TypeError, ValueError):
                    continue
                month = getattr(period, "month", None)
                quarters.append((month - 1) // 3 + 1 if month else len(quarters) % 4 + 1)
            return values, quarters
    return [], []


def resolve_ticker(ticker: str) -> str:
    """Normalise a user-entered symbol, auto-resolving Indian listings.

    A bare symbol (no exchange suffix) that does not resolve on its own is
    retried on the Indian exchanges (``.NS`` then ``.BO``).  Symbols that
    already contain a suffix are returned untouched.
    """
    raw = (ticker or "").strip().upper()
    if not raw:
        raise DataUnavailableError("No ticker provided.")
    if "." in raw or _has_price(raw):
        return raw
    for suffix in INDIA_EXCHANGE_SUFFIXES:
        candidate = f"{raw}{suffix}"
        if _has_price(candidate):
            return candidate
    # Nothing resolved; return the original so callers raise a clear error.
    return raw


def _has_price(ticker: str) -> bool:
    """Best-effort check that a Yahoo symbol returns a tradable price."""
    try:
        import yfinance as yf
    except ImportError:  # pragma: no cover - environment dependent
        return False
    try:
        info = yf.Ticker(ticker).get_info()
    except (ValueError, KeyError, ConnectionError, TimeoutError) as exc:
        _log.debug("Price probe failed for %s: %s", ticker, exc)
        return False
    except Exception as exc:  # noqa: BLE001 - yfinance raises many ad-hoc errors
        _log.warning("Unexpected error probing price for %s: %s", ticker, exc)
        return False
    if not info:
        return False
    return bool(info.get("currentPrice") or info.get("regularMarketPrice"))


def fetch_company(ticker: str) -> CompanyData:
    """Fetch and assemble :class:`CompanyData` for ``ticker`` from Yahoo.

    Raises
    ------
    DataUnavailableError
        If yfinance is not installed or the ticker has no data.
    """
    try:
        import yfinance as yf
    except ImportError as exc:  # pragma: no cover - environment dependent
        raise DataUnavailableError(
            "yfinance is not installed. Run: pip install yfinance"
        ) from exc

    ticker = (ticker or "").strip().upper()
    tk = yf.Ticker(ticker)
    info = {}
    try:
        info = tk.get_info()
    except Exception as exc:  # noqa: BLE001 - yfinance raises many ad-hoc errors
        _log.warning("get_info failed for %s, falling back to .info: %s", ticker, exc)
        info = getattr(tk, "info", {}) or {}

    if not info:
        raise DataUnavailableError(f"No data returned for ticker '{ticker}'.")

    income = _statement(tk, "income_stmt", "financials")
    balance = _statement(tk, "balance_sheet")
    cashflow = _statement(tk, "cashflow", "cash_flow")
    quarterly_income = _statement(tk, "quarterly_income_stmt", "quarterly_financials")

    price = _safe_get(info, "currentPrice") or _safe_get(info, "regularMarketPrice")
    shares = _safe_get(info, "sharesOutstanding")

    market = MarketData(
        ticker=ticker.upper(),
        name=_safe_get(info, "shortName", ticker.upper()),
        currency=_safe_get(info, "currency", "USD"),
        price=price,
        shares_outstanding=shares,
        beta=_safe_get(info, "beta"),
        market_cap=_safe_get(info, "marketCap"),
        dividend_per_share=_safe_get(info, "dividendRate"),
        sector=_safe_get(info, "sector", ""),
        industry=_safe_get(info, "industry", ""),
        sector_key=_safe_get(info, "sectorKey", ""),
        industry_key=_safe_get(info, "industryKey", ""),
    )

    ebit = _row(income, "EBIT", "Ebit", "Operating Income")
    ebitda = _row(income, "EBITDA", "Ebitda", "Normalized EBITDA")
    da = _row(cashflow, "Depreciation And Amortization", "Depreciation Amortization Depletion", "Depreciation")
    capex = _row(cashflow, "Capital Expenditure", "Capital Expenditures")
    fcf = _row(cashflow, "Free Cash Flow")
    interest = _row(income, "Interest Expense", "Interest Expense Non Operating")
    total_debt = _row(balance, "Total Debt") or _row(balance, "Long Term Debt")
    cash = _row(balance, "Cash And Cash Equivalents", "Cash Cash Equivalents And Short Term Investments")
    equity = _row(balance, "Stockholders Equity", "Total Stockholder Equity", "Common Stock Equity")

    eps = _safe_get(info, "trailingEps")
    book_value_ps = _safe_get(info, "bookValue")

    financials = Financials(
        revenue=_row(income, "Total Revenue", "Revenue"),
        ebit=ebit,
        ebitda=ebitda if ebitda is not None else _derive_ebitda(ebit, da),
        net_income=_row(income, "Net Income", "Net Income Common Stockholders"),
        depreciation_amortization=da,
        capex=capex,
        change_in_working_capital=_row(cashflow, "Change In Working Capital"),
        interest_expense=interest,
        total_debt=total_debt,
        cash_and_equivalents=cash,
        total_equity=equity,
        tax_rate=_effective_tax_rate(income),
        free_cash_flow=fcf,
        eps=eps,
        book_value_per_share=book_value_ps,
    )

    quarterly_rev, quarterly_periods = _quarterly_history(
        quarterly_income, "Total Revenue", "Revenue"
    )

    company = CompanyData(
        market=market,
        financials=financials,
        historical_revenue=_history(income, "Total Revenue", "Revenue"),
        historical_fcf=_history(cashflow, "Free Cash Flow"),
        historical_dividends=[],
        historical_total_debt=_history(balance, "Total Debt", "Long Term Debt"),
        quarterly_revenue=quarterly_rev,
        quarterly_revenue_periods=quarterly_periods,
        provenance=DataProvenance(
            source="yahoo-finance/yfinance",
            ticker=ticker.upper(),
            retrieved_at=datetime.now(timezone.utc).isoformat(),
            notes="Assembled from yfinance info + annual/quarterly statements.",
        ),
    )

    # Data-quality tripwire: attach findings and log any blocking errors so
    # corrupted inputs never silently flow into a valuation.
    report = validate_company(company)
    company.quality_issues = report.issues
    if report.errors:
        _log.warning(
            "Data-quality issues for %s: %s",
            ticker.upper(),
            "; ".join(str(i) for i in report.errors),
        )
    _log.info(
        "Fetched %s (%s); %s",
        ticker.upper(),
        market.currency,
        report.summary,
    )
    return company


def _statement(tk, *attrs):
    """Return the first available statement attribute, or ``None``."""
    for attr in attrs:
        try:
            stmt = getattr(tk, attr)
        except Exception as exc:  # noqa: BLE001 - yfinance attributes are fragile
            _log.debug("Statement '%s' unavailable: %s", attr, exc)
            continue
        if stmt is not None and not getattr(stmt, "empty", True):
            return stmt
    return None


def _derive_ebitda(ebit: Optional[float], da: Optional[float]) -> Optional[float]:
    if ebit is None:
        return None
    return ebit + abs(da) if da is not None else ebit


def _effective_tax_rate(income) -> Optional[float]:
    """Effective tax rate = tax provision / pre-tax income (bounded 0-50%)."""
    pretax = _row(income, "Pretax Income", "Income Before Tax")
    tax = _row(income, "Tax Provision", "Income Tax Expense")
    if pretax in (None, 0) or tax is None:
        return None
    rate = tax / pretax
    if rate < 0 or rate > 0.5:
        return None
    return rate


def fetch_peers(tickers: list[str]) -> list[CompanyData]:
    """Fetch several companies, skipping any that fail to resolve."""
    companies: list[CompanyData] = []
    for t in tickers:
        try:
            companies.append(fetch_company(t))
        except DataUnavailableError:
            continue
    return companies


def discover_peer_tickers(company: CompanyData, max_peers: int = 6) -> list[str]:
    """Find peer ticker symbols for ``company`` from its Yahoo industry/sector.

    Strategy: take the top companies in the same *industry* (closest match)
    and supplement with the broader *sector* if more are needed.  The target
    itself is always excluded.  Returns at most ``max_peers`` symbols.
    """
    try:
        import yfinance as yf
    except ImportError as exc:  # pragma: no cover - environment dependent
        raise DataUnavailableError(
            "yfinance is not installed. Run: pip install yfinance"
        ) from exc

    target = company.market.ticker.upper()
    found: list[str] = []

    def _collect(domain) -> None:
        try:
            table = domain.top_companies
        except Exception as exc:  # noqa: BLE001 - yfinance domain calls are fragile
            _log.debug("Peer discovery via %r failed: %s", domain, exc)
            return
        if table is None or getattr(table, "empty", True):
            return
        for symbol in table.index.tolist():
            sym = str(symbol).upper()
            if sym and sym != target and sym not in found:
                found.append(sym)

    if company.market.industry_key:
        _collect(yf.Industry(company.market.industry_key))
    if len(found) < max_peers and company.market.sector_key:
        _collect(yf.Sector(company.market.sector_key))

    return found[:max_peers]


def discover_peers(
    company: CompanyData,
    max_peers: int = 6,
    same_currency_only: bool = True,
) -> list[CompanyData]:
    """Discover and fetch peer companies for ``company`` automatically.

    When ``same_currency_only`` is set (the default) only peers quoted in the
    same currency as the target are kept, so an Indian (INR) stock is compared
    against Indian peers rather than US ones.  A wider candidate pool is
    scanned to compensate for peers dropped by the filter.

    For Indian targets, where Yahoo's global industry lists rarely contain
    local names, a curated NSE peer seed (by sector) is used as a fallback.
    """
    pool_size = max_peers * 4 if same_currency_only else max_peers
    tickers = discover_peer_tickers(company, max_peers=pool_size)
    candidates = fetch_peers(tickers)

    target_ccy = (company.market.currency or "").upper()
    if same_currency_only:
        candidates = [
            c for c in candidates
            if (c.market.currency or "").upper() == target_ccy
        ]

    # Indian fallback: top up from curated NSE peers when discovery is thin.
    if len(candidates) < max_peers and _is_indian(company, target_ccy):
        candidates = _supplement_indian_peers(company, candidates, max_peers)
        if same_currency_only:
            candidates = [
                c for c in candidates
                if (c.market.currency or "").upper() == target_ccy
            ]

    return candidates[:max_peers]


def _is_indian(company: CompanyData, currency: str) -> bool:
    ticker = company.market.ticker.upper()
    return currency == "INR" or ticker.endswith((".NS", ".BO"))


def _supplement_indian_peers(
    company: CompanyData,
    existing: list[CompanyData],
    max_peers: int,
) -> list[CompanyData]:
    """Add curated NSE peers (same sector) not already present."""
    seed = INDIA_SECTOR_PEERS.get(company.market.sector_key, ())
    if not seed:
        return existing

    target = company.market.ticker.upper()
    have = {c.market.ticker.upper() for c in existing}
    have.add(target)
    base_target = target.split(".")[0]

    extra_tickers: list[str] = []
    for sym in seed:
        if sym == base_target:
            continue
        candidate = f"{sym}.NS"
        if candidate.upper() not in have:
            extra_tickers.append(candidate)
        if len(existing) + len(extra_tickers) >= max_peers:
            break

    return existing + fetch_peers(extra_tickers)


