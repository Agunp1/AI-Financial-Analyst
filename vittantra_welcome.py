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


def _start_step(index: int) -> None:
    st.session_state["nav"] = "Job Tracker"
    st.session_state["trk-step"] = index


def _today_panel(user: str) -> None:
    """Today's three Job Tracker steps with a Start button each."""
    try:
        import academy_desk as desk
        import job_tracker as jt
        from academy_content import ROLES
        path = cloud.progress_path()
        progress = desk.load_progress(path) if path else {}
        plan = jt.daily_plan(progress)
    except Exception:
        return
    st.markdown(f"**Today · {ROLES[plan['role']]['title'].split(' (')[0]} desk** — {plan['done']} of 3 done")
    cols = st.columns(3)
    for i, (col, step) in enumerate(zip(cols, plan["steps"])):
        with col.container(border=True):
            st.markdown(f"{'✓' if step['done'] else '○'} **{step['step']}** · {step['minutes']} min")
            st.markdown(step["what"])
            if step.get("why"):
                st.caption(f"Why: {step['why']}")
            if not step["done"]:
                st.button("Start", key=f"welcome-start-{i}", on_click=_start_step, args=(i,), width="stretch",
                          type="primary" if i == next(j for j, s in enumerate(plan["steps"]) if not s["done"])
                          else "secondary")


def render_visitor_welcome() -> None:
    """Welcome card with sign-in for visitors on the online app."""
    with st.container(border=True):
        left, right = st.columns([3, 2], gap="large")
        with left:
            st.markdown(f"## {greeting()}, welcome to Vittantra")
            st.markdown("An investment research and portfolio platform on live public data, built to practise the "
                        "real work of each desk:")
            st.markdown("- **Markets and economy** — US and India, refreshed through the day\n"
                        "- **Research** — a valuation note on any US company in seconds\n"
                        "- **Agents** — seven AI analysts draft the work; you review and decide\n"
                        "- **Training** — daily desk tasks and CFA Level II practice, with a record of your work")
            st.caption("Explore freely. Sign in to save your work.")
        with right:
            st.markdown("#### Sign in")
            cloud.sign_in_form("home")


def render_welcome() -> None:
    """Top of Home: a welcome and sign-in for visitors; a greeting, today's plan and training for signed-in people."""
    user = cloud.current_user() if cloud.cloud_mode() else ("owner" if cloud.is_owner() else None)
    if not user:
        if cloud.cloud_mode():
            render_visitor_welcome()
        return
    name = display_name(user)
    today = datetime.now()
    with st.container(border=True):
        st.markdown(f"## {greeting()}, {name}")
        st.caption(f"{today:%A %d %B %Y}")
        if user != "owner" and not cloud.progress_path().exists() and not briefing_has_portfolio(user):
            st.markdown("Getting started: take the guided training below, or open **Job Tracker** for today's plan.")
        else:
            st.markdown("  \n".join(briefing(user)))
        _today_panel(user)
    import vittantra_coach
    vittantra_coach.home_card(st.session_state.get("vt_labels", {}))


def briefing_has_portfolio(user: str) -> bool:
    try:
        import my_portfolio as mp
        return bool(mp.load(user).get("holdings"))
    except Exception:
        return False
