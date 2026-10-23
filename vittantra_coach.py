"""
Training coach: a 4-week (28-day) guided programme that walks the owner (or any signed-in
person) through every desk, one click at a time. A slim banner on each page
shows the next step with "Take me there" and "Done"; Home shows the whole day.
Progress lives in the work record under "training". One training day unlocks
per calendar day so the habit builds daily.
"""

from __future__ import annotations

from datetime import date
from typing import Dict, List, Optional

import streamlit as st


# 28 days in four weeks; every day stays within an hour. Each step: (page, what to do, minutes, why it matters).
TRAINING: List[dict] = [
    # ---------------- Week 1 — find your way (guided tour of every desk) ----------------
    {"week": 1, "title": "Find your way around", "steps": [
        ("Home", "Read your greeting and today's plan at the top of Home.", 5,
         "Every desk starts the day with a plan; knowing where today's work is saves the first 15 minutes."),
        ("Job Tracker", "Open the 'CFA Level II plan' tab, pick your exam date and click 'Save exam date'.", 5,
         "Candidates plan backwards from the exam date so every topic is covered before final review."),
        ("Job Tracker", "Open the 'Today' tab and do step 1, the desk task.", 25,
         "Doing the real task, not reading about it, is what builds the experience you can talk about in interviews."),
        ("Guide", "Open the 'Navigation' tab and skim the map of every page.", 10,
         "A mental map of the tools is the first thing a new analyst builds; it makes every later task faster."),
    ]},
    {"week": 1, "title": "Think like an investment analyst", "steps": [
        ("Markets", "Open 'World Brief': what moved overnight and which headlines explain it.", 10,
         "Analysts must explain moves, not just report them; linking news to prices is the core of the morning call."),
        ("Agent Desk", "Pick 'Investment Analyst' and read the morning note. Switch on 'Show sources'.", 10,
         "Desks now get AI drafts; seeing the source of each number teaches you where the data lives."),
        ("Markets", "Check one number from the note here (for example the 10-year yield) — does it match?", 5,
         "Verifying before you repeat a number is a professional habit (and CFA Standard V(A): reasonable basis)."),
        ("Agent Desk", "Write your own call under 'Your review' and click 'Save review'.", 10,
         "Your value is the judgment on top of the data; writing a call forces you to take a view."),
        ("Job Tracker", "Do today's CFA Level II item set (step 2 on the 'Today' tab).", 15,
         "Level II is tested in vignette item sets; daily practice with live data builds speed and recall."),
    ]},
    {"week": 1, "title": "Research a company", "steps": [
        ("Research", "Open 'Valuation & reports', type a company you know (e.g. TSLA) and read the note.", 15,
         "Equity analysts start from what the price already assumes; the note shows value vs price and why."),
        ("Agent Desk", "Pick 'Equity Research', type the same ticker and compare the agent's note with yours.", 10,
         "Comparing two views trains you to spot what each one misses — the skill a senior reviewer looks for."),
        ("Academy", "Work Desk → 'Equity Research Analyst': do the company tear sheet and the valuation call.", 20,
         "A tear sheet and a valuation call are the junior analyst's daily outputs; you get graded like one."),
        ("Job Tracker", "Read today's lesson (step 3) and answer its interview questions out loud.", 10,
         "Saying answers out loud is how interview fluency is built; reading alone is not enough."),
    ]},
    {"week": 1, "title": "Trade with a plan", "steps": [
        ("Trading Desk", "Read the 'Agent brief': regime, top ideas and how the rules did historically.", 10,
         "Traders read the regime first because the same signal behaves differently in calm and volatile markets."),
        ("Trading Desk", "Open 'Ideas', pick one, read the chart and the reasons, then add it to your paper blotter.", 10,
         "A paper blotter builds a track record of decisions you can explain, without risking money."),
        ("Academy", "Work Desk → 'Trader': set a stop and size for the trade plan; send an execution report.", 20,
         "Sizing from the stop and measuring execution cost are what separate trading from gambling."),
        ("Job Tracker", "Do today's CFA Level II item set.", 15,
         "Consistency beats cramming: small daily sets keep every topic fresh."),
    ]},
    {"week": 1, "title": "Watch risk like a risk analyst", "steps": [
        ("Command Center", "Read the book status and alerts; if a remediation is pending, review it (you approve).", 10,
         "Risk analysts watch limits every morning; escalating early is cheaper than fixing a breach."),
        ("Risk Intelligence", "Look at VaR, stress scenarios and which positions drive the risk.", 15,
         "Weights hide risk; risk contributions and stress tests show where losses would really come from."),
        ("Agent Desk", "Pick 'Risk Analyst', read the report and save your review: escalate or not?", 10,
         "Deciding whether to escalate is the judgment call risk teams are hired for."),
        ("Academy", "Work Desk → 'Portfolio / Risk Analyst': do the daily risk check.", 15,
         "The daily risk check is the most common entry-level risk task; practising it makes it automatic."),
    ]},
    {"week": 1, "title": "Build and manage a portfolio", "steps": [
        ("Portfolio Manager", "Review the model portfolio: tracking error, biggest bets, sector tilts.", 15,
         "PMs are judged against a benchmark; tracking error and active bets show how far and where they deviate."),
        ("Agent Desk", "Pick 'Portfolio Manager', read the memo and save your review: what would you cut?", 10,
         "Deciding what to sell is harder than what to buy, and it is what investment committees ask about."),
        ("My Portfolio", "Build your own portfolio from a template and read its risk checks.", 15,
         "Building one yourself makes diversification, risk levels and suitability concrete."),
        ("Academy", "Work Desk → 'Portfolio Manager': write the rebalance proposal.", 15,
         "Rebalancing within turnover limits is a real trade-off between risk, return and cost."),
    ]},
    {"week": 1, "title": "PE/VC, your record and India", "steps": [
        ("Academy", "Work Desk → 'Private Equity / VC': screen the Monday deal flow.", 20,
         "Small funds see hundreds of companies to invest in a few; fast, fair screening is the core skill."),
        ("Job Tracker", "Open 'Readiness' to see which duties you have demonstrated; then 'Evidence pack'.", 10,
         "Interviewers ask for examples; the evidence pack turns your practice into concrete stories."),
        ("Markets", "Switch Market to 'India' in the sidebar and read India Markets; switch back to US after.", 15,
         "Comparing two markets (indices, rates, currency) sharpens your macro thinking for both."),
        ("Agent Desk", "Open 'Morning pack', prepare it and download it — your daily routine from now on.", 10,
         "Desk heads read a morning pack before the meeting; making it a habit is the point of week 1."),
    ]},
    # ---------------- Week 2 — the daily routine, with depth ----------------
    {"week": 2, "title": "Macro: read the economy like a strategist", "steps": [
        ("Agent Desk", "Morning pack: read the Investment Analyst note first (the desk's daily habit).", 5,
         "Starting every day the same way frees attention for what is actually new."),
        ("Markets", "'Macro & Economy': which indicator surprised most, and which asset classes react to it (macro betas)?", 15,
         "Markets move on surprises versus expectations; macro betas show which assets are exposed to each one."),
        ("Academy", "Work Desk → 'Investment Analyst': write the morning brief in 5 bullets.", 20,
         "Writing short is a skill: PMs read the first five lines and decide whether to read more."),
        ("Job Tracker", "CFA Level II item set.", 15, "Daily item sets keep exam topics fresh alongside the desk work."),
    ]},
    {"week": 2, "title": "Equity: compare two competitors", "steps": [
        ("Research", "Research two rivals (e.g. KO and PEP): valuation, growth, margins, rating.", 20,
         "Analysts cover sectors, not single stocks; relative value against peers is how calls are made."),
        ("Agent Desk", "Run 'Equity Research' on the one you prefer; note one claim you disagree with and why.", 10,
         "Disagreeing with evidence, not opinion, is what makes a research view credible."),
        ("Academy", "Work Desk → 'Equity Research Analyst': tear sheet on today's company.", 15,
         "Repetition on new companies builds the pattern recognition seniors rely on."),
        ("Job Tracker", "Lesson of the day + interview questions out loud.", 10,
         "Each lesson ties a formula to a real job task — the link interviewers test."),
    ]},
    {"week": 2, "title": "Trading: review your paper trades", "steps": [
        ("Trading Desk", "'Paper blotter': for each trade, was the stop or target hit? What is your average R?", 10,
         "Traders judge their process by average R over many trades, not by single wins or losses."),
        ("Trading Desk", "'Rule history': which setups made money after costs? Would you still take today's idea?", 10,
         "A rule without evidence is a guess; checking history after costs is basic professional hygiene."),
        ("Academy", "Work Desk → 'Trader': trade plan and execution report.", 20,
         "Planning the exit before the entry keeps every trade inside the desk's loss limits."),
        ("Job Tracker", "CFA Level II item set.", 15, "Keeps the exam routine going on trading-heavy days."),
    ]},
    {"week": 2, "title": "Risk: stress testing in depth", "steps": [
        ("Risk Intelligence", "Pick the worst stress scenario: which positions lose most and why?", 15,
         "Stress tests answer 'what if 2008 happened again?' — the question boards and regulators ask."),
        ("Portfolio Manager", "What-if: cut the biggest risk contributor by half — how do VaR and stress losses change?", 15,
         "Testing a fix before proposing it is how risk and PM teams work together."),
        ("Academy", "Work Desk → 'Portfolio / Risk Analyst': weekly stress question.", 10,
         "Identifying the worst scenario and its driver is a standard risk-analyst interview case."),
        ("Job Tracker", "CFA Level II item set.", 15, "Portfolio-management topics carry heavy exam weight."),
    ]},
    {"week": 2, "title": "PM: defend your portfolio", "steps": [
        ("Portfolio Manager", "Find one overweight that valuation calls expensive. Write two lines defending or cutting it.", 15,
         "Investment committees challenge every position; you must defend or change it with evidence."),
        ("Agent Desk", "'Portfolio Construction' review vs 'Portfolio Manager' memo: do they agree? Save a review.", 15,
         "Construction (the optimiser) and management (judgment) often disagree; resolving that is the PM's job."),
        ("Academy", "Work Desk → 'Portfolio Manager': rebalance proposal within the turnover limit.", 15,
         "Every trade costs money; good PMs get the most risk reduction per dollar traded."),
        ("Job Tracker", "Lesson of the day.", 10, "Builds the theory behind today's PM decisions."),
    ]},
    {"week": 2, "title": "PE/VC: term sheets and LBOs", "steps": [
        ("Academy", "Work Desk → 'Private Equity / VC' → 'Term sheet': post-money, ownership, exit value needed.", 20,
         "Ownership after dilution decides whether a deal can return the fund — the first thing partners check."),
        ("Academy", "'LBO' tab: MOIC and IRR; what drove the return — EBITDA growth, debt paydown or multiple?", 20,
         "PE interviews always include an LBO; knowing where returns come from shows real understanding."),
        ("Job Tracker", "CFA Level II item set (Alternative Investments if offered).", 15,
         "Private equity and real estate are Level II alternative-investment topics."),
    ]},
    {"week": 2, "title": "Weekly review", "steps": [
        ("Job Tracker", "'Readiness': which desk is weakest? Do one task on it today.", 30,
         "Improvement comes from working on weaknesses, not repeating strengths."),
        ("Job Tracker", "'CFA Level II plan': which topic is weakest? Do one extra item set in it.", 15,
         "The exam rewards breadth; your weakest topic costs the most points."),
        ("Job Tracker", "'Evidence pack': download it and read it as an interviewer would.", 10,
         "Seeing your record from the outside shows which stories you can already tell."),
    ]},
    # ---------------- Week 3 — interview-ready work products ----------------
    {"week": 3, "title": "Write a one-page market note", "steps": [
        ("Agent Desk", "Morning pack (10 minutes).", 10, "The routine you will run on any desk."),
        ("Markets", "Write a one-page note: three moves, why they happened, what to watch this week.", 30,
         "A written market note is a common case-study task in investment-analyst interviews."),
        ("Job Tracker", "CFA Level II item set.", 15, "Keeps exam practice daily during interview prep."),
    ]},
    {"week": 3, "title": "Pitch a stock in two minutes", "steps": [
        ("Research", "Pick a stock; get rating, fair value, implied growth, top risk.", 15,
         "Every research interview asks 'pitch me a stock'; you need the four facts ready."),
        ("Academy", "Practise the pitch out loud: thesis, valuation, catalyst, risk — two minutes, timed.", 20,
         "A tight two-minute structure is what makes a pitch memorable."),
        ("Agent Desk", "Run 'Equity Research' on it; did you miss anything? Save your review.", 10,
         "Stress-testing your own pitch before an interviewer does."),
        ("Job Tracker", "Lesson of the day.", 10, "Fills a theory gap behind the pitch."),
    ]},
    {"week": 3, "title": "Explain a trade to a PM", "steps": [
        ("Trading Desk", "Choose one idea; write entry, stop, target, size and why — five lines.", 15,
         "PMs approve trades they understand in thirty seconds; five clear lines is the standard."),
        ("Academy", "Work Desk → 'Trader': trade plan and execution report.", 20,
         "Shows you can turn an idea into a sized, costed trade."),
        ("Job Tracker", "CFA Level II item set.", 15, "Daily exam practice."),
    ]},
    {"week": 3, "title": "Escalate a risk issue", "steps": [
        ("Command Center", "Find the position closest to its limit. Draft a three-line escalation to the PM.", 15,
         "Clear, early escalation (what, how big, what to do) is the most valued risk-analyst behaviour."),
        ("Academy", "Work Desk → 'Portfolio / Risk Analyst': daily risk check with escalation note.", 20,
         "Graded practice of the same escalation skill."),
        ("Job Tracker", "CFA Level II item set.", 15, "Daily exam practice."),
    ]},
    {"week": 3, "title": "Present the portfolio to an investment committee", "steps": [
        ("Portfolio Manager", "Prepare three slides' worth of bullets: positioning, risk, changes proposed.", 25,
         "PM and portfolio-analyst roles present to committees; structure matters as much as numbers."),
        ("Agent Desk", "'Portfolio Analyst': use the attribution to explain what worked and what did not.", 10,
         "Attribution turns performance into an explanation: allocation, selection or luck."),
        ("Job Tracker", "Lesson of the day.", 10, "Theory behind the committee discussion."),
    ]},
    {"week": 3, "title": "Write a PE/VC investment memo", "steps": [
        ("Academy", "Work Desk → 'Private Equity / VC': pick one deal, write a half-page memo (meet or pass).", 30,
         "The IC memo is the analyst's main deliverable at a fund; partners decide from it."),
        ("Academy", "'Interview prep': answer one mock question out loud.", 10,
         "PE/VC interviews test how you think about deals, not formulas alone."),
        ("Job Tracker", "CFA Level II item set.", 15, "Daily exam practice."),
    ]},
    {"week": 3, "title": "Weekly review and mock interview", "steps": [
        ("Academy", "Answer five interview questions from different lessons out loud (one per desk).", 25,
         "Rotating desks mimics a real interview day with several interviewers."),
        ("Job Tracker", "Do one task on your weakest desk.", 20, "Closes the biggest gap before week 4."),
        ("Job Tracker", "Update and download your evidence pack.", 10, "Keeps your interview stories current."),
    ]},
    # ---------------- Week 4 — run each desk on your own ----------------
    {"week": 4, "title": "Investment analyst, unassisted", "steps": [
        ("Markets", "Write the morning note yourself first (20 minutes), then compare with the agent's.", 30,
         "Doing it first, then checking, proves you can do the job without the tool."),
        ("Job Tracker", "CFA Level II item set.", 15, "Daily exam practice."),
        ("Job Tracker", "Lesson of the day.", 10, "Fills remaining theory gaps."),
    ]},
    {"week": 4, "title": "Equity research, unassisted", "steps": [
        ("Research", "Value a company yourself: which model, which inputs, what is the price implying?", 30,
         "Choosing the model and defending the inputs is what senior analysts expect from you."),
        ("Agent Desk", "Compare with the agent and save your review.", 10, "Calibrates your judgment against the model."),
        ("Job Tracker", "CFA Level II item set.", 15, "Daily exam practice."),
    ]},
    {"week": 4, "title": "Trader, unassisted", "steps": [
        ("Trading Desk", "Pick your own trade from 'Full scan' (not the top ideas); plan and paper-trade it.", 25,
         "Finding your own idea, then sizing it, is the full trading workflow."),
        ("Trading Desk", "Review the blotter: average R and what you would change.", 10,
         "A written review after each trade is how traders improve."),
        ("Job Tracker", "CFA Level II item set.", 15, "Daily exam practice."),
    ]},
    {"week": 4, "title": "Risk analyst, unassisted", "steps": [
        ("Risk Intelligence", "Write the daily risk report yourself: status, top risks, stress, escalation.", 30,
         "The daily risk report is the risk analyst's core deliverable."),
        ("Agent Desk", "Compare with the Risk Analyst agent and save your review.", 10, "Checks what you missed."),
        ("Job Tracker", "CFA Level II item set.", 15, "Daily exam practice."),
    ]},
    {"week": 4, "title": "Portfolio manager, unassisted", "steps": [
        ("Portfolio Manager", "Propose one change to the model portfolio and test it in what-if.", 25,
         "PMs test changes on risk and return before taking them to committee."),
        ("Agent Desk", "Compare with the PM agent and save your review.", 10, "A second opinion before you commit."),
        ("Job Tracker", "CFA Level II item set.", 15, "Daily exam practice."),
    ]},
    {"week": 4, "title": "PE/VC, unassisted", "steps": [
        ("Academy", "Screen the deal flow, then run a term sheet and an LBO on your favourite deal.", 35,
         "The full deal workflow, start to finish, as you would at your fund."),
        ("Job Tracker", "CFA Level II item set.", 15, "Daily exam practice."),
    ]},
    {"week": 4, "title": "Graduation", "steps": [
        ("Job Tracker", "'Readiness': aim for every desk above 50%; do one task on the weakest.", 25,
         "Balanced readiness means you can interview for any of your target roles."),
        ("Job Tracker", "Download the final evidence pack — attach it to applications.", 10,
         "Concrete evidence of work sets you apart from candidates with only a CV."),
        ("Guide", "From now on the Job Tracker plans each day; keep the 45-minute routine.", 5,
         "Skills fade without use; the daily routine keeps you sharp until your first day on the job."),
    ]},
]
# 55 minutes at most, so with the 5-minute daily market & economy check a day never exceeds one hour.
MAX_DAY_MINUTES = 55
assert all(sum(m for _, _, m, _ in d["steps"]) <= MAX_DAY_MINUTES for d in TRAINING), "a training day is too long"


