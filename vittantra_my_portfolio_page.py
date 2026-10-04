"""
My Portfolio page: build your own portfolio and see it the way a professional would.
"""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import my_portfolio as mp
import vittantra_cloud as cloud
import vittantra_theme as vt


STATUS_TEXT = {
    "ON TARGET": ("✅", "Within your chosen risk level."),
    "SLIGHTLY ABOVE": ("🟡", "A little more risk than your chosen level — see the suggestions below."),
    "ABOVE RISK LEVEL": ("🟠", "Clearly more risk than your chosen level — see the suggestions below."),
}


@st.cache_resource(show_spinner="Loading price history…", ttl=900)
def _history():
    import whatif_engine as we
    return mp.base_history(), we.load_fred()


@st.cache_data(show_spinner="Downloading price history for new holdings…", ttl=86_400)
def _fetched(symbols: tuple) -> pd.DataFrame:
    return mp.fetch_history(list(symbols))


@st.cache_resource(show_spinner="Building the risk model…", ttl=900, max_entries=50)
def _model_for(symbols: tuple):
    history, fred = _history()
    missing = tuple(s for s in symbols if s not in history.columns)
    return mp.model_for(list(symbols), history, fred, _fetched(missing) if missing else None)


@st.cache_data(show_spinner=False, ttl=300)
def _universe() -> pd.DataFrame:
    return mp.universe()


def _money(value: float) -> str:
    return f"${value:,.0f}"


def _user_key() -> str:
    return cloud.current_user() or "visitor"


def _load_into_session(table: pd.DataFrame) -> None:
    user = _user_key()
    if st.session_state.get("mp_loaded_for") == user:
        return
    data = mp.load(None if user == "visitor" else user)
    st.session_state["mp_holdings"] = data.get("holdings", [])
    st.session_state["mp_profile"] = int(data.get("profile", 3))
    st.session_state["mp_loaded_for"] = user
    st.session_state.pop("mp-editor", None)


def _set_base(holdings: list) -> None:
    """Replace the holdings the editor starts from (and clear its pending edits)."""
    st.session_state["mp_holdings"] = holdings
    st.session_state.pop("mp-editor", None)


def _builder(table: pd.DataFrame) -> None:
    labels = {r.symbol: f"{r.symbol} — {r.name} ({r.asset_class})" for r in table.itertuples()}
    with st.expander("➕ Start from a template", expanded=not st.session_state.get("mp_holdings")):
        names = list(mp.TEMPLATES)
        c1, c2, c3 = st.columns([2, 1, 1])
        choice = c1.selectbox("Template", names, key="mp-template",
                              help="Ready-made portfolios professionals often use as a starting point.")
        amount = c2.number_input("Amount ($)", min_value=1_000, value=100_000, step=10_000, key="mp-amount")
        c1.caption(mp.TEMPLATES[choice]["about"])
        if c3.button("Use template", key="mp-use-template", width="stretch"):
            _set_base(mp.from_weights(mp.TEMPLATES[choice]["weights"], amount, table))
            st.rerun()
    with st.expander("➕ Add a holding"):
        c1, c2, c3 = st.columns([3, 1, 1])
        symbol = c1.selectbox("Security or asset", list(labels), format_func=labels.get, key="mp-add-symbol",
                              index=None, placeholder="Type to search: Tesla, Ford, gold, bitcoin, Treasury, hotel REIT…")
        dollars = c2.number_input("Amount ($)", min_value=0, value=10_000, step=1_000, key="mp-add-dollars")
        if c3.button("Add", key="mp-add", width="stretch", disabled=symbol is None):
            price = float(table.set_index("symbol").at[symbol, "price"])
            _set_base(st.session_state.get("mp_current", []) + [{"symbol": symbol, "quantity": round(dollars / price, 6)}])
            st.rerun()


def _holdings_editor(table: pd.DataFrame) -> list:
    holdings = st.session_state.get("mp_holdings", [])
    frame = pd.DataFrame(holdings or [], columns=["symbol", "quantity"])
    edited = st.data_editor(frame, num_rows="dynamic", hide_index=True, width="stretch", key="mp-editor",
                            column_config={
                                "symbol": st.column_config.SelectboxColumn(
                                    "Symbol", options=sorted(table["symbol"]), required=True,
                                    help="Pick from Vittantra's investable universe."),
                                "quantity": st.column_config.NumberColumn(
                                    "Quantity", min_value=0.0, format="%.4f",
                                    help="Number of shares or units. Change it to resize a holding.")})
    return edited.dropna(subset=["symbol"]).to_dict("records")


