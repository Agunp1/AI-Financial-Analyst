"""
Personal welcome: a greeting on sign-in and a short briefing at the top of Home,
built only from the person's own saved work and Vittantra's data.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional
from zoneinfo import ZoneInfo

import pandas as pd
import streamlit as st

import vittantra_cloud as cloud


BASE_DIR = Path(__file__).resolve().parent


def display_name(user: Optional[str]) -> Optional[str]:
    """How to address the person: the owner's name from Secrets (default 'Arjun'), else their username."""
    if not user:
        return None
    if user == "owner":
        return cloud._secret("owner_name", "Arjun")
    return user


def greeting(now: Optional[datetime] = None) -> str:
    """Good morning / afternoon / evening in the viewer's own time zone (browser), UTC if unknown."""
    if now is None:
        try:
            zone = ZoneInfo(st.context.timezone) if st.context.timezone else timezone.utc
        except Exception:
            zone = timezone.utc
        now = datetime.now(zone)
    hour = now.hour
    return "Good morning" if 5 <= hour < 12 else "Good afternoon" if 12 <= hour < 18 else "Good evening"


def announce_sign_in(user: str, new_account: bool = False) -> None:
    """Remember to show a welcome toast on the next run (the sign-in reruns the page)."""
    name = display_name(user)
    st.session_state["vt_welcome"] = (f"Welcome to Vittantra, {name}." if new_account
                                      else f"Welcome back, {name}.")


def show_pending_toast() -> None:
    message = st.session_state.pop("vt_welcome", None)
    if message:
        st.toast(message)


def _market_line() -> Optional[str]:
    path = BASE_DIR / "day76c_asset_analytics.csv"
    if not path.exists():
        return None
    data = pd.read_csv(path).set_index("symbol")
    if "SPY" not in data.index or pd.isna(data.at["SPY", "return_1d"]):
        return None
    move = float(data.at["SPY", "return_1d"])
    return f"The S&P 500 {'rose' if move >= 0 else 'fell'} {abs(move):.1%} on the last trading day."


def briefing(user: str) -> List[str]:
    """Short personal points, each from the person's own saved work or Vittantra data."""
    points = []
    market = _market_line()
    if market:
        points.append("**Markets** · " + market)
    try:
        import my_portfolio as mp
        holdings = mp.load(user).get("holdings", [])
        data = mp.load(user)
        table = mp.universe()
        perf = mp.performance(data, table)
        if holdings and perf and perf["portfolio_return"] is not None:
            spy = f" vs S&P 500 {perf['spy_return']:+.1%}" if perf["spy_return"] is not None else ""
            points.append(f"**Portfolio** · {perf['portfolio_return']:+.1%} since {perf['since']}{spy}.")
        else:
            points.append(f"**Portfolio** · {len(holdings)} holding(s)." if holdings else
                          "**Portfolio** · Not set up — start from a model portfolio in My Portfolio.")
        for alert in mp.alerts(data.get("watchlist", []), table):
            points.append("**Alert** · " + alert["text"])
    except Exception:
        pass
    try:
        import academy_desk as desk
        path = cloud.progress_path()
        progress = desk.load_progress(path) if path else {}
        xp = sum(progress.get("xp", {}).values())
        level, nxt, needed = desk.level_for(xp)
        tasks = len(progress.get("records", []))
        points.append(f"**Academy** · {tasks} task(s), {xp} XP, level {level}"
                      + (f" ({needed} XP to {nxt})." if nxt else "."))
    except Exception:
        pass
    if user == "owner":
        try:
            from vittantra_approval_page import pending
            if pending():
                points.append("**Approvals** · 1 remediation proposal pending (Risk Overview).")
        except Exception:
            pass
    return points


def render_welcome() -> None:
    """Greeting card at the top of Home for a signed-in person."""
    user = cloud.current_user() if cloud.cloud_mode() else ("owner" if cloud.is_owner() else None)
    if not user:
        return
    name = display_name(user)
    with st.container(border=True):
        st.markdown(f"#### {greeting()}, {name}")
        if user != "owner" and not cloud.progress_path().exists() and not briefing_has_portfolio(user):
            st.markdown("Getting started\n"
                        "1. **Guide → A day on the desk** — the daily routine of each role.\n"
                        "2. **My Portfolio** — start from a model portfolio and review its risk.\n"
                        "3. **Academy → Work Desk** — today's task for one role, with a review.")
        else:
            st.markdown("  \n".join(briefing(user)))


def briefing_has_portfolio(user: str) -> bool:
    try:
        import my_portfolio as mp
        return bool(mp.load(user).get("holdings"))
    except Exception:
        return False