def day_minutes(day: int) -> int:
    return sum(m for _, _, m, _ in TRAINING[day]["steps"])


def _state(progress: dict) -> dict:
    return progress.setdefault("training", {})


def step_id(day: int, index: int) -> str:
    return f"d{day + 1}s{index + 1}"


def _day_complete(done: set, day: int) -> bool:
    return all(step_id(day, i) in done for i in range(len(TRAINING[day]["steps"])))


def current_day(progress: dict, today: Optional[date] = None) -> Optional[int]:
    """Index of the training day to work on, or None (not started, finished, or today's day already done).

    One training day per calendar day: a missed day is simply done the next day (the programme shifts by a
    day) and work never piles up — after finishing a day, the next one waits until tomorrow."""
    t = progress.get("training") or {}
    if not t.get("started") or t.get("dismissed"):
        return None
    today_iso = (today or date.today()).isoformat()
    if today_iso in (t.get("completed_on") or {}).values():
        return None
    done = set(t.get("done", []))
    for day in range(len(TRAINING)):
        if not _day_complete(done, day):
            return day
    return None


def day_for_today(progress: dict, today: Optional[date] = None) -> Optional[int]:
    """The training day that belongs to today: the one finished today, else the one to work on."""
    t = progress.get("training") or {}
    if not t.get("started") or t.get("dismissed"):
        return None
    today_iso = (today or date.today()).isoformat()
    for day, when in (t.get("completed_on") or {}).items():
        if when == today_iso:
            return int(day) - 1
    return current_day(progress, today)


