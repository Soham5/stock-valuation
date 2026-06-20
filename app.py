"""Streamlit dashboard for the stock-valuation system.

Run with:

    streamlit run app.py

It fetches live data from Yahoo Finance, lets you tune valuation
assumptions in the sidebar, and shows DCF / DDM / multiples results, a
blended fair value with a BUY/HOLD/SELL call, a sensitivity heat-map,
Bear/Base/Bull scenarios and peer comparables.
"""
from __future__ import annotations

import os
import sys

# Make the `src` layout importable without installation.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

import pandas as pd  # noqa: E402
import plotly.graph_objects as go  # noqa: E402
import streamlit as st  # noqa: E402

from stockval.config import currency_symbol  # noqa: E402
from stockval.data.yahoo import (  # noqa: E402
    DataUnavailableError,
    discover_peers,
    fetch_company,
    fetch_peers,
    resolve_ticker,
)
from stockval.engine import Assumptions, derive_assumptions, run_valuation  # noqa: E402
from stockval.valuation import ai_analyst, comparables, sensitivity  # noqa: E402

st.set_page_config(page_title="Stock Valuation System", page_icon="📈", layout="wide")


@st.cache_data(show_spinner=False, ttl=900)
def load_company(ticker: str):
    resolved = resolve_ticker(ticker)
    return fetch_company(resolved)


@st.cache_data(show_spinner=False, ttl=900)
def load_peers(tickers: tuple[str, ...]):
    return fetch_peers(list(tickers))


@st.cache_data(show_spinner=False, ttl=900)
def auto_peers(resolved_ticker: str, max_peers: int):
    company = fetch_company(resolved_ticker)
    return discover_peers(company, max_peers=max_peers)


def fmt_money(value, currency=None) -> str:
    if value is None:
        return "—"
    return f"{currency_symbol(currency)}{value:,.2f}"


def fmt_pct(value) -> str:
    return "—" if value is None else f"{value * 100:,.1f}%"


def fmt_big(value, currency=None) -> str:
    if value is None:
        return "—"
    sym = currency_symbol(currency)
    for unit, scale in (("T", 1e12), ("B", 1e9), ("M", 1e6), ("K", 1e3)):
        if abs(value) >= scale:
            return f"{sym}{value / scale:,.2f}{unit}"
    return f"{sym}{value:,.0f}"


# --------------------------------------------------------------------------
# Sidebar – inputs
# --------------------------------------------------------------------------
st.sidebar.title("📈 Stock Valuation")
ticker = st.sidebar.text_input(
    "Ticker", value="AAPL",
    help="US e.g. AAPL · India e.g. RELIANCE, TCS, INFY (auto .NS), or RELIANCE.NS / 500325.BO",
).strip().upper()
auto_discover = st.sidebar.checkbox(
    "Auto-discover peers", value=True,
    help="Find same-market peers automatically from the ticker's Yahoo industry/sector.",
)
max_peers = st.sidebar.slider("Max peers", 2, 12, 6, disabled=not auto_discover)
peers_raw = st.sidebar.text_input(
    "Peer tickers (optional override)",
    value="",
    help="Leave blank to use auto-discovered peers. Comma-separated. Bare symbols inherit the target's exchange (e.g. INFY -> INFY.NS).",
)
run = st.sidebar.button("Run valuation", type="primary", use_container_width=True)

st.title("Equity Valuation Workbench")
st.caption(
    "Live fundamentals from Yahoo Finance · DCF (FCFF/FCFE), DDM, multiples, "
    "comparables, sensitivity & scenarios."
)

if not run:
    st.info("Enter a ticker in the sidebar and click **Run valuation** to begin.")
    st.stop()

# --------------------------------------------------------------------------
# Data load
# --------------------------------------------------------------------------
try:
    with st.spinner(f"Fetching {ticker}…"):
        company = load_company(ticker)
except DataUnavailableError as exc:
    st.error(f"Could not load **{ticker}**: {exc}")
    st.stop()

resolved = company.market.ticker
if resolved != ticker:
    st.sidebar.caption(f"Resolved **{ticker}** → **{resolved}**")

# A bare manual peer inherits the target's exchange suffix (e.g. INFY -> INFY.NS).
target_suffix = "." + resolved.split(".")[-1] if "." in resolved else ""


def _normalize_peer(sym: str) -> str:
    sym = sym.strip().upper()
    if sym and target_suffix and "." not in sym:
        sym += target_suffix
    return sym


peer_tickers = tuple(
    _normalize_peer(p)
    for p in peers_raw.split(",")
    if p.strip() and _normalize_peer(p) != resolved
)
if peer_tickers:
    # Manual override always wins.
    peers = load_peers(peer_tickers)
