"""
Vittantra Academy page: learn by doing.

Work Desk (real tasks from live data, graded) → lessons on demand →
role handbook → work record for interviews.
"""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import academy_desk as desk
import academy_live as live
from academy_content import LESSONS, ROLES, SIMULATOR_TASKS


LESSON_BY_ID = {lesson["id"]: lesson for lesson in LESSONS}
ROLE_KEYS = list(ROLES)


def _role_label(key: str) -> str:
    return ROLES[key]["title"].split(" (")[0]


def render_lesson(lesson: dict, progress: dict, key_prefix: str = "") -> None:
    st.markdown(f"**Concept.** {lesson['concept']}")
    for label, formula in lesson["formulas"]:
        st.caption(label)
        st.latex(formula)
    st.markdown("**Live example from your Vittantra data**")
    try:
        st.markdown(getattr(live, lesson["live"])())
    except live.MissingData as exc:
        st.info(str(exc))
    st.markdown(f"**Where it is in the code:** {', '.join(f'`{c}`' for c in lesson['code'])}")
    st.markdown(f"**On the job:** {lesson['on_the_job']}")
    st.markdown(f"**Exercise:** {lesson['exercise']}")
    with st.expander("Interview questions"):
        for qa in lesson["interview"]:
            st.markdown(f"**Q: {qa['question']}**")
            st.markdown(f"A: {qa['answer']}")
    if lesson["id"] not in progress.get("lessons_read", []):
        if st.button("Mark as learned", key=f"{key_prefix}read-{lesson['id']}"):
            progress.setdefault("lessons_read", []).append(lesson["id"])
            desk.save_progress(progress)
            st.rerun()
    else:
        st.caption("✅ Learned")


def _lesson_help(ids, progress, key):
    with st.expander("📘 Stuck? Learn what you need for this task"):
        for lesson_id in ids:
            lesson = LESSON_BY_ID[lesson_id]
            st.markdown(f"#### {lesson_id} · {lesson['title']}")
            render_lesson(lesson, progress, key_prefix=f"{key}-")


def _review(score: float, feedback: str, reference: str) -> None:
    colour = "green" if score >= 80 else "orange" if score >= 50 else "red"
    st.markdown(f"### Review: :{colour}[{score:.0f}/100]")
    if feedback:
        st.markdown(feedback)
    st.markdown("**Senior colleague's reference answer**")
    st.markdown(reference)


def _submit(progress, role, task, score, answer, review_text, state_key):
    if not st.session_state.get(state_key):
        desk.record_task(progress, role, task, score, answer, review_text)
        desk.save_progress(progress)
        st.session_state[state_key] = True


def _checklist(role: str, key: str) -> float:
    items = SIMULATOR_TASKS[role]["checklist"]
    st.markdown("**Self-review checklist** (be honest — this is how seniors review your work)")
    ticked = sum(st.checkbox(item, key=f"{key}-{i}") for i, item in enumerate(items))
    return 100 * ticked / len(items)


# ==============================================================
# DESKS
# ==============================================================

def desk_investment_analyst(progress):
    role = "investment_analyst"
    task = SIMULATOR_TASKS[role]
    st.markdown(f"#### 🕗 {task['title']}")
    st.write(task["brief"])
    try:
        data = desk.morning_brief_task()
    except live.MissingData as exc:
        st.info(str(exc)); return
    st.markdown(data["context"])
    text = st.text_area("Your morning brief (3 bullets)", key="ia-brief", height=140)
    score = _checklist(role, "ia-check")
    if st.button("Send to PM", key="ia-submit", disabled=not text.strip()):
        _submit(progress, role, task["title"], score, {"brief": text}, data["reference"], "ia-done")
        _review(score, "", data["reference"])
    _lesson_help(data["lessons"], progress, "ia")


