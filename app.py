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
from stockval.valuation import monte_carlo  # noqa: E402

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

# Data-quality tripwire: warn before any number is trusted.
dq = getattr(summary, "data_quality", None)
if dq is not None and dq.issues:
    icon = "🔴" if dq.errors else "🟠"
    with st.expander(f"{icon} Data quality — {dq.summary}", expanded=bool(dq.errors)):
        for issue in dq.issues:
            line = f"**{issue.severity}** · `{issue.field}` — {issue.message}"
            if issue.severity == "ERROR":
                st.error(line)
            elif issue.severity == "WARN":
                st.warning(line)
            else:
                st.info(line)
        if company.provenance is not None:
            st.caption(
                f"Source: {company.provenance.source} · "
                f"retrieved {company.provenance.retrieved_at}"
            )

# --------------------------------------------------------------------------
# Tabs
# --------------------------------------------------------------------------
tab_analysis, tab_val, tab_sens, tab_scen, tab_mc, tab_peers, tab_data = st.tabs(
    ["Analysis", "Valuation", "Sensitivity", "Scenarios", "Monte Carlo", "Peer Comparison", "Fundamentals"]
)

with tab_analysis:
    # Build the full analytical picture once.
    analyst = ai_analyst.AIAnalyst(company)
    thesis = analyst.generate_thesis(summary.blended_fair_value, mkt.price)
    trend = analyst.identify_trend()
    seasonality = analyst.detect_seasonality()
    growth_data = analyst.analyze_growth_trajectory()

    rating_color = {
        "STRONG BUY": "🟢",
        "BUY": "🟢",
        "HOLD": "🟡",
        "SELL": "🔴",
        "STRONG SELL": "🔴",
    }.get(thesis.investment_rating, "⚪")
    rating_text_color = {
        "STRONG BUY": "green",
        "BUY": "green",
        "HOLD": "orange",
        "SELL": "red",
        "STRONG SELL": "red",
    }.get(thesis.investment_rating, "gray")

    # ----- Report header -----------------------------------------------
    st.markdown(f"## Equity Research Report — {mkt.name} ({mkt.ticker})")
    if mkt.sector or mkt.industry:
        st.caption(f"{mkt.sector} · {mkt.industry}  ·  Institutional analysis")
    st.markdown(f"#### {thesis.thesis_title}")

    h1, h2, h3, h4 = st.columns(4)
    with h1:
        st.caption("Rating")
        st.markdown(
            f"### {rating_color} :{rating_text_color}[{thesis.investment_rating}]"
        )
    h2.metric("Conviction", f"{thesis.conviction_level:.0%}")
    h3.metric(
        "Price target (12m)",
        fmt_money(summary.blended_fair_value, mkt.currency),
        delta=fmt_pct(summary.blended_upside),
    )
    h4.metric("Current price", fmt_money(mkt.price, mkt.currency))

    # ----- 1. Executive summary ----------------------------------------
    st.divider()
    st.markdown("### 1. Executive Summary")
    st.markdown(thesis.executive_summary)

    # ----- 2. Valuation snapshot ---------------------------------------
    st.divider()
    st.markdown("### 2. Valuation Snapshot")
    snap_rows = [
        {
            "Method": r.method,
            "Fair value": fmt_money(r.fair_value_per_share, mkt.currency),
            "Upside / (Downside)": fmt_pct(r.upside(mkt.price)),
        }
        for r in summary.results
    ]
    snap_rows.append(
        {
            "Method": "Blended fair value",
            "Fair value": fmt_money(summary.blended_fair_value, mkt.currency),
            "Upside / (Downside)": fmt_pct(summary.blended_upside),
        }
    )
    st.dataframe(pd.DataFrame(snap_rows), hide_index=True, use_container_width=True)
    st.markdown(f"**Valuation view —** {thesis.valuation_commentary}")

    # ----- 3. Investment thesis ----------------------------------------
    st.divider()
    st.markdown("### 3. Investment Thesis")
    bull_col, bear_col = st.columns(2)
    with bull_col:
        st.success("**Bull Case** 🟢")
        st.markdown(thesis.bull_case)
    with bear_col:
        st.error("**Bear Case** 🔴")
        st.markdown(thesis.bear_case)

    # ----- 4. Catalysts & risks ----------------------------------------
    st.divider()
    st.markdown("### 4. Catalysts & Risks")
    cat_col, risk_col = st.columns(2)
    with cat_col:
        st.markdown("**Key Catalysts**")
        for catalyst in thesis.key_catalysts:
            st.markdown(f"- {catalyst}")
    with risk_col:
        st.markdown("**Key Risks**")
        for risk in thesis.risks:
            st.markdown(f"- {risk}")

    # ----- 5. Growth & trend analysis ----------------------------------
    st.divider()
    st.markdown("### 5. Growth & Market Trend Analysis")
    g1, g2, g3 = st.columns(3)
    with g1:
        st.markdown("**Trend Profile**")
        st.metric("Type", trend.trend_type)
        st.metric("Confidence", f"{trend.confidence:.0%}")
        st.caption(trend.description)
    with g2:
        st.markdown("**Growth Trajectory**")
        if growth_data.get("status") != "insufficient_data":
            st.metric("Historical CAGR", f"{growth_data.get('historical_cagr', 0):.1%}")
            st.metric("Recent Growth", f"{growth_data.get('recent_growth_rate', 0):.1%}")
            st.metric("Momentum", str(growth_data.get("momentum", "—")).title())
            st.caption(f"Quality: {growth_data.get('growth_quality', '—')}")
        else:
            st.caption("Insufficient history for growth analysis.")
    with g3:
        st.markdown("**Seasonality**")
        if seasonality.is_seasonal:
            st.metric("Seasonal", "Yes")
            st.metric("Strength", f"{seasonality.seasonality_strength:.0%}")
            if seasonality.peak_quarters:
                st.caption("Peak: Q" + ", Q".join(map(str, seasonality.peak_quarters)))
            if seasonality.trough_quarters:
                st.caption("Trough: Q" + ", Q".join(map(str, seasonality.trough_quarters)))
        else:
            st.metric("Seasonal", "No")
            st.metric("Strength", "Minimal")

    st.markdown("**Growth outlook —** " + thesis.growth_outlook)
    st.caption(seasonality.reasoning)
    if trend.key_drivers:
        st.markdown("**Trend drivers:** " + " · ".join(trend.key_drivers))

    # ----- 6. Competitive position -------------------------------------
    st.divider()
    st.markdown("### 6. Competitive Position")
    st.markdown(thesis.competitive_position)

    # ----- 7. SWOT analysis --------------------------------------------
    st.divider()
    st.markdown("### 7. SWOT Analysis")
    swot = analyst.generate_swot()
    sw1, sw2 = st.columns(2)
    with sw1:
        st.success("**Strengths** 💪")
        for item in swot.strengths:
            st.markdown(f"- {item}")
        st.warning("**Weaknesses** ⚠️")
        for item in swot.weaknesses:
            st.markdown(f"- {item}")
    with sw2:
        st.info("**Opportunities** 🚀")
        for item in swot.opportunities:
            st.markdown(f"- {item}")
        st.error("**Threats** 🛡️")
        for item in swot.threats:
            st.markdown(f"- {item}")

    # ----- 8. Analyst commentary ---------------------------------------
    st.divider()
    st.markdown("### 8. Analyst Commentary")
    st.markdown(thesis.analyst_notes)