def _save_controls(holdings: list) -> None:
    user = cloud.current_user()
    if user is None:
        st.caption("You are trying this as a visitor: the portfolio lasts until you close the page. Sign in or "
                   "create an account (sidebar) to save it.")
        return
    if st.button("💾 Save my portfolio", key="mp-save", type="primary"):
        path = mp.save(user, holdings, int(st.session_state.get("mp_profile", 3)), table=_universe())
        cloud.persist(path, f"Portfolio saved by {user}")
        st.success("Saved.")


def _analysis(holdings: list, table: pd.DataFrame, profile: int) -> None:
    symbols = tuple(sorted({str(h["symbol"]).upper() for h in holdings if h.get("symbol")}))
    result = mp.analyse(holdings, _model_for(symbols), table, profile)
    if result.get("error"):
        st.info(result["error"])
        return
    level, status = result["profile"], result["status"]
    icon, text = STATUS_TEXT[status]
    risk = result["risk"]
    m = st.columns(4)
    m[0].metric("Portfolio value", _money(result["value"]))
    m[1].metric("Volatility (a year)", f"{result['volatility']:.1%}",
                f"target {level['target_vol']:.0%} ({level['name']})", delta_color="off")
    m[2].metric("1-day 99% VaR", _money(risk["var99_1d_parametric"]))
    m[3].metric("Beta to S&P 500", f"{risk['beta_spy']:.2f}" if pd.notna(risk.get("beta_spy")) else "n/a")
    st.markdown(f"### {icon} {status.title()} — {text}")

    left, right = st.columns(2)
    with left:
        mix = result["mix"]
        fig = go.Figure(go.Pie(labels=mix.index, values=mix.values * 100, hole=0.55, sort=False))
        fig.update_layout(height=300, margin=dict(l=10, r=10, t=40, b=10), title="What you own (by value)")
        st.plotly_chart(fig, width="stretch")
    with right:
        pos = result["positions"].sort_values("risk_share")
        fig = go.Figure(go.Bar(x=pos["risk_share"] * 100, y=pos["symbol"], orientation="h",
                               marker_color=vt.FOREST, text=[f"{v:.0%}" for v in pos["risk_share"]],
                               textposition="outside"))
        fig.update_layout(height=300, margin=dict(l=10, r=30, t=40, b=10), title="What drives your risk (%)")
        st.plotly_chart(fig, width="stretch")
    st.caption("Professionals look at both: a holding can be small by value but large by risk (Euler risk "
               "contributions — the shares add up to 100%).")

    st.markdown("#### Checks professionals run")
    for name, ok, detail in result["checks"]:
        st.markdown(f"{'✅' if ok else '⚠️'} **{name}** — {detail}")

    st.markdown("#### Stress tests: what would happen in…")
    scen = pd.DataFrame([{"Scenario": k, "Estimated P&L ($)": v, "P&L (%)": v / result["value"] * 100}
                         for k, v in result["scenarios"].items()])
    st.dataframe(scen, hide_index=True, width="stretch",
                 column_config={"Estimated P&L ($)": st.column_config.NumberColumn(format="$%.0f"),
                                "P&L (%)": st.column_config.NumberColumn(format="%+.1f%%")})
    st.caption("Each scenario applies factor shocks sized like past episodes (e.g. 2022 rates, 2008 credit) to "
               "each holding's measured sensitivities. Linear estimates, not forecasts.")
    if result["tips"]:
        st.markdown("#### Suggestions")
        for tip in result["tips"]:
            st.markdown(f"- {tip}")
    else:
        st.success("No changes suggested: the portfolio fits your risk level and passes every check.")
    with st.expander("Holdings detail"):
        st.dataframe(result["positions"][["symbol", "name", "asset_class", "quantity", "price", "market_value",
                                          "weight", "risk_share"]], hide_index=True, width="stretch",
                     column_config={"price": st.column_config.NumberColumn("Price", format="$%.2f"),
                                    "market_value": st.column_config.NumberColumn("Market value", format="$%.0f"),
                                    "weight": st.column_config.NumberColumn("Weight", format="percent"),
                                    "risk_share": st.column_config.NumberColumn("Risk share", format="percent")})
    if result.get("missing"):
        st.caption("No daily price history yet for: " + ", ".join(result["missing"]) + " (left out of risk).")
    st.caption("A model portfolio for learning — prices from free data (may be delayed); nothing is traded.")