def desk_equity_researcher(progress):
    role = "equity_researcher"
    task = SIMULATOR_TASKS[role]
    st.markdown(f"#### 📄 {task['title']}")
    st.write(task["brief"])
    try:
        data = desk.tear_sheet_task()
    except live.MissingData as exc:
        st.info(str(exc)); return
    st.markdown(data["context"])
    cols = st.columns(4)
    ratings = {label: cols[i].selectbox(label, desk.BANDS, index=1, key=f"er-{label}")
               for i, label in enumerate(desk.PILLARS.values())}
    view = st.text_area("Your overall view and the single most important reason", key="er-view")
    risk = st.text_input("Key risk to your view", key="er-risk")
    if st.button("Publish note", key="er-submit", disabled=not view.strip()):
        score, feedback = desk.grade_tear_sheet(data["answer_key"], ratings)
        _submit(progress, role, f"{task['title']}: {data['ticker']}", score,
                {**ratings, "view": view, "risk": risk}, feedback + "\n\n" + data["reference"], "er-done")
        _review(score, feedback, data["reference"])
    _lesson_help(data["lessons"], progress, "er")


def desk_portfolio_analyst(progress):
    role = "portfolio_analyst"
    task = SIMULATOR_TASKS[role]
    st.markdown(f"#### 🛡️ {task['title']}")
    st.write(task["brief"])
    try:
        data = desk.risk_check_task()
        stress = desk.stress_task()
    except live.MissingData as exc:
        st.info(str(exc)); return
    st.markdown(data["context"])
    picked = st.multiselect("Which positions breach their risk budget?", data["symbols"], key="ra-pick")
    escalation = st.text_area("Your escalation note to the PM", key="ra-note")
    if st.button("Escalate", key="ra-submit", disabled=not escalation.strip()):
        score, feedback = desk.grade_set(data["answer"], picked)
        _submit(progress, role, task["title"], score, {"breaches": picked, "note": escalation},
                feedback + "\n\n" + data["reference"], "ra-done")
        _review(score, feedback, data["reference"])

    st.divider()
    st.markdown("#### ⚡ Weekly stress question")
    st.write("Looking at Vittantra's stress scenarios: which one hurts this portfolio most, and which position "
             "contributes the largest loss in it?")
    scenario = st.selectbox("Worst scenario", stress["scenarios"], key="ra-scn")
    symbol = st.selectbox("Largest contributor", stress["symbols"], key="ra-sym")
    if st.button("Answer", key="ra-stress"):
        score = 50 * (scenario == stress["answer"][0]) + 50 * (symbol == stress["answer"][1])
        _submit(progress, role, "Stress question", score, {"scenario": scenario, "symbol": symbol},
                stress["reference"], "ra-stress-done")
        _review(score, "", stress["reference"])
    _lesson_help(data["lessons"] + stress["lessons"], progress, "ra")