with tab_val:
    # Headline valuation metrics.
    v1, v2, v3, v4 = st.columns(4)
    v1.metric("Blended fair value", fmt_money(summary.blended_fair_value, mkt.currency),
              delta=fmt_pct(summary.blended_upside))
    v2.metric("Current price", fmt_money(mkt.price, mkt.currency))
    v3.metric("WACC", fmt_pct(summary.wacc.wacc))
    v4.metric("Cost of equity", fmt_pct(summary.cost_of_equity))

    rows = []
    for r in summary.results:
        up = r.upside(mkt.price)
        rows.append(
            {
                "Method": r.method,
                "Fair value": fmt_money(r.fair_value_per_share, mkt.currency),
                "Upside": fmt_pct(up),
                "Enterprise value": fmt_big(r.enterprise_value, mkt.currency),
                "Equity value": fmt_big(r.equity_value, mkt.currency),
                "Signal": (
                    "—" if up is None
                    else "BUY" if up >= 0.15
                    else "SELL" if up <= -0.15
                    else "HOLD"
                ),
                "_fv": r.fair_value_per_share,
                "_up": up if up is not None else 0,
            }
        )
    df = pd.DataFrame(rows)
    left, right = st.columns([3, 2])
    with left:
        st.dataframe(
            df[["Method", "Fair value", "Upside", "Enterprise value", "Equity value", "Signal"]],
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

    # Dispersion stats across the methods (the valuation "football field").
    fvs = summary.fair_values
    if fvs:
        st.markdown("#### Fair-value range across methods")
        lo, hi = min(fvs), max(fvs)
        med = sorted(fvs)[len(fvs) // 2]
        spread = (hi / lo - 1.0) if lo else None
        s1, s2, s3, s4 = st.columns(4)
        s1.metric("Low", fmt_money(lo, mkt.currency),
                  delta=fmt_pct((lo / mkt.price - 1) if mkt.price else None))
        s2.metric("Median", fmt_money(med, mkt.currency),
                  delta=fmt_pct((med / mkt.price - 1) if mkt.price else None))
        s3.metric("High", fmt_money(hi, mkt.currency),
                  delta=fmt_pct((hi / mkt.price - 1) if mkt.price else None))
        s4.metric("Low–High spread", fmt_pct(spread))
        st.caption(
            f"Methods used: {len(fvs)} · Recommendation: **{summary.recommendation()}** "
            f"based on the blended {fmt_pct(summary.blended_upside)} implied upside."
        )

with tab_sens:
    st.caption("Fair value per share across WACC (rows) and terminal growth (cols).")
    wacc_axis = sensitivity.linspace(max(summary.wacc.wacc - 0.02, 0.03), summary.wacc.wacc + 0.02, 5)
    tg_axis = sensitivity.linspace(max(a.terminal_growth - 0.015, 0.0), a.terminal_growth + 0.015, 5)
    grid = sensitivity.sensitivity_grid(company, a.growth_rate, a.tax_rate, wacc_axis, tg_axis)
    flat = [v for row in grid["values"] for v in row if v is not None]
    if flat:
        # Headline read-outs for the grid.
        base = sensitivity.fcff_dcf(
            company, wacc=summary.wacc.wacc, growth_rate=a.growth_rate,
            tax_rate=a.tax_rate, terminal_growth=a.terminal_growth,
        ).fair_value_per_share if hasattr(sensitivity, "fcff_dcf") else None
        lo, hi = min(flat), max(flat)
        d1, d2, d3, d4 = st.columns(4)
        d1.metric("Base case FV", fmt_money(base, mkt.currency) if base else "—",
                  delta=fmt_pct((base / mkt.price - 1) if base and mkt.price else None))
        d2.metric("Grid low", fmt_money(lo, mkt.currency))
        d3.metric("Grid high", fmt_money(hi, mkt.currency))
        d4.metric("Range width", fmt_pct((hi / lo - 1.0) if lo else None))

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

        # Numeric grid for precise read-off.
        st.markdown("#### Sensitivity grid (fair value per share)")
        sym = currency_symbol(mkt.currency)
        grid_df = pd.DataFrame(
            [
                [f"{sym}{v:,.2f}" if v is not None else "—" for v in row]
                for row in grid["values"]
            ],
            index=[f"WACC {w*100:.2f}%" for w in grid["wacc"]],
            columns=[f"g {g*100:.2f}%" for g in grid["terminal_growth"]],
        )
        st.dataframe(grid_df, use_container_width=True)
        st.caption(
            "Each cell re-runs the FCFF DCF at the given WACC × terminal-growth "
            "pair, holding the explicit growth and tax assumptions constant."
        )
    else:
        st.warning("Not enough cash-flow data to build a sensitivity grid.")

with tab_scen:
    scenarios = sensitivity.default_scenarios(a.growth_rate, summary.wacc.wacc, a.terminal_growth)
    outcomes = sensitivity.scenario_analysis(company, scenarios, a.tax_rate, mkt.price)
    # Pair each outcome with the assumptions that produced it.
    by_name = {sc.name: sc for sc in scenarios}
    srows = []
    for o in outcomes:
        sc = by_name.get(o.name)
        srows.append(
            {
                "Scenario": o.name,
                "FCF growth": fmt_pct(sc.growth_rate) if sc else "—",
                "WACC": fmt_pct(sc.wacc) if sc else "—",
                "Terminal growth": fmt_pct(sc.terminal_growth) if sc else "—",
                "Fair value": fmt_money(o.fair_value_per_share, mkt.currency),
                "Upside": fmt_pct(o.upside),
            }
        )
    st.dataframe(pd.DataFrame(srows), hide_index=True, use_container_width=True)

    valid = [o for o in outcomes if o.fair_value_per_share is not None]
    if valid:
        # Summary read-outs across the three cases.
        fvs = [o.fair_value_per_share for o in valid]
        bear = next((o for o in valid if o.name == "Bear"), None)
        base = next((o for o in valid if o.name == "Base"), None)
        bull = next((o for o in valid if o.name == "Bull"), None)
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Bear", fmt_money(bear.fair_value_per_share, mkt.currency) if bear else "—",
                  delta=fmt_pct(bear.upside) if bear else None)
        c2.metric("Base", fmt_money(base.fair_value_per_share, mkt.currency) if base else "—",
                  delta=fmt_pct(base.upside) if base else None)
        c3.metric("Bull", fmt_money(bull.fair_value_per_share, mkt.currency) if bull else "—",
                  delta=fmt_pct(bull.upside) if bull else None)
        c4.metric("Bear–Bull spread", fmt_pct((max(fvs) / min(fvs) - 1.0) if min(fvs) else None))

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
        st.caption(
            "Scenarios flex FCF growth, WACC and terminal growth together: the Bear "
            "case applies a higher discount rate and lower growth, the Bull case the reverse."
        )

with tab_mc:
    st.caption(
        "Probabilistic FCFF DCF: the fair value is re-computed across thousands "
        "of draws from triangular distributions over growth, WACC and terminal "
        "growth, yielding a distribution rather than a single point estimate."
    )
    mc1, mc2, mc3 = st.columns(3)
    growth_spread = mc1.slider("Growth uncertainty (±)", 0.05, 0.75, 0.40, 0.05)
    wacc_spread = mc2.slider("WACC uncertainty (±)", 0.05, 0.40, 0.20, 0.05)
    iterations = mc3.select_slider("Iterations", options=[1000, 2500, 5000, 10000], value=5000)

    mc_res = monte_carlo.monte_carlo_dcf(
        company,
        tax_rate=a.tax_rate,
        growth=monte_carlo.symmetric_band(a.growth_rate, growth_spread),
        wacc=monte_carlo.symmetric_band(summary.wacc.wacc, wacc_spread),
        terminal_growth=monte_carlo.Triangular(
            max(a.terminal_growth - 0.01, 0.0), a.terminal_growth, a.terminal_growth + 0.01
        ),
        years=a.forecast_years,
        iterations=int(iterations),
        fade_to_terminal=True,
    )

    if mc_res.samples == 0:
        st.warning("Insufficient cash-flow data to run a probabilistic valuation.")
    else:
        k1, k2, k3, k4 = st.columns(4)
        k1.metric("Mean fair value", fmt_money(mc_res.mean, mkt.currency),
                  delta=fmt_pct((mc_res.mean / mkt.price - 1) if mkt.price else None))
        k2.metric("Median", fmt_money(mc_res.median, mkt.currency))
        k3.metric("90% band", f"{fmt_money(mc_res.p5, mkt.currency)} – {fmt_money(mc_res.p95, mkt.currency)}")
        k4.metric("P(upside)", fmt_pct(mc_res.prob_upside))

        fig = go.Figure(go.Histogram(x=mc_res.fair_values, nbinsx=50, marker_color="#1565c0"))
        if mkt.price:
            fig.add_vline(x=mkt.price, line_dash="dash", line_color="#c62828",
                          annotation_text="Price", annotation_position="top")
        fig.add_vline(x=mc_res.median, line_dash="dot", line_color="#2e7d32",
                      annotation_text="Median", annotation_position="bottom")
        fig.update_layout(
            title="Distribution of fair value per share", height=380,
            xaxis_title="Fair value per share", yaxis_title="Frequency",
            margin=dict(l=10, r=10, t=40, b=10),
        )
        st.plotly_chart(fig, use_container_width=True)
        st.caption(
            f"{mc_res.samples:,} valid draws · interquartile range "
            f"{fmt_money(mc_res.p25, mkt.currency)} – {fmt_money(mc_res.p75, mkt.currency)} · "
            "seeded for reproducibility."
        )

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

        def _hl_target(row):
            is_target = row["Ticker"] == mkt.ticker
            return ["background-color: #fff3cd" if is_target else "" for _ in row]

        styled = pd.DataFrame(prows).style.apply(_hl_target, axis=1)
        st.dataframe(styled, hide_index=True, use_container_width=True)

        m1, m2, m3 = st.columns(3)
        m1.metric("Peer median P/E", "—" if bench.median_pe is None else f"{bench.median_pe:.1f}")
        m2.metric("Peer median EV/EBITDA", "—" if bench.median_ev_ebitda is None else f"{bench.median_ev_ebitda:.1f}")
        m3.metric("Peer median P/B", "—" if bench.median_pb is None else f"{bench.median_pb:.1f}")

        # Target vs peer-median: premium/discount + implied fair value per multiple.
        target = comparables.peer_metrics(company)
        st.markdown(f"#### {mkt.ticker} vs peer median")

        def _premium(t, m):
            if t is None or m is None or m == 0:
                return None
            return t / m - 1.0

        prem_rows = []
        # P/E implied price = peer median P/E × EPS.
        implied_pe = bench.median_pe * fin.eps if bench.median_pe and fin.eps else None
        implied_pb = bench.median_pb * fin.book_value_per_share if bench.median_pb and fin.book_value_per_share else None
        prem_rows.append({
            "Multiple": "P/E",
            f"{mkt.ticker}": "—" if target.pe is None else f"{target.pe:.1f}",
            "Peer median": "—" if bench.median_pe is None else f"{bench.median_pe:.1f}",
            "Premium / (Discount)": fmt_pct(_premium(target.pe, bench.median_pe)),
            "Implied price": fmt_money(implied_pe, mkt.currency),
        })
        prem_rows.append({
            "Multiple": "EV/EBITDA",
            f"{mkt.ticker}": "—" if target.ev_ebitda is None else f"{target.ev_ebitda:.1f}",
            "Peer median": "—" if bench.median_ev_ebitda is None else f"{bench.median_ev_ebitda:.1f}",
            "Premium / (Discount)": fmt_pct(_premium(target.ev_ebitda, bench.median_ev_ebitda)),
            "Implied price": "—",
        })
        prem_rows.append({
            "Multiple": "P/B",
            f"{mkt.ticker}": "—" if target.pb is None else f"{target.pb:.1f}",
            "Peer median": "—" if bench.median_pb is None else f"{bench.median_pb:.1f}",
            "Premium / (Discount)": fmt_pct(_premium(target.pb, bench.median_pb)),
            "Implied price": fmt_money(implied_pb, mkt.currency),
        })
        st.dataframe(pd.DataFrame(prem_rows), hide_index=True, use_container_width=True)

        # Implied values vs current price.
        implied = [v for v in (implied_pe, implied_pb) if v is not None]
        if implied:
            avg_implied = sum(implied) / len(implied)
            ic1, ic2 = st.columns(2)
            ic1.metric("Avg implied price (peer multiples)",
                       fmt_money(avg_implied, mkt.currency),
                       delta=fmt_pct((avg_implied / mkt.price - 1) if mkt.price else None))
            verdict = (
                "trading at a premium to peers" if target.pe and bench.median_pe and target.pe > bench.median_pe
                else "trading at a discount to peers"
            )
            ic2.markdown(f"**Relative read:** {mkt.ticker} is {verdict}.")

        # Visual: P/E comparison across the group.
        pe_rows = [(r.ticker, r.pe) for r in bench.rows if r.pe is not None]
        if pe_rows:
            fig = go.Figure(
                go.Bar(
                    x=[t for t, _ in pe_rows],
                    y=[v for _, v in pe_rows],
                    marker_color=["#1565c0" if t == mkt.ticker else "#90a4ae" for t, _ in pe_rows],
                )
            )
            if bench.median_pe:
                fig.add_hline(y=bench.median_pe, line_dash="dash",
                              annotation_text="Peer median", line_color="#555")
            fig.update_layout(title="P/E comparison", height=320,
                              margin=dict(l=10, r=10, t=40, b=10))
            st.plotly_chart(fig, use_container_width=True)
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

    # ----- Year-by-year comparison -------------------------------------
    st.divider()
    st.markdown("#### Year-by-year history")
    hist_series = {
        "Revenue": company.historical_revenue,
        "Free cash flow": company.historical_fcf,
        "Dividends": company.historical_dividends,
    }
    hist_series = {k: v for k, v in hist_series.items() if v}
    if hist_series:
        n_years = max(len(v) for v in hist_series.values())
        # Oldest-first series; label as relative fiscal years (FY-n … latest).
        year_labels = [f"Y{i + 1}" for i in range(n_years)]
        sym = currency_symbol(mkt.currency)

        table_rows = []
        for metric, series in hist_series.items():
            # Left-pad shorter series so the latest values line up on the right.
            padded = [None] * (n_years - len(series)) + list(series)
            row = {"Metric": metric}
            for label, val in zip(year_labels, padded):
                row[label] = "—" if val is None else f"{sym}{val / 1e6:,.1f}M"
            table_rows.append(row)
        st.dataframe(pd.DataFrame(table_rows), hide_index=True, use_container_width=True)

        # Year-over-year growth table.
        yoy_rows = []
        for metric, series in hist_series.items():
            padded = [None] * (n_years - len(series)) + list(series)
            row = {"Metric": metric + " YoY"}
            prev = None
            for label, val in zip(year_labels, padded):
                if val is None or prev is None or prev == 0:
                    row[label] = "—"
                else:
                    row[label] = fmt_pct(val / prev - 1.0)
                prev = val if val is not None else prev
            yoy_rows.append(row)
        st.markdown("**Year-over-year growth**")
        st.dataframe(pd.DataFrame(yoy_rows), hide_index=True, use_container_width=True)

        # Revenue trend chart.
        if company.historical_revenue:
            rev = company.historical_revenue
            labels = year_labels[-len(rev):]
            fig = go.Figure(go.Bar(x=labels, y=rev, marker_color="#1565c0"))
            fig.update_layout(title="Revenue trend", height=300,
                              margin=dict(l=10, r=10, t=40, b=10))
            st.plotly_chart(fig, use_container_width=True)
        st.caption("History is oldest→latest (Y1 = earliest available fiscal year).")
    else:
        st.info("No multi-year history available for this ticker.")