elif auto_discover:
    with st.spinner("Discovering peers…"):
        try:
            peers = auto_peers(resolved, max_peers)
        except DataUnavailableError:
            peers = []
    if peers:
        st.sidebar.caption(
            "Auto-detected peers: " + ", ".join(p.market.ticker for p in peers)
        )
    else:
        st.sidebar.caption(
            "No same-market peers found automatically — add peers manually for comparables."
        )
else:
    peers = []

seed = derive_assumptions(company)

# --------------------------------------------------------------------------
# Sidebar – assumptions (seeded from the company's own data)
# --------------------------------------------------------------------------
st.sidebar.subheader("Assumptions")
a = Assumptions(
    risk_free_rate=st.sidebar.slider("Risk-free rate", 0.0, 0.10, float(seed.risk_free_rate), 0.0025),
    equity_risk_premium=st.sidebar.slider("Equity risk premium", 0.02, 0.10, float(seed.equity_risk_premium), 0.0025),
    tax_rate=st.sidebar.slider("Tax rate", 0.0, 0.45, float(seed.tax_rate), 0.01),
    beta=st.sidebar.slider("Beta", 0.0, 2.5, float(seed.beta), 0.05),
    growth_rate=st.sidebar.slider("FCF growth (explicit)", -0.10, 0.30, float(seed.growth_rate), 0.005),
    terminal_growth=st.sidebar.slider("Terminal growth", 0.0, 0.05, float(seed.terminal_growth), 0.0025),
    forecast_years=st.sidebar.slider("Forecast years", 3, 10, int(seed.forecast_years)),
    dividend_growth=st.sidebar.slider("Dividend growth", -0.05, 0.20, float(seed.dividend_growth), 0.005),
    pre_tax_cost_of_debt=st.sidebar.slider("Pre-tax cost of debt", 0.0, 0.15, float(seed.pre_tax_cost_of_debt), 0.0025),
)

summary = run_valuation(company, a, peers=peers)
mkt = company.market
fin = company.financials

# --------------------------------------------------------------------------
# Header metrics
# --------------------------------------------------------------------------
st.subheader(f"{mkt.name}  ·  {mkt.ticker}")
if mkt.sector or mkt.industry:
    st.caption(f"{mkt.sector} · {mkt.industry}")

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Price", fmt_money(mkt.price, mkt.currency))
c2.metric("Market cap", fmt_big(mkt.equity_value, mkt.currency))
c3.metric("WACC", fmt_pct(summary.wacc.wacc))
c4.metric("Cost of equity", fmt_pct(summary.cost_of_equity))
blended = summary.blended_fair_value
c5.metric(
    "Blended fair value",
    fmt_money(blended, mkt.currency),
    delta=fmt_pct(summary.blended_upside),
)

rec = summary.recommendation()
colors = {"BUY": "green", "HOLD": "orange", "SELL": "red", "N/A": "gray"}
st.markdown(
    f"### Recommendation: :{colors.get(rec, 'gray')}[{rec}]"
    + (f"  ·  Implied upside **{fmt_pct(summary.blended_upside)}**" if summary.blended_upside is not None else "")
)

# --------------------------------------------------------------------------
# Tabs
# --------------------------------------------------------------------------
tab_ai, tab_val, tab_sens, tab_scen, tab_peers, tab_data = st.tabs(
    ["🤖 AI Analyst", "Valuation", "Sensitivity", "Scenarios", "Comparables", "Fundamentals"]
)