def desk_portfolio_manager(progress):
    role = "portfolio_manager"
    task = SIMULATOR_TASKS[role]
    st.markdown(f"#### ⚖️ {task['title']}")
    st.write(task["brief"])
    st.caption(f"Limits: no position above {desk.RISK_CAP:.0%} of portfolio risk; one-way turnover at most "
               f"{desk.TURNOVER_CAP:.0%}.")
    try:
        inputs = desk.rebalance_inputs()
    except live.MissingData as exc:
        st.info(str(exc)); return
    top = sorted(inputs["risk_share"], key=inputs["risk_share"].get, reverse=True)[:5]
    st.markdown("**Current risk shares:** " + ", ".join(f"{s} {inputs['risk_share'][s]:.0%}" for s in top))
    cols = st.columns(len(top))
    cuts = {s: cols[i].slider(f"Cut {s} by", 0, 100, 0, 5, key=f"pm-{s}", format="%d%%") / 100
            for i, s in enumerate(top)}
    if st.button("Run my proposal through the risk model", key="pm-eval"):
        result = desk.evaluate_rebalance(inputs, cuts)
        st.session_state["pm-result"] = result
    result = st.session_state.get("pm-result")
    if result:
        shares = result["shares"].sort_values(ascending=False)
        figure = go.Figure(go.Bar(x=shares.index, y=shares.values * 100,
                                  marker_color=["#E5484D" if v > desk.RISK_CAP else "#2E6BE6" for v in shares.values]))
        figure.add_hline(y=desk.RISK_CAP * 100, line_dash="dash", annotation_text="35% limit")
        figure.update_layout(height=280, margin=dict(l=10, r=10, t=10, b=10), yaxis_title="Risk share (%)")
        st.plotly_chart(figure, width="stretch")
        c1, c2 = st.columns(2)
        # A leading "-" makes Streamlit show the breach in red.
        c1.metric("Largest risk share", f"{result['max_share']:.0%} ({result['max_symbol']})",
                  "within limit" if result["within_cap"] else "-over limit")
        c2.metric("Turnover", f"{result['turnover']:.0%}",
                  "within limit" if result["within_turnover"] else "-over limit")
        rationale = st.text_area("Your rationale for the investment committee", key="pm-why")
        if st.button("Submit to committee", key="pm-submit", disabled=not rationale.strip()):
            reference = ("Vittantra's own Day 65 rebalancer cuts the largest contributor until its Euler risk share is "
                         "at the 35% limit, recomputing every pass, while respecting turnover. A strong proposal "
                         "reaches the limit with the least trading, and explains what return is given up.")
            _submit(progress, role, task["title"], result["score"],
                    {**{f"cut {k}": f"{v:.0%}" for k, v in cuts.items()}, "rationale": rationale},
                    reference, "pm-done")
            _review(result["score"], "", reference)
    _lesson_help(["PM1", "PM5", "RA5", "PM3"], progress, "pm")


def desk_advisor(progress):
    role = "advisor"
    task = SIMULATOR_TASKS[role]
    st.markdown(f"#### 🤝 {task['title']}")
    st.write(task["brief"])
    data = desk.client_task()
    c = data["client"]
    st.info(f"**{c['name']}, {c['age']}** — goal: **{c['goal']}** in **{c['horizon']} years**. "
            f"Savings {live.money(c['savings'])}, saves {live.money(c['annual_saving'])}/year, goal "
            f"{live.money(c['target'])}. Income: {c['income']}. If the portfolio fell 20%: *“{c['reaction']}”*.")
    cols = st.columns(4)
    weights = {sleeve: cols[i].number_input(f"{sleeve} %", 0, 100, default, 5, key=f"ad-{sleeve}")
               for i, (sleeve, default) in enumerate(
                   [("Stocks", 40), ("Bonds", 40), ("Cash", 10), ("Alternatives", 10)])}
    total = sum(weights.values())
    st.caption(f"Total: {total}%" + ("" if total == 100 else " — must add up to 100%"))
    explanation = st.text_area("How would you explain this recommendation and its risk to the client?", key="ad-why")
    if st.button("Present to client", key="ad-submit", disabled=total != 100 or not explanation.strip()):
        try:
            vols = desk.sleeve_volatility()
        except live.MissingData:
            vols = {"Stocks": 0.16, "Bonds": 0.06, "Cash": 0.005, "Alternatives": 0.18}
        result = desk.evaluate_allocation(c, {k: v / 100 for k, v in weights.items()}, vols)
        best = desk.reference_allocation(c, vols)
        feedback = "\n".join(f"- {'✅' if ok else '❌'} {name}: {detail}" for name, ok, detail in result["checks"])
        reference = "Suitable reference allocation: " + ", ".join(
            f"{k} {v:.0%}" for k, v in best["weights"].items()) + \
            f" → expected {best['expected_return']:.1%}/yr (assumption), bad year ≈ {best['bad_year_loss']:.0%}." \
            if best else "No allocation meets every rule; tell the client the goal needs more saving or time."
        reference += ("\n\nAssumptions (stated, not forecasts): long-run returns stocks 6%, bonds 4%, cash 3%, "
                      "alternatives 5%; volatilities from Vittantra's Markets data.")
        _submit(progress, role, f"{task['title']}: {c['name']}", result["score"],
                {**{k: f"{v}%" for k, v in weights.items()}, "explanation": explanation},
                feedback + "\n\n" + reference, "ad-done")
        _review(result["score"], feedback, reference)
    _lesson_help(data["lessons"], progress, "ad")


