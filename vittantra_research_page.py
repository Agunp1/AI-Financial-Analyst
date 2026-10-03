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


def render_research() -> None:
    st.markdown("### Research — Fundamental Analysis")
    st.caption(
        "Point-in-time fundamentals from SEC EDGAR filings (10-K / 10-Q). "
        "Scores are percentiles within the research universe (0–100)."
    )

    universe = st.radio(
        "View",
        ["Research universe (33 stocks)", "All US-listed stocks", "Multi-factor ratings"],
        horizontal=True,
    )
    if universe == "Multi-factor ratings":
        render_ratings()
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
            marker_color="#2E6BE6",
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
