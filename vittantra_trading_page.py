"""
Trading Desk page (Day 92): the trader agent's brief, ranked ideas with a
chart of each plan, a paper blotter and the honest history of the rules.
Nothing is executed; the blotter is paper only.
"""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import academy_desk as desk
import trader_agent as ta
import vittantra_cloud as cloud
import vittantra_theme as vt


@st.cache_data(ttl=900, show_spinner=False)
def _run(stamp: float):
    history = ta.load_history()
    backtest = ta.backtest_setups(history)
    return history, ta.scan(history, backtest=backtest), backtest, ta.regime(history)


def _load_progress() -> dict:
    path = cloud.progress_path()
    return desk.load_progress(path) if path is not None else desk.load_progress()


def _chart(history: pd.DataFrame, row: pd.Series) -> go.Figure:
    frame = ta.indicator_frame(history[row["symbol"]]).tail(180)
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=frame.index, y=frame["price"], name="Price", line={"color": vt.INK, "width": 1.6}))
    fig.add_trace(go.Scatter(x=frame.index, y=frame["sma50"], name="50-day", line={"color": vt.BRASS, "width": 1}))
    fig.add_trace(go.Scatter(x=frame.index, y=frame["sma200"], name="200-day",
                             line={"color": vt.MUTED, "width": 1, "dash": "dot"}))
    if pd.notna(row.get("stop")):
        for level, label, colour in ((row["entry"], "Entry", vt.INK), (row["stop"], "Stop", vt.NEGATIVE),
                                     (row["target"], "Target", vt.POSITIVE)):
            fig.add_hline(y=level, line={"color": colour, "width": 1, "dash": "dash"},
                          annotation_text=f"{label} {level:,.4g}", annotation_position="right")
    fig.update_layout(height=360, margin={"l": 10, "r": 90, "t": 10, "b": 10}, legend={"orientation": "h"},
                      paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", font={"color": vt.INK})
    return fig


def render_trading() -> None:
    st.markdown("### Trading Desk")
    st.markdown('<div class="vt-lede">A rule-based trader agent scans every instrument with daily history, '
                'reads the regime and proposes trades with entry, stop, target and size. You decide; ideas go to '
                'a paper blotter only. Nothing is executed.</div>', unsafe_allow_html=True)
    try:
        stamp = max((ta.BASE_DIR / f).stat().st_mtime for f in (ta.HISTORY, ta.ANALYTICS))
        history, table, backtest, reg = _run(stamp)
    except FileNotFoundError as exc:
        st.info(str(exc))
        return
    ideas = ta.top_ideas(table)
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Regime", reg["state"])
    c2.metric("VIX", f"{reg['vix']:.1f}" if reg["vix"] else "—",
              f"{reg['vix_percentile']:.0%} percentile (1y)" if reg["vix"] else None, delta_color="off",
              delta_arrow="off")
    c3.metric("S&P 500 vs 200-day", f"{reg['spy_vs_200d']:+.1%}" if reg["spy_vs_200d"] is not None else "—")
    c4.metric("Directional setups", f"{int(table['direction'].isin(['Long', 'Short']).sum())} of {len(table)}")
    st.caption(f"Daily closes to {table['as_of'].max()} · paper book {ta.BOOK:,.0f} USD · risk per idea "
               f"{ta.RISK_PER_TRADE:.1%} of the book · stop {ta.STOP_ATR:.0f} ATR, target {ta.TARGET_ATR:.0f} ATR")

    brief, ideas_tab, blotter, history_tab, scan_tab = st.tabs(
        ["Agent brief", "Ideas", "Paper blotter", "Rule history", "Full scan"])

    with brief:
        st.markdown(ta.agent_brief(table, reg, backtest).replace("$", "\\$"))

    progress = _load_progress()
    with ideas_tab:
        if ideas.empty:
            st.info("No directional setups today.")
        else:
            show = ideas[["symbol", "name", "asset_class", "direction", "setup", "conviction", "entry", "stop",
                          "target", "quantity", "risk_at_stop"] + (["history_edge"] if "history_edge" in ideas else [])]
            st.dataframe(show.rename(columns={
                "symbol": "Symbol", "name": "Name", "asset_class": "Asset class", "direction": "Direction",
                "setup": "Setup", "conviction": "Conviction", "entry": "Entry", "stop": "Stop", "target": "Target",
                "quantity": "Quantity", "risk_at_stop": "Risk at stop (USD)", "history_edge": "Historical edge"}),
                hide_index=True, width="stretch",
                column_config={"Conviction": st.column_config.ProgressColumn(min_value=0, max_value=100, format="%d"),
                               "Entry": st.column_config.NumberColumn(format="%.4g"),
                               "Stop": st.column_config.NumberColumn(format="%.4g"),
                               "Target": st.column_config.NumberColumn(format="%.4g"),
                               "Quantity": st.column_config.NumberColumn(format="%.2f"),
                               "Risk at stop (USD)": st.column_config.NumberColumn(format="%.0f")})
            pick = st.selectbox("Idea", ideas["symbol"], key="td-pick",
                                format_func=lambda s: f"{s} · {ideas.set_index('symbol').loc[s, 'name']}")
            row = ideas.set_index("symbol").loc[pick].copy()
            row["symbol"] = pick
            st.plotly_chart(_chart(history, row), width="stretch")
            st.markdown(f"**Why:** {row['why']}.")
            if cloud.cloud_mode() and cloud.current_user() is None:
                st.caption("Sign in (sidebar) to keep a paper blotter.")
            elif st.button(f"Add {pick} to my paper blotter", key="td-add", type="primary"):
                from vittantra_academy_page import _save
                ta.open_paper_trade(progress, {**row.to_dict(), "symbol": pick})
                _save(progress)
                st.success(f"Paper trade added: {row['direction']} {pick}. Nothing was sent to any market.")

    with blotter:
        marked = ta.mark_paper_trades(progress, history)
        summary = ta.blotter_summary(marked)
        b1, b2, b3, b4 = st.columns(4)
        b1.metric("Paper trades", summary["trades"], f"{summary['open']} open", delta_color="off", delta_arrow="off")
        b2.metric("Paper P&L", f"{summary['pnl']:+,.0f} USD")
        b3.metric("Hit rate", f"{summary['hit_rate']:.0%}" if summary["hit_rate"] is not None else "—")
        b4.metric("Average R", f"{summary['avg_r']:+.2f}" if summary["avg_r"] is not None else "—")
        if marked.empty:
            st.info("No paper trades yet. Add one from the Ideas tab.")
        else:
            view = marked[["id", "opened", "direction", "symbol", "setup", "entry", "stop", "target", "last",
                           "status", "pnl", "r_multiple"]]
            st.dataframe(view.rename(columns={"id": "#", "opened": "Opened", "direction": "Direction",
                                              "symbol": "Symbol", "setup": "Setup", "entry": "Entry", "stop": "Stop",
                                              "target": "Target", "last": "Last / exit", "status": "Status",
                                              "pnl": "P&L (USD)", "r_multiple": "R multiple"}),
                         hide_index=True, width="stretch",
                         column_config={"P&L (USD)": st.column_config.NumberColumn(format="%.0f"),
                                        "R multiple": st.column_config.NumberColumn(format="%.2f")})
            open_ids = marked.loc[marked["status"] == "Open", "id"].tolist()
            if open_ids and not (cloud.cloud_mode() and cloud.current_user() is None):
                close_id = st.selectbox("Close a paper trade at the last price", open_ids, key="td-close-id")
                if st.button("Close paper trade", key="td-close"):
                    from vittantra_academy_page import _save
                    last = float(marked.set_index("id").loc[close_id, "last"])
                    ta.close_paper_trade(progress, int(close_id), last)
                    _save(progress)
                    st.rerun()
            st.caption("Marked on daily closes: a close beyond the stop or target closes the trade at that close. "
                       "Paper only; R multiple = P&L ÷ the risk taken at entry.")

    with history_tab:
        st.markdown("Every 5 trading days in the saved history, each rule was applied with data up to that day "
                    f"and the next {ta.HORIZON} days were measured, after 10 bp of costs each way. Historical "
                    "research on a short sample, not a forecast.")
        st.dataframe(backtest.rename(columns={"setup": "Setup", "direction": "Direction", "signals": "Signals",
                                              "hit_rate": "Hit rate", "avg_return": "Average return",
                                              "avg_r": "Average R"}),
                     hide_index=True, width="stretch",
                     column_config={"Hit rate": st.column_config.NumberColumn(format="percent"),
                                    "Average return": st.column_config.NumberColumn(format="percent"),
                                    "Average R": st.column_config.NumberColumn(format="%.2f")})
        st.caption("Why this matters: a rule that sounds right can still lose money after costs. Professionals "
                   "test rules out of sample, with costs, before risking capital — and re-test as regimes change.")

    with scan_tab:
        cls = st.multiselect("Asset class", sorted(table["asset_class"].unique()), key="td-classes")
        view = table[table["asset_class"].isin(cls)] if cls else table
        st.dataframe(view[["symbol", "name", "asset_class", "setup", "direction", "conviction", "price", "vs_200d",
                           "rsi14", "ret_1m", "ret_3m", "vol20"]].rename(columns={
            "symbol": "Symbol", "name": "Name", "asset_class": "Asset class", "setup": "Setup",
            "direction": "Direction", "conviction": "Conviction", "price": "Price", "vs_200d": "vs 200-day",
            "rsi14": "RSI (14)", "ret_1m": "1-month return", "ret_3m": "3-month return", "vol20": "Volatility (20d)"}),
            hide_index=True, width="stretch",
            column_config={"Price": st.column_config.NumberColumn(format="%.4g"),
                           "vs 200-day": st.column_config.NumberColumn(format="percent"),
                           "RSI (14)": st.column_config.NumberColumn(format="%.0f"),
                           "1-month return": st.column_config.NumberColumn(format="percent"),
                           "3-month return": st.column_config.NumberColumn(format="percent"),
                           "Volatility (20d)": st.column_config.NumberColumn(format="percent")})