with tab_ai:
    st.subheader("📊 Institutional Equity Analysis")
    st.caption("Powered by 20+ years of investment banking expertise")
    
    # Initialize AI analyst
    analyst = ai_analyst.AIAnalyst(company)
    
    # Generate comprehensive thesis
    thesis = analyst.generate_thesis(summary.blended_fair_value, mkt.price)
    
    # Executive summary with rating
    col1, col2, col3 = st.columns([2, 1, 1])
    with col1:
        st.markdown(f"### {thesis.thesis_title}")
    with col2:
        rating_color = {
            "STRONG BUY": "🟢",
            "BUY": "🟢",
            "HOLD": "🟡",
            "SELL": "🔴",
            "STRONG SELL": "🔴",
        }.get(thesis.investment_rating, "⚪")
        st.metric("Rating", f"{rating_color} {thesis.investment_rating}")
    with col3:
        st.metric("Conviction", f"{thesis.conviction_level:.0%}")
    
    st.markdown(thesis.executive_summary)
    
    # Investment thesis sections
    st.divider()
    st.markdown("### Investment Thesis")
    
    bull_col, bear_col = st.columns(2)
    with bull_col:
        st.markdown("**Bull Case** 🟢")
        st.markdown(thesis.bull_case)
    
    with bear_col:
        st.markdown("**Bear Case** 🔴")
        st.markdown(thesis.bear_case)
    
    # Catalysts and risks
    st.divider()
    st.markdown("### Catalysts & Risks")
    
    cat_col, risk_col = st.columns(2)
    with cat_col:
        st.markdown("**Key Catalysts**")
        for catalyst in thesis.key_catalysts:
            st.markdown(f"• {catalyst}")
    
    with risk_col:
        st.markdown("**Key Risks**")
        for risk in thesis.risks:
            st.markdown(f"• {risk}")
    
    # Analysis sections
    st.divider()
    st.markdown("### Detailed Analysis")
    
    analysis_col1, analysis_col2 = st.columns(2)
    
    with analysis_col1:
        st.markdown("**Valuation Assessment**")
        st.info(thesis.valuation_commentary)
        
        st.markdown("**Growth Outlook**")
        st.info(thesis.growth_outlook)
    
    with analysis_col2:
        st.markdown("**Competitive Position**")
        st.info(thesis.competitive_position)
    
    # Trend analysis
    st.divider()
    st.markdown("### Market & Trend Analysis")
    
    trend = analyst.identify_trend()
    seasonality = analyst.detect_seasonality()
    growth_data = analyst.analyze_growth_trajectory()
    
    trend_col1, trend_col2, trend_col3 = st.columns(3)
    
    with trend_col1:
        st.markdown("**Trend Profile**")
        st.metric("Type", trend.trend_type)
        st.metric("Confidence", f"{trend.confidence:.0%}")
        st.caption(trend.description)
    
    with trend_col2:
        st.markdown("**Growth Analysis**")
        if growth_data.get("status") != "insufficient_data":
            st.metric("Historical CAGR", f"{growth_data.get('historical_cagr', 0):.1%}")
            st.metric("Recent Growth", f"{growth_data.get('recent_growth_rate', 0):.1%}")
            st.metric("Momentum", growth_data.get('momentum', '—'))
            st.metric("Quality", growth_data.get('growth_quality', '—'))
        else:
            st.caption("Insufficient data for growth analysis")
    
    with trend_col3:
        st.markdown("**Seasonality**")
        if seasonality.is_seasonal:
            st.metric("Seasonal", "Yes ✓")
            st.metric("Strength", f"{seasonality.seasonality_strength:.0%}")
            if seasonality.peak_quarters:
                st.caption(f"Peak: Q{',Q'.join(map(str, seasonality.peak_quarters))}")
            if seasonality.trough_quarters:
                st.caption(f"Trough: Q{',Q'.join(map(str, seasonality.trough_quarters))}")
        else:
            st.metric("Seasonal", "No")
            st.metric("Strength", "Minimal")
    
    st.markdown("**Seasonality Details**")
    st.caption(seasonality.reasoning)
    
    # Trend drivers
    st.markdown("**Trend Drivers**")
    for driver in trend.key_drivers:
        st.markdown(f"• {driver}")
    
    # Analyst notes
    st.divider()
    st.markdown("### Analyst Commentary")
    st.markdown(thesis.analyst_notes)


    rows = []
    for r in summary.results:
        up = r.upside(mkt.price)
        rows.append(
            {
                "Method": r.method,
                "Fair value": fmt_money(r.fair_value_per_share, mkt.currency),
                "Upside": fmt_pct(up),
                "_fv": r.fair_value_per_share,
                "_up": up if up is not None else 0,
            }
        )
    df = pd.DataFrame(rows)
    left, right = st.columns([3, 2])
    with left:
        st.dataframe(
            df[["Method", "Fair value", "Upside"]],
            hide_index=True,
            use_container_width=True,
        )
    with right:
        plot_df = df.dropna(subset=["_fv"])
        if not plot_df.empty:
            fig = go.Figure(
                go.Bar(
                    x=plot_df["_fv"],
                    y=plot_df["Method"],
                    orientation="h",
                    marker_color=["#2e7d32" if u >= 0 else "#c62828" for u in plot_df["_up"]],
                )
            )
            if mkt.price:
                fig.add_vline(
                    x=mkt.price, line_dash="dash", line_color="#555",
                    annotation_text="Price", annotation_position="top",
                )
            fig.update_layout(
                title="Fair value by method", height=320,
                margin=dict(l=10, r=10, t=40, b=10),
            )
            st.plotly_chart(fig, use_container_width=True)

