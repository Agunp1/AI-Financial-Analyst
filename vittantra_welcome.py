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


def _go(page: str) -> None:
    st.session_state["nav"] = page


def _tick(item_id: str, training: bool) -> None:
    import academy_desk as desk
    import daily_checklist as dc
    import vittantra_coach as coach
    path = cloud.progress_path()
    if path is None:
        return
    progress = desk.load_progress(path)
    if training:
        coach.mark_done(progress, item_id)
    else:
        dc.tick(progress, item_id)
    from vittantra_academy_page import _save
    _save(progress)


@st.cache_data(ttl=900, show_spinner=False)
def _snapshot(stamp: str) -> list:
    import daily_checklist as dc
    try:
        return dc.market_snapshot()
    except Exception:
        return []


def _checklist_panel(user: str) -> None:
    """Today's checklist: market & economy check, then training steps or the Job Tracker's three steps."""
    try:
        import academy_desk as desk
        import daily_checklist as dc
        path = cloud.progress_path()
        progress = desk.load_progress(path) if path else {}
        items = dc.checklist(progress)
    except Exception:
        return
    s = dc.summary(items)
    st.markdown(f"#### Today's checklist · {s['done']} of {s['total']} done")
    st.progress(s["done"] / s["total"], text=(f"About {s['minutes_left']} min left of {s['minutes']}"
                                              if s["minutes_left"] else "All done for today"))
    stamp_path = cloud.BASE_DIR / "day75_refresh_stamp.csv"
    snapshot = _snapshot(stamp_path.read_text() if stamp_path.exists() else "")
    for item in items:
        with st.container(border=True):
            c1, c2, c3 = st.columns([7, 1.4, 1.2], vertical_alignment="center")
            with c1:
                st.markdown(f"{'✓' if item['done'] else '○'} **{item['title']}** · {item['minutes']} min — "
                            f"{item['what']}")
                if item.get("why"):
                    st.caption(f"Why: {item['why']}")
            if not item["done"]:
                if "tracker_step" in item:
                    c2.button("Do it", key=f"chk-go-{item['id']}", on_click=_start_step,
                              args=(item["tracker_step"],), width="stretch", type="primary")
                    c3.caption("Ticks itself when saved")
                else:
                    if item["id"] != dc.MARKET_CHECK:
                        c2.button("Do it", key=f"chk-go-{item['id']}", on_click=_go, args=(item["page"],),
                                  width="stretch")
                    c3.button("Done", key=f"chk-done-{item['id']}", on_click=_tick,
                              args=(item["id"], bool(item.get("training"))), width="stretch", type="primary")
            if item["id"] == dc.MARKET_CHECK:
                if snapshot:
                    left, right = st.columns(2)
                    half = (len(snapshot) + 1) // 2
                    for col, rows in ((left, snapshot[:half]), (right, snapshot[half:])):
                        col.markdown("  \n".join(f"**{r['section']}** · {r['text']}" for r in rows))
                    st.caption("From the Investment Analyst agent (every line cites its source on Agent Desk). "
                               "Prices ~15 min delayed; economic data as of the last release.")
                else:
                    st.caption("Market data is not available yet; open Markets after the next refresh.")
    missed = dc.yesterday_open(progress)
    if missed:
        st.caption("Left open yesterday: " + ", ".join(missed) + ". Not added to today — work never piles up.")


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
        _checklist_panel(user)
    import vittantra_coach
    try:
        import academy_desk as desk
        path = cloud.progress_path()
        progress = desk.load_progress(path) if path else {}
        training_active = vittantra_coach.day_for_today(progress) is not None
    except Exception:
        training_active = False
    if not training_active:                       # while training runs its steps are in the checklist above
        vittantra_coach.home_card(st.session_state.get("vt_labels", {}))


def briefing_has_portfolio(user: str) -> bool:
    try:
        import my_portfolio as mp
        return bool(mp.load(user).get("holdings"))
    except Exception:
        return False
