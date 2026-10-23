"""
Daily checklist for Home: everything for today in one list, ticked as it is
done, within an hour.

  1. Market & economy check (5 min) — always first; ticked by the person
  2. Training day steps (while the 4-week training runs), or
     the Job Tracker's three steps: desk duty, CFA Level II item set, lesson

Desk, CFA and lesson items tick themselves from the saved work record; the
market check and training steps are ticked with a button. Items not done stay
open for the rest of the day; yesterday's open items are listed for
information only — they are never added to today, so work does not pile up.
Pure functions; no Streamlit.
"""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path
from typing import List, Optional

import job_tracker as jt
import vittantra_coach as coach


MARKET_CHECK = "market"
MARKET_MINUTES = 5


def _log(progress: dict) -> dict:
    return progress.setdefault("daily_log", {})


def tick(progress: dict, item_id: str, day: Optional[date] = None) -> None:
    items = _log(progress).setdefault((day or date.today()).isoformat(), [])
    if item_id not in items:
        items.append(item_id)


def ticked(progress: dict, day: date) -> set:
    return set((progress.get("daily_log") or {}).get(day.isoformat(), []))


def checklist(progress: dict, day: Optional[date] = None) -> List[dict]:
    """Today's items: id, title, what, page, minutes, why, done, auto (ticks itself)."""
    day = day or date.today()
    manual = ticked(progress, day)
    items = [{"id": MARKET_CHECK, "title": "Market & economy check", "page": "Markets", "minutes": MARKET_MINUTES,
              "what": "Read the snapshot below (regime, stocks, rates, credit, inflation, jobs, next event).",
              "why": "Every desk starts the day knowing what moved and what is coming; interviewers ask about it.",
              "done": MARKET_CHECK in manual, "auto": False}]
    training_day = coach.day_for_today(progress, day)
    if training_day is not None:
        done = set((progress.get("training") or {}).get("done", []))
        for i, (page, text, minutes, why) in enumerate(coach.TRAINING[training_day]["steps"]):
            sid = coach.step_id(training_day, i)
            items.append({"id": sid, "title": f"Training · Day {training_day + 1}, step {i + 1}", "page": page,
                          "what": text, "minutes": minutes, "why": why, "done": sid in done, "auto": False,
                          "training": True})
        return items
    plan = jt.daily_plan(progress, day)
    for key, step, page in (("desk", plan["steps"][0], "Job Tracker"), ("cfa", plan["steps"][1], "Job Tracker"),
                            ("lesson", plan["steps"][2], "Job Tracker")):
        items.append({"id": key, "title": step["step"], "page": page, "what": step["what"], "minutes": step["minutes"],
                      "why": step.get("why", ""), "done": step["done"], "auto": True,
                      "tracker_step": ["desk", "cfa", "lesson"].index(key)})
    return items


def summary(items: List[dict]) -> dict:
    done = sum(i["done"] for i in items)
    return {"done": done, "total": len(items), "minutes": sum(i["minutes"] for i in items),
            "minutes_left": sum(i["minutes"] for i in items if not i["done"])}


def yesterday_open(progress: dict, today: Optional[date] = None) -> List[str]:
    """Titles of yesterday's items left open (information only; never carried into today)."""
    yesterday = (today or date.today()) - timedelta(days=1)
    t = progress.get("training") or {}
    if t.get("started") and date.fromisoformat(t["started"]) > yesterday:
        return []                                         # training began today: nothing to report
    if not any(d < (today or date.today()).isoformat() for d in (progress.get("daily_log") or {})):
        return []                                         # has not used the checklist before today
    items = checklist(progress, yesterday)
    return [i["title"] for i in items if not i["done"] and not i.get("training")]


# ==============================================================
# MARKET & ECONOMY SNAPSHOT (from the Investment Analyst agent's cited findings)
# ==============================================================

SNAPSHOT_FIELDS = [("Regime", None), ("Markets", "SPY.return_1d"), ("Markets", "QQQ.return_1d"),
                   ("Rates", "10Y.yield_pct"), ("Rates", "slope_3m10y_bp"), ("Credit", "US high yield.spread_bp"),
                   ("Economy", "CPIAUCSL.latest"), ("Economy", "UNRATE.latest"), ("Economy", "FEDFUNDS.latest"),
                   ("What to watch", None)]


def market_snapshot(base: Optional[Path] = None) -> List[dict]:
    """A dozen cited lines on the market and the economy; empty if the data is missing."""
    import analyst_agents as aa
    run = aa.investment_analyst(base or aa.BASE_DIR)
    out = []
    for section, field in SNAPSHOT_FIELDS:
        for f in run.sections.get(section, []):
            if field is None or f.field == field:
                out.append({"section": section, "text": f.text, "source": f.source, "field": f.field})
                break
    for f in run.sections.get("What it means", [])[:3]:
        out.append({"section": "What it means", "text": f.text, "source": f.source, "field": f.field})
    return out