def next_step(progress: dict, today: Optional[date] = None) -> Optional[dict]:
    day = current_day(progress, today)
    if day is None:
        return None
    done = set(progress["training"].get("done", []))
    for i, (page, text, minutes, why) in enumerate(TRAINING[day]["steps"]):
        if step_id(day, i) not in done:
            return {"day": day, "index": i, "id": step_id(day, i), "page": page, "text": text, "minutes": minutes,
                    "why": why,
                    "total": len(TRAINING[day]["steps"]), "week": TRAINING[day]["week"]}
    return None                                   # today's training done; next day unlocks tomorrow


def start(progress: dict, today: Optional[date] = None) -> None:
    _state(progress).update({"started": (today or date.today()).isoformat(), "done": [], "dismissed": False})


def mark_done(progress: dict, sid: str, today: Optional[date] = None) -> None:
    state = _state(progress)
    done = state.setdefault("done", [])
    if sid not in done:
        done.append(sid)
    day = int(sid[1:sid.index("s")]) - 1
    if _day_complete(set(done), day):
        state.setdefault("completed_on", {}).setdefault(str(day + 1), (today or date.today()).isoformat())


def finished(progress: dict) -> bool:
    done = set((progress.get("training") or {}).get("done", []))
    return all(step_id(d, i) in done for d, p in enumerate(TRAINING) for i in range(len(p["steps"])))