with tab_sens:
    st.caption("Fair value per share across WACC (rows) and terminal growth (cols).")
    wacc_axis = sensitivity.linspace(max(summary.wacc.wacc - 0.02, 0.03), summary.wacc.wacc + 0.02, 5)
    tg_axis = sensitivity.linspace(max(a.terminal_growth - 0.015, 0.0), a.terminal_growth + 0.015, 5)
    grid = sensitivity.sensitivity_grid(company, a.growth_rate, a.tax_rate, wacc_axis, tg_axis)
    if any(v is not None for row in grid["values"] for v in row):
        heat = go.Figure(
            go.Heatmap(
                z=grid["values"],
                x=[f"{g*100:.2f}%" for g in grid["terminal_growth"]],
                y=[f"{w*100:.2f}%" for w in grid["wacc"]],
                colorscale="RdYlGn",
                colorbar_title="Fair value",
                hovertemplate="WACC %{y}<br>g %{x}<br>FV %{z:.2f}<extra></extra>",
            )
        )
        heat.update_layout(
            xaxis_title="Terminal growth", yaxis_title="WACC", height=420,
            margin=dict(l=10, r=10, t=30, b=10),
        )
        st.plotly_chart(heat, use_container_width=True)
    else:
        st.warning("Not enough cash-flow data to build a sensitivity grid.")

with tab_scen:
    scenarios = sensitivity.default_scenarios(a.growth_rate, summary.wacc.wacc, a.terminal_growth)
    outcomes = sensitivity.scenario_analysis(company, scenarios, a.tax_rate, mkt.price)
    srows = [
        {"Scenario": o.name, "Fair value": fmt_money(o.fair_value_per_share, mkt.currency), "Upside": fmt_pct(o.upside)}
        for o in outcomes
    ]
    st.dataframe(pd.DataFrame(srows), hide_index=True, use_container_width=True)
    valid = [o for o in outcomes if o.fair_value_per_share is not None]
    if valid:
        fig = go.Figure(
            go.Bar(
                x=[o.name for o in valid],
                y=[o.fair_value_per_share for o in valid],
                marker_color=["#c62828", "#1565c0", "#2e7d32"][: len(valid)],
            )
        )
        if mkt.price:
            fig.add_hline(y=mkt.price, line_dash="dash", annotation_text="Price")
        fig.update_layout(title="Bear · Base · Bull", height=340, margin=dict(l=10, r=10, t=40, b=10))
        st.plotly_chart(fig, use_container_width=True)

with tab_peers:
    if peers:
        bench = comparables.benchmark([company, *peers])
        prows = [
            {
                "Ticker": r.ticker,
                "Name": r.name,
                "Price": fmt_money(r.price, mkt.currency),
                "Market cap": fmt_big(r.market_cap, mkt.currency),
                "P/E": "—" if r.pe is None else f"{r.pe:.1f}",
                "EV/EBITDA": "—" if r.ev_ebitda is None else f"{r.ev_ebitda:.1f}",
                "P/B": "—" if r.pb is None else f"{r.pb:.1f}",
            }
            for r in bench.rows
        ]
        st.dataframe(pd.DataFrame(prows), hide_index=True, use_container_width=True)
        m1, m2, m3 = st.columns(3)
        m1.metric("Peer median P/E", "—" if bench.median_pe is None else f"{bench.median_pe:.1f}")
        m2.metric("Peer median EV/EBITDA", "—" if bench.median_ev_ebitda is None else f"{bench.median_ev_ebitda:.1f}")
        m3.metric("Peer median P/B", "—" if bench.median_pb is None else f"{bench.median_pb:.1f}")
    else:
        st.info("No peers available. Enable auto-discovery or add peer tickers in the sidebar.")

with tab_data:
    fundamentals = {
        "Revenue": fmt_big(fin.revenue, mkt.currency),
        "EBIT": fmt_big(fin.ebit, mkt.currency),
        "EBITDA": fmt_big(fin.ebitda, mkt.currency),
        "Net income": fmt_big(fin.net_income, mkt.currency),
        "Free cash flow": fmt_big(fin.free_cash_flow, mkt.currency),
        "Total debt": fmt_big(fin.total_debt, mkt.currency),
        "Cash": fmt_big(fin.cash_and_equivalents, mkt.currency),
        "Net debt": fmt_big(fin.net_debt, mkt.currency),
        "Shares outstanding": fmt_big(mkt.shares_outstanding, ""),
        "EPS (TTM)": fmt_money(fin.eps, mkt.currency),
        "Book value / share": fmt_money(fin.book_value_per_share, mkt.currency),
        "Dividend / share": fmt_money(mkt.dividend_per_share, mkt.currency),
        "Beta": "—" if mkt.beta is None else f"{mkt.beta:.2f}",
        "Effective tax rate": fmt_pct(fin.tax_rate),
    }
    st.dataframe(
        pd.DataFrame(fundamentals.items(), columns=["Metric", "Value"]),
        hide_index=True,
        use_container_width=True,
    )

st.caption(
    "⚠️ Educational tool. Outputs depend on assumptions and third-party data; "
    "not investment advice."
)
