"""
Application chrome: grouped navigation and the top bar with a market ticker,
in the style of professional platforms (terse, data-first, no decoration).
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Tuple

import pandas as pd
import streamlit as st

import vittantra_theme as vt


BASE_DIR = Path(__file__).resolve().parent

NAV_GROUPS: List[Tuple[str, List[str]]] = [
    ("Overview", ["Home", "My Portfolio"]),
    ("Research & Markets", ["Markets", "Research"]),
    ("Portfolio & Risk", ["Portfolio Manager", "Command Center", "Risk Intelligence", "Portfolio", "Governance",
                          "Remediation"]),
    ("Clients", ["Advisory"]),
    ("Tools", ["Copilot", "AI Analyst"]),
    ("Learn", ["Guide", "Academy"]),
    ("System", ["System"]),
]

TICKER: List[Tuple[str, str, str]] = [            # symbol, label, kind
    ("SPY", "S&P 500", "pct"), ("QQQ", "Nasdaq 100", "pct"), ("IWM", "Russell 2000", "pct"),
    ("EFA", "Intl Dev", "pct"), ("DGS10", "UST 10Y", "yield"), ("DX-Y.NYB", "DXY", "pct"),
    ("EURUSD=X", "EUR/USD", "pct"), ("GC=F", "Gold", "pct"), ("CL=F", "WTI", "pct"),
    ("BTC-USD", "Bitcoin", "pct"), ("^VIX", "VIX", "pct"),
]


def _go(page: str) -> None:
    st.session_state["nav"] = page


def render_nav(labels: Dict[str, str]) -> str:
    """Grouped navigation in the sidebar; returns the current page."""
    st.session_state.setdefault("nav", "Home")
    current = st.session_state["nav"]
    st.markdown('<div class="vt-brand">VITTANTRA</div>', unsafe_allow_html=True)
    for section, pages in NAV_GROUPS:
        st.markdown(f'<div class="vt-nav-section">{section}</div>', unsafe_allow_html=True)
        for page in pages:
            st.button(labels.get(page, page), key=f"nav-{page}", on_click=_go, args=(page,), width="stretch",
                      type="primary" if page == current else "tertiary")
    return current


def _quote(row, kind: str) -> Tuple[str, str]:
    price, move = row.get("price"), row.get("return_1d")
    if kind == "yield":
        return (f"{price:.2f}%" if pd.notna(price) else "—"), ""
    if pd.isna(price):
        return "—", ""
    level = f"{price:,.0f}" if price >= 1000 else f"{price:,.2f}" if price >= 10 else f"{price:,.4f}"
    if pd.isna(move):
        return level, ""
    cls = "vt-up" if move >= 0 else "vt-down"
    return level, f'<span class="{cls}">{move:+.2%}</span>'


def render_topbar(page_label: str, refreshed: str = "") -> None:
    """Compact header (product | page | data time) and a ticker tape."""
    path = BASE_DIR / "day76c_asset_analytics.csv"
    items = []
    if path.exists():
        data = pd.read_csv(path).set_index("symbol")
        for symbol, label, kind in TICKER:
            if symbol in data.index:
                level, change = _quote(data.loc[symbol], kind)
                items.append(f'<span class="vt-tick"><span class="vt-tick-label">{label}</span> '
                             f'<span class="vt-tick-level">{level}</span> {change}</span>')
    st.markdown(
        f'<div class="vt-topbar"><span class="vt-topbar-brand">VITTANTRA</span>'
        f'<span class="vt-topbar-sep">/</span><span class="vt-topbar-page">{page_label}</span>'
        f'<span class="vt-topbar-time">{refreshed}</span></div>'
        + (f'<div class="vt-tape">{"".join(items)}</div>' if items else ""),
        unsafe_allow_html=True)


def css() -> str:
    """Styles for the chrome, from the theme palette."""
    return f"""
    <style>
    .vt-brand {{ font-family: "Source Serif 4", Georgia, serif; font-weight: 700; letter-spacing: 0.28em;
                 color: {vt.BRASS}; font-size: 1.05rem; padding: 0.2rem 0 0.6rem 0.35rem; }}
    .vt-nav-section {{ display: block; height: 1.0rem; color: {vt.MUTED}; font-size: 0.68rem; letter-spacing: 0.14em;
                       text-transform: uppercase; margin: 0.9rem 0 0.35rem 0.35rem; line-height: 1.0rem; }}
    section[data-testid="stSidebar"] [data-testid="stMarkdownContainer"]:has(.vt-nav-section),
    section[data-testid="stSidebar"] [data-testid="stMarkdownContainer"]:has(.vt-brand) {{ margin-bottom: 0 !important; }}
    section[data-testid="stSidebar"] [data-testid="stVerticalBlock"] {{ gap: 0.2rem; }}
    section[data-testid="stSidebar"] .stButton button {{ justify-content: flex-start; text-align: left;
                       padding: 0.2rem 0.7rem; min-height: 1.85rem; font-size: 0.88rem; border-radius: 3px;
                       border: none; border-left: 3px solid transparent; background: transparent; color: {vt.INK}; }}
    section[data-testid="stSidebar"] .stButton button div {{ justify-content: flex-start; }}
    section[data-testid="stSidebar"] .stButton button p {{ text-align: left; }}
    section[data-testid="stSidebar"] .stButton button:hover {{ background: {vt.PAPER}; color: {vt.BRASS}; }}
    section[data-testid="stSidebar"] .stButton button[data-testid="stBaseButton-primary"],
    section[data-testid="stSidebar"] .stButton button[kind="primary"] {{ border-left: 3px solid {vt.BRASS};
                       background: {vt.PAPER}; color: {vt.BRASS}; font-weight: 600; }}
    .vt-topbar {{ display: flex; align-items: baseline; gap: 0.6rem; border-bottom: 1px solid {vt.LINE};
                  padding: 0.1rem 0 0.45rem 0; margin-bottom: 0.35rem; }}
    .vt-topbar-brand {{ font-family: "Source Serif 4", Georgia, serif; letter-spacing: 0.22em; color: {vt.BRASS};
                        font-weight: 700; font-size: 0.85rem; }}
    .vt-topbar-sep {{ color: {vt.MUTED}; }}
    .vt-topbar-page {{ color: {vt.INK}; font-weight: 600; font-size: 0.95rem; }}
    .vt-topbar-time {{ margin-left: auto; color: {vt.MUTED}; font-size: 0.75rem; font-family: "IBM Plex Mono",
                       monospace; }}
    .vt-tape {{ display: flex; flex-wrap: wrap; gap: 0.25rem 1.2rem; padding: 0.35rem 0 0.6rem 0;
                border-bottom: 1px solid {vt.LINE}; margin-bottom: 0.9rem; font-family: "IBM Plex Mono", monospace;
                font-size: 0.78rem; }}
    .vt-tick-label {{ color: {vt.MUTED}; }}
    .vt-tick-level {{ color: {vt.INK}; }}
    .vt-lede {{ color: {vt.MUTED}; font-size: 1.02rem; max-width: 60rem; margin: 0.2rem 0 1rem 0; }}
    .vt-up {{ color: {vt.POSITIVE}; }}
    .vt-down {{ color: {vt.NEGATIVE}; }}
    </style>
    """