# ==============================================================
# STREAMLIT
# ==============================================================

def _load_progress() -> Optional[dict]:
    import academy_desk as desk
    import vittantra_cloud as cloud
    path = cloud.progress_path()
    if path is None:
        return None
    return desk.load_progress(path)


def _save(progress: dict) -> None:
    from vittantra_academy_page import _save as save_progress
    save_progress(progress)


def _go(page: str) -> None:
    st.session_state["nav"] = page


def _done(sid: str) -> None:
    progress = _load_progress()
    if progress is not None:
        mark_done(progress, sid)
        _save(progress)


def page_banner(page: str, labels: Dict[str, str]) -> None:
    """Slim coach strip under the top bar: the next training step, wherever you are."""
    progress = _load_progress()
    if not progress:
        return
    step = next_step(progress)
    if step is None:
        return
    here = step["page"] == page
    with st.container(border=True):
        c1, c2, c3 = st.columns([6, 1.3, 1.1], vertical_alignment="center")
        where = "" if here else f" — on **{labels.get(step['page'], step['page'])}**"
        c1.markdown(f"**Training · Week {step['week']} · Day {step['day'] + 1} of {len(TRAINING)} · step "
                    f"{step['index'] + 1} of {step['total']}**{where}  \n{step['text']} *(about {step['minutes']} min)*  \n"
                    f"**Why:** {step['why']}")
        if not here:
            c2.button("Take me there", key=f"coach-go-{page}", on_click=_go, args=(step["page"],), width="stretch")
        c3.button("Done", key=f"coach-done-{page}", on_click=_done, args=(step["id"],), type="primary",
                  width="stretch")