DESKS = {
    "investment_analyst": desk_investment_analyst,
    "equity_researcher": desk_equity_researcher,
    "portfolio_analyst": desk_portfolio_analyst,
    "portfolio_manager": desk_portfolio_manager,
    "advisor": desk_advisor,
}


# ==============================================================
# PAGE
# ==============================================================

def render_academy() -> None:
    st.markdown("### Vittantra Academy — learn by doing")
    st.caption("Do the real work of each role on live data. Get reviewed like a junior on a desk. "
               "Lessons appear when you need them.")
    progress = desk.load_progress()

    cols = st.columns(len(ROLE_KEYS))
    for col, key in zip(cols, ROLE_KEYS):
        xp = progress.get("xp", {}).get(key, 0)
        level, nxt, needed = desk.level_for(xp)
        col.metric(_role_label(key), level, f"{xp} XP" + (f" · {needed} to {nxt}" if nxt else ""),
                   delta_color="off")

    work, handbook, lessons, record = st.tabs(["🖥️ Work Desk", "📘 Role Handbook", "🎓 Lessons", "🗂️ My Work Record"])

    with work:
        role = st.radio("Today you are working as", ROLE_KEYS, format_func=_role_label,
                        horizontal=True, key="desk-role")
        st.caption(f"Shift: {pd.Timestamp.now():%A %d %B %Y} · tasks refresh daily from live data")
        DESKS[role](progress)

    with handbook:
        key = st.selectbox("Role", ROLE_KEYS, format_func=_role_label, key="hb-role")
        r = ROLES[key]
        st.markdown(f"## {r['title']}")
        st.markdown(f"**Mission:** {r['mission']}")
        st.markdown("**Framework professionals use**")
        st.markdown("\n".join(f"- {item}" for item in r["framework"]))
        st.markdown("**Regular duties**")
        for freq, items in r["duties"].items():
            st.markdown(f"*{freq}*")
            st.markdown("\n".join(f"- {item}" for item in items))
        st.markdown(f"**Key outputs:** {', '.join(r['outputs'])}")
        st.markdown(f"**Tools:** {', '.join(r['tools'])}")
        st.markdown(f"**How performance is judged:** {', '.join(r['kpis'])}")
        st.markdown(f"**Career path:** {r['career']}")
        st.markdown(f"**Credentials:** {r['credentials']}")
        st.markdown(f"**Practise it in Vittantra:** {r['vittantra']}")

    with lessons:
        key = st.selectbox("Track", ROLE_KEYS, format_func=_role_label, key="ls-role")
        read = set(progress.get("lessons_read", []))
        track = [lesson for lesson in LESSONS if lesson["role"] == key]
        st.progress(sum(l["id"] in read for l in track) / len(track),
                    text=f"{sum(l['id'] in read for l in track)} of {len(track)} lessons learned")
        for lesson in track:
            with st.expander(f"{'✅ ' if lesson['id'] in read else ''}{lesson['id']} · {lesson['title']}"):
                render_lesson(lesson, progress, key_prefix="tab-")

    with record:
        records = progress.get("records", [])
        if not records:
            st.info("No work yet. Start a shift on the Work Desk.")
        else:
            table = pd.DataFrame(records)[["time", "role", "task", "score", "xp"]]
            table["role"] = table["role"].map(_role_label)
            st.dataframe(table.iloc[::-1], width="stretch", hide_index=True)
            st.download_button("Download my work record (for interviews)",
                               desk.work_record_markdown(progress), "vittantra_work_record.md")
