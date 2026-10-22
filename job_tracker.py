"""
Job Tracker — a daily plan across every desk and a CFA Level II routine.

Each day has three small steps (about 45 minutes in total):

1. Desk duty     — one real task for the role of the day (the six roles rotate
                   Monday to Saturday; Sunday goes to the weakest role).
2. CFA L2 step   — one item set in the topic area where accuracy is lowest.
3. Lesson        — the next unread lesson for the role of the day.

The plan for a day is built only from work done *before* that day, so it does
not change while you work through it. The readiness scorecard shows, per role,
which responsibilities have graded evidence (a score of 70 or more) — the
evidence an interviewer can ask about. Pure functions; no Streamlit.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Dict, List, Optional

import academy_cfa as cfa
from academy_content import LESSONS, ROLES


PASS_SCORE = 70
ROLE_ORDER = list(ROLES)                     # Monday … Saturday
CFA_TASK_PREFIX = "CFA L2 item set: "

# Responsibilities per role and the recorded task names that evidence them
# (prefix match on the Work Desk / item-set record).
RESPONSIBILITIES: Dict[str, List[dict]] = {
    "investment_analyst": [
        {"name": "Morning market brief", "desk": True, "prefixes": ["Morning market brief"]},
        {"name": "Read economic data and surprises", "prefixes": [CFA_TASK_PREFIX + "Reading an inflation surprise"]},
        {"name": "Macro factor analysis", "prefixes": [CFA_TASK_PREFIX + "Macro factor sensitivities"]},
        {"name": "Currencies and parity", "prefixes": [CFA_TASK_PREFIX + "Currency exchange rates and parity"]},
    ],
    "equity_researcher": [
        {"name": "Company tear sheet", "desk": True, "prefixes": ["Company tear sheet"]},
        {"name": "Valuation call", "desk": True, "prefixes": ["Valuation call"]},
        {"name": "Ratio analysis (DuPont)", "prefixes": [CFA_TASK_PREFIX + "Valuation and DuPont"]},
        {"name": "Cash-flow and residual-income valuation",
         "prefixes": [CFA_TASK_PREFIX + "Free cash flow and residual income"]},
        {"name": "Testing a factor (regression)", "prefixes": [CFA_TASK_PREFIX + "Multiple regression"]},
    ],
    "portfolio_analyst": [
        {"name": "Daily risk check and escalation", "desk": True, "prefixes": ["Daily risk check"]},
        {"name": "Stress testing", "desk": True, "prefixes": ["Stress question"]},
        {"name": "VaR and backtesting", "prefixes": [CFA_TASK_PREFIX + "Measuring and backtesting market risk"]},
        {"name": "Rate risk (duration, convexity)", "prefixes": [CFA_TASK_PREFIX + "Duration, convexity"]},
        {"name": "Risk contributions", "prefixes": [CFA_TASK_PREFIX + "Risk contributions and stress tests"]},
    ],
    "portfolio_manager": [
        {"name": "Rebalance proposal within limits", "desk": True, "prefixes": ["Rebalance proposal"]},
        {"name": "Active management (IR, breadth)", "prefixes": [CFA_TASK_PREFIX + "Active management"]},
        {"name": "Option valuation and hedging", "prefixes": [CFA_TASK_PREFIX + "Option valuation and parity"]},
        {"name": "Risk contributions and stress", "prefixes": [CFA_TASK_PREFIX + "Risk contributions and stress tests"]},
    ],
    "advisor": [
        {"name": "Client meeting and allocation", "desk": True, "prefixes": ["Client meeting"]},
        {"name": "Suitability and goals planning", "prefixes": [CFA_TASK_PREFIX + "Suitability and goals-based"]},
        {"name": "Real estate for clients", "prefixes": [CFA_TASK_PREFIX + "Commercial real estate"]},
        {"name": "Explaining market risk", "prefixes": [CFA_TASK_PREFIX + "Measuring and backtesting market risk"]},
    ],
    "private_markets_analyst": [
        {"name": "Deal flow screening", "desk": True, "prefixes": ["Deal flow screen"]},
        {"name": "Term sheet and dilution", "desk": True, "prefixes": ["Term sheet"]},
        {"name": "LBO returns", "desk": True, "prefixes": ["Quick LBO"]},
        {"name": "Interview answers", "desk": True, "prefixes": ["Mock interview"]},
        {"name": "VC method and fund maths", "prefixes": [CFA_TASK_PREFIX + "Venture capital method"]},
    ],
}

# Approximate Level II topic weights (CFA Institute ranges; check the current
# curriculum — they change). Used only to break ties between weak topics.
CFA_WEIGHTS = {
    "Ethical and Professional Standards": "10–15%", "Quantitative Methods": "5–10%", "Economics": "5–10%",
    "Financial Statement Analysis": "10–15%", "Corporate Issuers": "5–10%", "Equity Valuation": "10–15%",
    "Fixed Income": "10–15%", "Derivatives": "5–10%", "Alternative Investments": "5–10%",
    "Portfolio Management": "10–15%",
}

# Topic of each item set (matches the item set's own "topic"; checked by tests).
ITEM_SET_TOPIC = {
    "fixed_income": "Fixed Income", "derivatives": "Derivatives", "portfolio_risk": "Portfolio Management",
    "economics_fx": "Economics", "equity": "Equity Valuation", "quant": "Quantitative Methods",
    "real_estate": "Alternative Investments", "macro": "Economics", "equity_valuation": "Equity Valuation",
    "news_surprise": "Economics", "active_management": "Portfolio Management", "advisory": "Portfolio Management",
    "private_equity": "Alternative Investments", "stress_testing": "Portfolio Management",
}


def _day(value) -> Optional[date]:
    try:
        return datetime.fromisoformat(str(value)).date()
    except ValueError:
        return None


def _matches(record: dict, role: str, item: dict) -> bool:
    task = str(record.get("task", ""))
    if not any(task.startswith(p) for p in item["prefixes"]):
        return False
    # Desk tasks belong to their role; an item set counts for every role that lists it.
    return record.get("role") == role or task.startswith(CFA_TASK_PREFIX)


def records_before(progress: dict, day: date) -> List[dict]:
    return [r for r in progress.get("records", []) if (_day(r.get("time")) or day) < day]


def records_on(progress: dict, day: date) -> List[dict]:
    return [r for r in progress.get("records", []) if _day(r.get("time")) == day]


def lessons_on(progress: dict, day: date) -> List[str]:
    return [e["id"] for e in progress.get("lesson_log", []) if _day(e.get("date")) == day]


def responsibility_status(progress: dict, role: str, records: Optional[List[dict]] = None) -> List[dict]:
    """One row per responsibility: times done, best score, last date, status."""
    records = progress.get("records", []) if records is None else records
    rows = []
    for item in RESPONSIBILITIES[role]:
        done = [r for r in records if _matches(r, role, item)]
        best = max((float(r.get("score", 0)) for r in done), default=None)
        last = max((_day(r.get("time")) for r in done if _day(r.get("time"))), default=None)
        status = ("Not started" if not done else "Demonstrated" if best >= PASS_SCORE else "In progress")
        rows.append({"responsibility": item["name"], "desk": bool(item.get("desk")), "times_done": len(done),
                     "best_score": best, "last_done": last, "status": status})
    return rows


def readiness(progress: dict, role: str, records: Optional[List[dict]] = None) -> float:
    rows = responsibility_status(progress, role, records)
    return sum(r["status"] == "Demonstrated" for r in rows) / len(rows)


def role_of_the_day(progress: dict, day: date) -> str:
    """Monday–Saturday rotate through the six roles; Sunday is for the weakest role."""
    if day.weekday() < 6:
        return ROLE_ORDER[day.weekday()]
    before = records_before(progress, day)
    return min(ROLE_ORDER, key=lambda r: (readiness(progress, r, before), ROLE_ORDER.index(r)))


def _next_duty(progress: dict, role: str, day: date) -> dict:
    """The desk responsibility to do next: never done first, then the weakest, then the oldest."""
    rows = [r for r in responsibility_status(progress, role, records_before(progress, day)) if r["desk"]]
    order = {"Not started": 0, "In progress": 1, "Demonstrated": 2}
    return min(rows, key=lambda r: (order[r["status"]], r["best_score"] or 0, r["last_done"] or date.min))


def cfa_focus(progress: dict, day: Optional[date] = None) -> List[dict]:
    """Topics with an item set in Vittantra, weakest first (accuracy, then fewest answered)."""
    stats = progress.get("cfa", {})
    rows = []
    for topic in sorted(set(ITEM_SET_TOPIC.values())):
        s = stats.get(topic, {"answered": 0, "correct": 0})
        accuracy = s["correct"] / s["answered"] if s["answered"] else None
        rows.append({"topic": topic, "answered": s["answered"], "accuracy": accuracy,
                     "weight": CFA_WEIGHTS.get(topic, "")})
    return sorted(rows, key=lambda r: (r["accuracy"] if r["accuracy"] is not None else -1, r["answered"],
                                       -int(r["weight"].split("–")[-1].rstrip("%") or 0)))


def _cfa_stats_before(progress: dict, day: date) -> dict:
    """CFA accuracy from records before `day` (so today's plan stays put while you work)."""
    stats: Dict[str, dict] = {}
    for r in records_before(progress, day):
        task = str(r.get("task", ""))
        if not task.startswith(CFA_TASK_PREFIX):
            continue
        answers = r.get("answer", {}) or {}
        total = len(answers) or 1
        correct = round(float(r.get("score", 0)) / 100 * total)
        topic = next((ITEM_SET_TOPIC[k] for k, t in _TITLE_PREFIX.items()
                                          if task[len(CFA_TASK_PREFIX):].startswith(t)), None)
        if topic:
            s = stats.setdefault(topic, {"answered": 0, "correct": 0})
            s["answered"] += total
            s["correct"] += correct
    return stats


# Title prefix of each item set (for reading old records back to a topic).
_TITLE_PREFIX = {
    "fixed_income": "Duration, convexity", "derivatives": "Option valuation", "portfolio_risk": "Measuring and backtesting",
    "economics_fx": "Currency exchange", "equity": "Valuation and DuPont", "quant": "Multiple regression",
    "real_estate": "Commercial real estate", "macro": "Macro factor", "equity_valuation": "Free cash flow",
    "news_surprise": "Reading an inflation", "active_management": "Active management", "advisory": "Suitability",
    "private_equity": "Venture capital", "stress_testing": "Risk contributions",
}


def cfa_item_key(progress: dict, day: date) -> str:
    """Item set for today: the weakest topic (as of the start of the day), rotating within the topic."""
    focus = cfa_focus({"cfa": _cfa_stats_before(progress, day)})
    topic = focus[0]["topic"]
    keys = sorted(k for k, t in ITEM_SET_TOPIC.items() if t == topic)
    return keys[day.toordinal() % len(keys)]


def next_lesson(progress: dict, role: str, day: date) -> Optional[dict]:
    """First lesson of the role not learned before today (or the one learned today)."""
    today = set(lessons_on(progress, day))
    learned_before = set(progress.get("lessons_read", [])) - today
    for lesson in LESSONS:
        if lesson["role"] == role and lesson["id"] not in learned_before:
            return lesson
    return None


def daily_plan(progress: dict, day: Optional[date] = None) -> dict:
    """Today's three steps and whether each is done."""
    day = day or date.today()
    role = role_of_the_day(progress, day)
    today = records_on(progress, day)
    duty = _next_duty(progress, role, day)
    lesson = next_lesson(progress, role, day)
    steps = [
        {"step": "Desk duty", "what": duty["responsibility"], "role": role, "minutes": 20,
         "done": any(r.get("role") == role and not str(r.get("task", "")).startswith(CFA_TASK_PREFIX)
                     for r in today)},
        {"step": "CFA Level II", "what": ITEM_SET_TOPIC[cfa_item_key(progress, day)], "key": cfa_item_key(progress, day),
         "minutes": 15, "done": any(str(r.get("task", "")).startswith(CFA_TASK_PREFIX) for r in today)},
        {"step": "Lesson", "what": f"{lesson['id']} · {lesson['title']}" if lesson else "Review any lesson",
         "lesson": lesson["id"] if lesson else None, "minutes": 10, "done": bool(lessons_on(progress, day))},
    ]
    return {"day": day, "role": role, "steps": steps, "done": sum(s["done"] for s in steps)}


def active_days(progress: dict) -> set:
    days = {_day(r.get("time")) for r in progress.get("records", [])}
    days |= {_day(e.get("date")) for e in progress.get("lesson_log", [])}
    return {d for d in days if d}


def streak(progress: dict, day: Optional[date] = None) -> int:
    """Consecutive active days ending today (or yesterday, if nothing is done yet today)."""
    day = day or date.today()
    days = active_days(progress)
    current = day if day in days else day - timedelta(days=1)
    count = 0
    while current in days:
        count += 1
        current -= timedelta(days=1)
    return count


def week_summary(progress: dict, day: Optional[date] = None) -> dict:
    day = day or date.today()
    start = day - timedelta(days=6)
    recent = [r for r in progress.get("records", []) if start <= (_day(r.get("time")) or date.min) <= day]
    lessons = [e for e in progress.get("lesson_log", []) if start <= (_day(e.get("date")) or date.min) <= day]
    roles = {r.get("role") for r in recent if not str(r.get("task", "")).startswith(CFA_TASK_PREFIX)}
    cfa_sets = [r for r in recent if str(r.get("task", "")).startswith(CFA_TASK_PREFIX)]
    return {"active_days": len({d for d in active_days(progress) if start <= d <= day}),
            "tasks": len(recent) - len(cfa_sets), "cfa_sets": len(cfa_sets), "lessons": len(lessons),
            "roles": len(roles)}


def log_lesson(progress: dict, lesson_id: str, when: Optional[datetime] = None) -> dict:
    progress.setdefault("lesson_log", []).append(
        {"id": lesson_id, "date": (when or datetime.now()).isoformat(timespec="minutes")})
    return progress


def days_to_exam(progress: dict, day: Optional[date] = None) -> Optional[int]:
    exam = (progress.get("tracker") or {}).get("cfa_exam")
    exam_day = _day(exam) if exam else None
    return (exam_day - (day or date.today())).days if exam_day else None


def evidence_pack(progress: dict, day: Optional[date] = None) -> str:
    """Markdown for interviews: readiness per role, best work per responsibility, CFA accuracy."""
    day = day or date.today()
    lines = ["# Vittantra — candidate evidence pack", "",
             f"Prepared {day:%d %B %Y}. Work done on live public data in Vittantra (research and education; "
             "no real money or clients).", "",
             f"Current streak: {streak(progress, day)} day(s) · last 7 days: "
             f"{week_summary(progress, day)['tasks']} desk task(s), {week_summary(progress, day)['cfa_sets']} CFA "
             f"item set(s).", ""]
    for role in ROLE_ORDER:
        rows = responsibility_status(progress, role)
        lines += [f"## {ROLES[role]['title']} — readiness {readiness(progress, role):.0%}", ""]
        for row in rows:
            mark = "✓" if row["status"] == "Demonstrated" else "·"
            best = f"best {row['best_score']:.0f}/100, done {row['times_done']}×" if row["times_done"] else "not yet"
            lines.append(f"- {mark} {row['responsibility']} — {best}")
        best_record = max((r for r in progress.get("records", []) if r.get("role") == role),
                          key=lambda r: float(r.get("score", 0)), default=None)
        if best_record:
            lines += ["", f"Best piece of work: **{best_record['task']}** ({best_record['score']}/100, "
                          f"{str(best_record['time'])[:10]})."]
        lines.append("")
    lines += ["## CFA Level II practice", ""]
    for row in cfa_focus(progress):
        acc = f"{row['accuracy']:.0%}" if row["accuracy"] is not None else "—"
        lines.append(f"- {row['topic']}: {row['answered']} question(s), accuracy {acc}")
    return "\n".join(lines)
