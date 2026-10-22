"""
US | India market switch. The two markets are kept separate: each has its own
data files, benchmark, volatility gauge, currency and pages. Pages that do not
yet have an India version are hidden while India is selected.
"""

from __future__ import annotations

from typing import List, Optional

import streamlit as st


MARKETS = ["US", "India"]
INDIA_PAGES: List[str] = ["Home", "Markets", "Trading Desk", "Guide", "Job Tracker", "Academy", "System"]


def current() -> str:
    return st.session_state.get("market") or "US"


def allowed_pages(market: Optional[str] = None) -> Optional[List[str]]:
    """None means every page; India shows only pages with India data."""
    return INDIA_PAGES if (market or current()) == "India" else None


def _on_change() -> None:
    pages = allowed_pages()
    if pages is not None and st.session_state.get("nav") not in pages:
        st.session_state["nav"] = "Markets"


def render_switch() -> str:
    st.session_state.setdefault("market", "US")
    st.radio("Market", MARKETS, key="market", horizontal=True, on_change=_on_change,
             help="US and India are kept separate: each has its own data, benchmark and currency.")
    return current()