def _performance_and_watchlist(table: pd.DataFrame) -> None:
    user = cloud.current_user()
    data = mp.load(user) if user else {}
    perf = mp.performance(data, table) if data else None
    if perf and perf["portfolio_return"] is not None:
        st.markdown("#### Since you saved it")
        c = st.columns(3)
        c[0].metric("Portfolio return", f"{perf['portfolio_return']:+.2%}", f"since {perf['since']}", delta_color="off")
        c[1].metric("S&P 500 (SPY)", f"{perf['spy_return']:+.2%}" if perf["spy_return"] is not None else "n/a",
                    delta_color="off")
        c[2].metric("Value", _money(perf["value_now"]), f"from {_money(perf['value_then'])}", delta_color="off")
        st.caption("Historical result of a hypothetical portfolio at free (possibly delayed) prices — not a promise of "
                   "future returns. Changing the holdings and saving starts a new baseline.")

    st.markdown("#### 👀 Watchlist & alerts")
    st.caption("Professionals keep a watchlist and set alerts so they react to moves instead of watching screens all "
               "day. Alerts show here and in your Home briefing.")
    current = pd.DataFrame(data.get("watchlist", []) if data else st.session_state.get("mp_watch", []),
                           columns=["symbol", "move", "above", "below"])
    edited = st.data_editor(current, num_rows="dynamic", hide_index=True, width="stretch", key="mp-watch-editor",
                            column_config={
                                "symbol": st.column_config.SelectboxColumn("Symbol", options=sorted(table["symbol"]),
                                                                           required=True),
                                "move": st.column_config.NumberColumn("Daily move ±%", min_value=0.0, format="%.1f",
                                                                      help="Alert when the price moves more than this "
                                                                           "in a day (in either direction)."),
                                "above": st.column_config.NumberColumn("Price above $", min_value=0.0, format="%.2f"),
                                "below": st.column_config.NumberColumn("Price below $", min_value=0.0, format="%.2f")})
    watch = edited.dropna(subset=["symbol"]).to_dict("records")
    if user:
        if st.button("Save watchlist", key="mp-watch-save"):
            path = mp.save_watchlist(user, watch)
            cloud.persist(path, f"Watchlist saved by {user}")
            st.success("Watchlist saved.")
    else:
        st.session_state["mp_watch"] = watch
    triggered = mp.alerts([w for w in watch if w.get("symbol")], table)
    for alert in triggered:
        st.warning("🔔 " + alert["text"])
    if watch and not triggered:
        st.success("No alerts triggered right now.")


def render_my_portfolio() -> None:
    st.markdown("### My Portfolio")
    st.caption("Build your own portfolio from 4,000+ US stocks and 200+ funds and assets — bonds, FX, commodities, "
               "crypto, real estate and alternatives — and see it the way a portfolio manager and risk team would.")
    table = _universe()
    if table.empty:
        st.info("Market data is not available yet.")
        return
    _load_into_session(table)
    profiles = mp.profiles()
    profile = st.select_slider("Your risk level", options=list(profiles), key="mp_profile",
                               format_func=lambda k: f"{profiles[k]['name']} (~{profiles[k]['target_vol']:.0%} vol)",
                               help="Like an adviser's risk profile: the yearly volatility you are comfortable "
                                    "with. The portfolio is checked against it. Unsure? Take the questionnaire in "
                                    "Advisory → New client questionnaire.")
    _builder(table)
    holdings = _holdings_editor(table)
    st.session_state["mp_current"] = holdings            # editor result; the base changes only via the builder
    _save_controls(holdings)
    if holdings:
        st.divider()
        _analysis(holdings, table, profile)
    st.divider()
    _performance_and_watchlist(table)


SNAPSHOT = [("SPY", "S&P 500"), ("QQQ", "Nasdaq-100"), ("EFA", "Developed ex-US"), ("TLT", "20Y+ Treasuries"),
            ("GLD", "Gold"), ("USO", "Oil"), ("BTC-USD", "Bitcoin"), ("EURUSD=X", "EUR / USD")]


def sidebar_markets() -> None:
    """Market snapshot in the sidebar for visitors and users (1-day moves from Vittantra's market data)."""
    from pathlib import Path
    path = Path(mp.BASE_DIR) / mp.ANALYTICS
    if not path.exists():
        return
    data = pd.read_csv(path).set_index("symbol")
    st.caption("MARKETS TODAY")
    lines = []
    for symbol, label in SNAPSHOT:
        if symbol not in data.index or pd.isna(data.at[symbol, "return_1d"]):
            continue
        move = float(data.at[symbol, "return_1d"])
        colour = "green" if move >= 0 else "red"
        lines.append(f"{label} :{colour}[{'▲' if move >= 0 else '▼'} {abs(move):.1%}]")
    st.markdown("  \n".join(lines))
    user = cloud.current_user()
    if user and user != "owner":
        saved = mp.load(user).get("holdings")
        st.caption("MY PORTFOLIO")
        st.markdown(f"{len(saved)} holding(s) saved" if saved else "Not built yet — open **My Portfolio**")