def home_card(labels: Dict[str, str]) -> None:
    """Home: start training, or show today's training day as a checklist."""
    progress = _load_progress()
    if progress is None:
        return
    t = progress.get("training") or {}
    if not t.get("started"):
        with st.container(border=True):
            st.markdown("#### Start your 4-week guided training")
            st.markdown("Four weeks, never more than an hour a day. Week 1 tours every desk click by click; week 2 "
                        "builds the daily routine with depth; week 3 produces interview-ready work (a market note, a "
                        "stock pitch, a trade plan, an escalation, an IC presentation, a PE/VC memo); week 4 you run "
                        "each desk on your own. A coach strip on every page tells you where to click next.")
            if st.button("Start training", key="coach-start", type="primary"):
                start(progress)
                _save(progress)
                st.rerun()
        return
    if t.get("dismissed"):
        return
    if finished(progress):
        if not t.get("graduated_seen"):
            with st.container(border=True):
                st.markdown("#### Training complete — four weeks done")
                st.markdown("From here the Job Tracker plans each day. Keep the routine and refresh your evidence pack "
                            "before each application.")
                if st.button("Close", key="coach-graduated"):
                    _state(progress)["graduated_seen"] = True
                    _save(progress)
                    st.rerun()
        return
    day = current_day(progress)
    if day is None:
        done_days = sum(_day_complete(set(t.get("done", [])), d) for d in range(len(TRAINING)))
        st.success(f"Today's training is done ({done_days} of {len(TRAINING)} days). The next day opens "
                   "tomorrow — missed days never pile up.")
        return
    done = set(t.get("done", []))
    plan = TRAINING[day]
    with st.container(border=True):
        st.markdown(f"#### Training · Week {plan['week']} · Day {day + 1} of {len(TRAINING)} — {plan['title']}")
        st.caption(f"About {day_minutes(day)} minutes today.")
        for i, (page, text, minutes, why) in enumerate(plan["steps"]):
            sid = step_id(day, i)
            c1, c2 = st.columns([7, 1.3], vertical_alignment="center")
            mark = "✓" if sid in done else "○"
            with c1:
                st.markdown(f"{mark} **{labels.get(page, page)}** — {text} *({minutes} min)*")
                st.caption(f"Why: {why}")
            if sid not in done:
                c2.button("Go", key=f"coach-home-{sid}", on_click=_go, args=(page,), width="stretch")
        if st.button("Hide training", key="coach-hide"):
            _state(progress)["dismissed"] = True
            _save(progress)
            st.rerun()
