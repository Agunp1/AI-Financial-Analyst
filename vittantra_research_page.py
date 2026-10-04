"""
Day 76 — Research page for the Vittantra app (fundamental analysis).

Reads day76_fundamental_scores.csv and day76_fundamental_metrics.csv
written by fundamental_engine.py.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import vittantra_theme as vt


BASE_DIR = Path(__file__).resolve().parent

PILLAR_LABELS = {
    "value_score": "Value",
    "growth_score": "Growth",
    "quality_score": "Quality",
    "financial_health_score": "Financial Health",
}

METRIC_FORMATS = [
    ("Valuation", [
        ("pe_ratio", "P/E", "{:.1f}x"),
        ("earnings_yield", "Earnings yield", "{:.1%}"),
        ("fcf_yield", "FCF yield", "{:.1%}"),
        ("book_to_price", "Book / price", "{:.2f}"),
        ("ebit_to_ev", "EBIT / EV", "{:.1%}"),
    ]),
    ("Growth (TTM, year over year)", [
        ("revenue_growth", "Revenue growth", "{:+.1%}"),
        ("eps_growth", "EPS growth", "{:+.1%}"),
        ("operating_income_growth", "Operating income growth", "{:+.1%}"),
    ]),
    ("Quality", [
        ("roe", "Return on equity", "{:.1%}"),
        ("roa", "Return on assets", "{:.1%}"),
        ("gross_margin", "Gross margin", "{:.1%}"),
        ("operating_margin", "Operating margin", "{:.1%}"),
        ("accruals_ratio", "Accruals ratio (lower is better)", "{:+.1%}"),
    ]),
    ("Financial health", [
        ("debt_to_equity", "Debt / equity", "{:.2f}"),
        ("current_ratio", "Current ratio", "{:.2f}"),
        ("interest_coverage", "Interest coverage", "{:.1f}x"),
        ("net_debt_to_ebitda", "Net debt / EBITDA", "{:.2f}"),
        ("equity_to_assets", "Equity / assets", "{:.1%}"),
    ]),
]


@st.cache_data(show_spinner=False, ttl=60)
def _load(name: str) -> pd.DataFrame:
    path = BASE_DIR / name
    return pd.read_csv(path) if path.exists() else pd.DataFrame()


def _fmt(value, pattern: str) -> str:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return "n/a"
    if pd.isna(number):
        return "n/a"
    return pattern.format(number)


def _money(value) -> str:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return "n/a"
    if pd.isna(number):
        return "n/a"
    for unit, size in (("T", 1e12), ("B", 1e9), ("M", 1e6)):
        if abs(number) >= size:
            return f"${number / size:,.1f}{unit}"
    return f"${number:,.0f}"


PILLAR_NAMES = ["fundamental", "technical", "quant", "economic", "risk"]


def render_ratings() -> None:
    ratings = _load("day77_current_ratings.csv")
    ic = _load("day77_ic_summary.csv")
    backtest = _load("day77_backtest_summary.csv")
    validation = _load("day77_validation_summary.csv")
    if ratings.empty:
        st.info("No ratings yet. Run `python multi_factor_rating.py`.")
        return
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("As of", str(ratings["as_of"].iloc[0]))
    c2.metric("Overweight", int((ratings["rating"] == "Overweight").sum()))
    c3.metric("Macro regime", str(ratings["regime"].iloc[0]).replace("_", "-"))
    c4.metric("Data checks", f"{int(validation['passed'].sum())}/{len(validation)}" if not validation.empty else "n/a")
    basis = ratings["rating_basis"].iloc[0] if "rating_basis" in ratings else "composite"
    score_columns = ["composite_ic_weighted", "composite"] if "composite_ic_weighted" in ratings else ["composite"]
    view = ratings[["ticker", "name", "sector", "rating", *score_columns, *PILLAR_NAMES,
                    "strongest_pillar", "weakest_pillar"]].rename(
        columns=lambda c: {"composite_ic_weighted": "Score (IC-weighted)", "composite": "Equal-weight"}.get(c, c.title()))
    config = {label: st.column_config.ProgressColumn(label, min_value=0, max_value=100, format="%.0f")
              for label in ["Score (IC-weighted)", "Equal-weight", *[p.title() for p in PILLAR_NAMES]]}
    st.dataframe(view, width="stretch", hide_index=True, column_config=config)
    basis_text = ("the IC-weighted score (pillars weighted by how well they predicted returns in past, "
                  "completed periods)" if basis == "composite_ic_weighted" else "the equal-weight composite")
    st.caption(f"Overweight = top 30% of {basis_text}, Underweight = bottom 30%. Research labels, "
               "not trade instructions.")
    if not ic.empty:
        st.markdown("**Does each pillar predict returns?** Information coefficient = rank correlation between "
                    "the score and the next 20-day return, averaged across past dates (point in time).")
        st.dataframe(ic.round(3), width="stretch", hide_index=True)
        st.caption("|t-stat| above about 2 is statistically meaningful. A combined score is only worth using "
                   "if it beats its best single pillar out of sample.")
    if not backtest.empty:
        st.markdown("**Backtest portfolios** (equal weight, 10 bps per dollar traded)")
        st.dataframe(backtest.round(3), width="stretch", hide_index=True)
    if not validation.empty:
        with st.expander("Data quality"):
            st.dataframe(validation[["check", "passed", "details"]], width="stretch", hide_index=True)


def _value_chart(row, height: int = 300):
    models = {m: row.get(f"{m.lower()}_value") for m in ("DCF", "RI", "DDM")}
    models = {m: float(v) for m, v in models.items() if v is not None and pd.notna(v)}
    if not models:
        return None
    figure = go.Figure(go.Bar(x=list(models), y=list(models.values()), marker_color=vt.FOREST,
                              text=[f"${v:,.0f}" for v in models.values()], textposition="outside"))
    figure.add_hline(y=float(row["price"]), line_dash="dash", line_color=vt.BRASS,
                     annotation_text=f"Price ${float(row['price']):,.0f}")
    figure.update_layout(height=height, margin=dict(l=10, r=10, t=40, b=10), title="Value per share by model",
                         yaxis_title="$ per share")
    return figure


def _note_for_page(note: str) -> str:
    # Smaller headings inside the page; escape $ so Streamlit does not read it as LaTeX
    return note.replace("$", "\\$").replace("\n## ", "\n#### ").replace("# ", "### ", 1)


def render_any_company() -> None:
    """On-demand note for any US-listed company in the all-US scan."""
    from research_report import report_markdown, research_any

    st.markdown("#### Research any US-listed company")
    query = st.text_input("Ticker (e.g. TSLA, F, NFLX)", key="any-ticker",
                          placeholder="Type a ticker and press Enter").strip().upper()
    if not query:
        st.caption("Full reports with multi-factor ratings cover the 33-stock research universe below; any other "
                   "US-listed company gets an on-demand valuation and note from its SEC filings.")
        return
    result = research_any(query)
    if result is None:
        st.warning(f"{query} is not in Vittantra's US company scan (operating companies with SEC filings; funds "
                   "and ETFs are excluded). Check the ticker, or browse Research → All US-listed stocks.")
        return
    summary, valuation = result["summary"], result["valuation"]
    m = st.columns(4)
    m[0].metric("Price", _fmt(summary["price"], "${:,.2f}"))
    m[1].metric(f"Intrinsic value ({summary['primary_model'] or 'n/a'})", _fmt(summary["fair_value"], "${:,.2f}"))
    m[2].metric("Upside", _fmt(summary["upside"], "{:+.0%}"))
    m[3].metric("Valuation", summary["valuation_signal"] or "not valued")
    left, right = st.columns([3, 2])
    note = report_markdown(query, result["claims"], summary)
    with left:
        st.markdown(_note_for_page(note))
    with right:
        figure = _value_chart(valuation)
        if figure is not None:
            st.plotly_chart(figure, width="stretch")
        grid = result["sensitivity"]
        if not grid.empty:
            pivot = grid.pivot(index="wacc", columns="terminal_growth", values="value_per_share")
            pivot.index = [f"WACC {w:.1%}" for w in pivot.index]
            pivot.columns = [f"g {g:.1%}" for g in pivot.columns]
            st.markdown("**DCF sensitivity ($ per share)**")
            st.dataframe(pivot.round(0), width="stretch")
        st.download_button("Download note (Markdown)", note, file_name=f"vittantra_note_{query}.md",
                           key="any-download")
    st.caption("On-demand notes use the same valuation models and the same evidence rule as the full reports. "
               "Beta defaults to 1.0 (no price history for companies outside the research universe), and the "
               "note lists what is missing. Research only, not a recommendation.")
    st.divider()


def render_valuation_reports() -> None:
    """Day 78: intrinsic value models and evidence-linked research notes."""
    from research_report import report_markdown

    render_any_company()

    valuation = _load("day78_valuation.csv")
    summary = _load("day78_report_summary.csv")
    claims = _load("day78_research_claims.csv")
    sensitivity = _load("day78_dcf_sensitivity.csv")
    assumptions = _load("day78_valuation_assumptions.csv")
    if valuation.empty or summary.empty:
        st.info("Run `python valuation_engine.py` and then `python research_report.py`.")
        return

    c1, c2, c3, c4 = st.columns(4)
    signals = valuation["valuation_signal"].value_counts()
    c1.metric("Stocks valued", int(valuation["fair_value"].notna().sum()))
    c2.metric("Undervalued (>15% below value)", int(signals.get("Undervalued", 0)))
    c3.metric("Overvalued (>15% above value)", int(signals.get("Overvalued", 0)))
    rf = assumptions.set_index("assumption")["value"].get("risk_free_rate") if not assumptions.empty else None
    c4.metric("Risk-free rate (10Y)", f"{float(rf):.2%}" if rf is not None else "n/a")

    table = summary[["ticker", "name", "rating", "price", "fair_value", "upside", "primary_model",
                     "implied_growth", "valuation_signal", "bull_points", "bear_points"]].copy()
    for column in ("upside", "implied_growth"):
        table[column] = pd.to_numeric(table[column], errors="coerce") * 100
    st.dataframe(table.rename(columns={
        "ticker": "Ticker", "name": "Name", "rating": "Rating", "price": "Price", "fair_value": "Intrinsic value",
        "upside": "Upside %", "primary_model": "Model", "implied_growth": "Growth priced in %",
        "valuation_signal": "Valuation", "bull_points": "Bull points", "bear_points": "Bear points"}),
        width="stretch", hide_index=True,
        column_config={"Price": st.column_config.NumberColumn(format="$%.2f"),
                       "Intrinsic value": st.column_config.NumberColumn(format="$%.2f"),
                       "Upside %": st.column_config.NumberColumn(format="%+.0f%%"),
                       "Growth priced in %": st.column_config.NumberColumn(format="%.1f%%")})
    st.caption("Model = the primary model for the business type: DCF (free cash flow to the firm), RI (residual "
               "income — banks and insurers) or DDM (dividend discount — dividend-paying utilities and REITs). "
               "'Growth priced in' is the reverse DCF: the five-year growth rate the current price implies.")

    ticker = st.selectbox("Research note", summary["ticker"], format_func=lambda t: f"{t} — "
                          f"{summary.set_index('ticker').at[t, 'name']}")
    row = valuation.set_index("ticker").loc[ticker]
    left, right = st.columns([3, 2])
    with left:
        note = report_markdown(ticker, claims, summary.set_index("ticker").loc[ticker])
        st.markdown(_note_for_page(note))
    with right:
        figure = _value_chart(row)
        if figure is not None:
            st.plotly_chart(figure, width="stretch")
        grid = sensitivity[sensitivity["ticker"] == ticker] if not sensitivity.empty else sensitivity
        if not grid.empty:
            pivot = grid.pivot(index="wacc", columns="terminal_growth", values="value_per_share")
            pivot.index = [f"WACC {w:.1%}" for w in pivot.index]
            pivot.columns = [f"g {g:.1%}" for g in pivot.columns]
            st.markdown("**DCF sensitivity ($ per share)**")
            st.dataframe(pivot.round(0), width="stretch")
            st.caption("Small changes in the discount rate and terminal growth move the value a lot — "
                       "that is why professionals show a range, not one number.")
        st.download_button("Download note (Markdown)",
                           report_markdown(ticker, claims, summary.set_index("ticker").loc[ticker]),
                           file_name=f"vittantra_note_{ticker}.md")
    with st.expander("Valuation assumptions and sources"):
        st.dataframe(assumptions, width="stretch", hide_index=True)


def render_research() -> None:
    st.markdown("### Research — Fundamental Analysis")
    st.caption(
        "Point-in-time fundamentals from SEC EDGAR filings (10-K / 10-Q). "
        "Scores are percentiles within the research universe (0–100)."
    )

    universe = st.radio(
        "View",
        ["Research universe (33 stocks)", "All US-listed stocks", "Multi-factor ratings", "Valuation & reports"],
        horizontal=True,
    )
    if universe == "Multi-factor ratings":
        render_ratings()
        return
    if universe == "Valuation & reports":
        render_valuation_reports()
        return
    us_market = universe.startswith("All US")
    prefix = "day76_us_" if us_market else "day76_"
    scores = _load(f"{prefix}fundamental_scores.csv")
    metrics = _load(f"{prefix}fundamental_metrics.csv")
    validation = _load(f"{prefix}validation_summary.csv")
    if scores.empty or metrics.empty:
        command = "us_fundamental_engine.py" if us_market else "fundamental_engine.py"
        st.info(
            "No fundamental data yet. Add `SEC_USER_AGENT=Your Name your@email.com` "
            f"to your `.env` file, then run `python {command}`."
        )
        return

    metrics = metrics.set_index("ticker")
    scores = scores.set_index("ticker")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("As of", str(metrics["as_of"].iloc[0]))
    c2.metric("Companies scored", f"{int(scores['fundamental_score'].notna().sum())}/{len(scores)}")
    c3.metric("Sectors", int(scores["sector"].nunique()))
    c4.metric(
        "Data checks",
        f"{int(validation['passed'].sum())}/{len(validation)}" if not validation.empty else "n/a",
    )

    sectors = sorted(scores["sector"].dropna().unique())
    if us_market:
        f1, f2, f3 = st.columns([2, 1, 1])
        chosen = f1.multiselect("Sectors", sectors, default=[])
        size = f2.selectbox("Market cap", ["All", "≥ $300M", "≥ $2B", "≥ $10B", "≥ $200B"], index=2)
        search = f3.text_input("Find ticker or name").strip().lower()
        minimum = {"All": 0, "≥ $300M": 3e8, "≥ $2B": 2e9, "≥ $10B": 1e10, "≥ $200B": 2e11}[size]
        table = scores.copy()
        if chosen:
            table = table[table["sector"].isin(chosen)]
        table = table[pd.to_numeric(table["market_cap"], errors="coerce").fillna(0) >= minimum]
        if search:
            mask = table.index.str.lower().str.contains(search, regex=False) | \
                table["name"].str.lower().str.contains(search, regex=False)
            table = table[mask]
        st.caption(f"{len(table):,} companies match; scores are percentiles within each sector.")
    else:
        chosen = st.multiselect("Sectors", sectors, default=sectors)
        table = scores[scores["sector"].isin(chosen)].copy()
    table = table.sort_values("fundamental_score", ascending=False)
    columns = ["name", "sector", "fundamental_score", *PILLAR_LABELS]
    if us_market:
        table["market_cap_b"] = pd.to_numeric(table["market_cap"], errors="coerce") / 1e9
        columns = ["name", "sector", "market_cap_b", "fundamental_score", *PILLAR_LABELS, "sector_rank"]
    display = table[columns].head(500 if us_market else len(table)).rename(
        columns={**PILLAR_LABELS, "fundamental_score": "Fundamental", "name": "Company",
                 "sector": "Sector", "market_cap_b": "Mkt cap ($B)", "sector_rank": "Sector rank"}
    )
    score_columns = {
        label: st.column_config.ProgressColumn(label, min_value=0, max_value=100, format="%.0f")
        for label in [*PILLAR_LABELS.values(), "Fundamental"]
    }
    st.dataframe(display, width="stretch", column_config=score_columns)

    st.divider()
    ticker = st.selectbox(
        "Company detail",
        display.index.tolist() or scores.index.tolist(),
        format_func=lambda t: f"{t} — {scores.loc[t, 'name']}",
    )
    row, score_row = metrics.loc[ticker], scores.loc[ticker]

    d1, d2, d3, d4 = st.columns(4)
    d1.metric("Fundamental score", _fmt(score_row["fundamental_score"], "{:.0f}"))
    if us_market:
        rank = score_row.get("sector_rank")
        peers = int(scores.loc[scores["sector"] == score_row["sector"], "fundamental_score"].notna().sum())
        d2.metric("Sector rank", f"{int(rank)} of {peers}" if pd.notna(rank) else "n/a")
    else:
        rank = score_row.get("fundamental_rank")
        d2.metric("Rank", f"{int(rank)} of {int(scores['fundamental_score'].notna().sum())}"
                  if pd.notna(rank) else "n/a")
    d3.metric("Market cap", _money(row.get("market_cap")))
    d4.metric("Revenue (TTM)", _money(row.get("revenue_ttm")))

    left, right = st.columns([1, 1.4])
    with left:
        values = [score_row.get(column) for column in PILLAR_LABELS]
        figure = go.Figure(go.Bar(
            x=values, y=list(PILLAR_LABELS.values()), orientation="h",
            text=[_fmt(v, "{:.0f}") for v in values], textposition="outside",
            marker_color=vt.FOREST,
        ))
        figure.update_layout(height=260, margin=dict(l=10, r=30, t=10, b=10),
                             xaxis=dict(range=[0, 110], title="Percentile score"))
        st.plotly_chart(figure, width="stretch")
    with right:
        for title, items in METRIC_FORMATS:
            st.markdown(f"**{title}**")
            st.markdown(" · ".join(f"{label}: **{_fmt(row.get(key), fmt)}**" for key, label, fmt in items))

    notes = [
        f"Latest filing: {str(row.get('latest_filing_date'))[:10]}; "
        f"period ending {str(row.get('latest_period_end'))[:10]}."
    ]
    if str(row.get("negative_equity")).lower() == "true":
        notes.append("Shareholders' equity is negative (often from buybacks), so ROE, book/price "
                     "and debt/equity are not meaningful.")
    if row.get("sector") == "Financials":
        notes.append("Financials: gross margin, current ratio, leverage and EV-based ratios do not "
                     "apply to banks and asset managers; capital strength (equity/assets) is used.")
    if row.get("sector") == "Real Estate":
        notes.append("REITs are usually valued on funds from operations (FFO); P/E understates them.")
    for note in notes:
        st.caption(note)
    st.caption("Research inputs only — not investment recommendations.")
