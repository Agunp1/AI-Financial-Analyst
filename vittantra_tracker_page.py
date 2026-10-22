"""
Job Tracker page: today's three steps across the desks and CFA Level II,
a readiness scorecard per role, the CFA plan and an evidence pack for
interviews. Logic lives in job_tracker.py; the work itself reuses the
Academy desks, item sets and lessons.
"""

from __future__ import annotations

from datetime import date

import pandas as pd
import streamlit as st

import academy_cfa as cfa
import academy_desk as desk
import academy_live as live
import job_tracker as jt
import vittantra_cloud as cloud
from academy_content import ROLES
from vittantra_academy_page import DESKS, LESSON_BY_ID, _role_label, _save, render_item_set, render_lesson


def _load() -> dict:
    path = cloud.progress_path()
    return desk.load_progress(path) if path is not None else desk.load_progress()


def _step_header(step: dict, number: int) -> str:
    mark = "✓" if step["done"] else "○"
    return f"{mark} {number}. **{step['step']}** — {step['what']} (about {step['minutes']} min)"


def render_tracker() -> None:
    st.markdown("### Job Tracker")
    st.markdown('<div class="vt-lede">Three small steps a day: one real duty on a desk, one CFA Level II item set, '
                'one lesson. The roles rotate so every responsibility gets practised; graded work becomes '
                'evidence for interviews.</div>', unsafe_allow_html=True)
    progress = _load()
    if cloud.cloud_mode() and cloud.current_user() is None:
        st.caption("You are viewing the owner's tracker. Sign in or create an account (sidebar) to keep your own.")

    today = date.today()
    plan = jt.daily_plan(progress, today)
    week = jt.week_summary(progress, today)
    exam_days = jt.days_to_exam(progress, today)
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Today's steps", f"{plan['done']} of 3", _role_label(plan["role"]), delta_color="off", delta_arrow="off")
    c2.metric("Streak", f"{jt.streak(progress, today)} day(s)")
    c3.metric("Last 7 days", f"{week['tasks']} task(s)", f"{week['cfa_sets']} item set(s) · {week['lessons']} lesson(s)",
              delta_color="off", delta_arrow="off")
    c4.metric("CFA exam in", f"{exam_days} days" if exam_days is not None and exam_days >= 0 else "—",
              "set the date under CFA plan" if exam_days is None else None, delta_color="off", delta_arrow="off")

    today_tab, scorecard, cfa_tab, evidence = st.tabs(["Today", "Readiness", "CFA Level II plan", "Evidence pack"])

    with today_tab:
        st.caption(f"{today:%A %d %B %Y} · desk of the day: **{ROLES[plan['role']]['title']}** "
                   "(Monday to Saturday rotate through the six roles; Sunday goes to your weakest role).")
        duty, cfa_step, lesson_step = plan["steps"]
        st.markdown("  \n".join(_step_header(step, i + 1) for i, step in enumerate(plan["steps"])))
        first_open = next((i for i, step in enumerate(plan["steps"]) if not step["done"]), 0)
        chosen = st.radio("Work on", [0, 1, 2], index=first_open, horizontal=True, key="trk-step",
                          format_func=lambda i: plan["steps"][i]["step"])
        with st.container(border=True):
            if chosen == 0:
                st.markdown(f"Suggested duty: **{duty['what']}** — the responsibility on this desk with the least "
                            "evidence so far. Any graded task on this desk completes the step.")
                DESKS[plan["role"]](progress)
            elif chosen == 1:
                st.markdown(f"Focus topic: **{cfa_step['what']}** — your weakest Level II area among the topics "
                            "Vittantra covers.")
                try:
                    item = {"key": cfa_step["key"], **cfa.ITEM_SETS[cfa_step["key"]](today)}
                    owner = next(r for r, keys in cfa.DESK_ITEM_SETS.items() if cfa_step["key"] in keys)
                    render_item_set(item, progress, owner, f"trk-cfa-{cfa_step['key']}")
                except live.MissingData as exc:
                    st.info(str(exc))
            elif lesson_step["lesson"]:
                render_lesson(LESSON_BY_ID[lesson_step["lesson"]], progress, key_prefix="trk-")
            else:
                st.markdown("Every lesson on this desk is learned. Open any lesson in Academy → Lessons and "
                            "answer its interview questions out loud.")
        if plan["done"] == 3:
            st.success("All three steps done today.")

    with scorecard:
        st.caption(f"A responsibility is demonstrated when you have graded work on it scoring {jt.PASS_SCORE} or "
                   "more. This is what an interviewer can ask you to walk through.")
        summary = pd.DataFrame([{"Role": ROLES[r]["title"], "Readiness": jt.readiness(progress, r),
                                 "Demonstrated": sum(x["status"] == "Demonstrated"
                                                     for x in jt.responsibility_status(progress, r)),
                                 "Responsibilities": len(jt.RESPONSIBILITIES[r])} for r in jt.ROLE_ORDER])
        st.dataframe(summary, hide_index=True, width="stretch",
                     column_config={"Readiness": st.column_config.ProgressColumn(format="percent", min_value=0,
                                                                                 max_value=1)})
        role = st.selectbox("Role detail", jt.ROLE_ORDER, format_func=_role_label, key="trk-role")
        rows = pd.DataFrame(jt.responsibility_status(progress, role)).drop(columns="desk")
        rows["last_done"] = rows["last_done"].map(lambda d: f"{d:%d %b %Y}" if d else "—")
        rows["best_score"] = rows["best_score"].map(lambda v: f"{v:.0f}" if v is not None and v == v else "—")
        st.dataframe(rows.rename(columns={"responsibility": "Responsibility", "times_done": "Times done",
                                          "best_score": "Best score", "last_done": "Last done",
                                          "status": "Status"}), hide_index=True, width="stretch")

    with cfa_tab:
        tracker = progress.setdefault("tracker", {})
        current = jt._day(tracker.get("cfa_exam")) if tracker.get("cfa_exam") else None
        picked = st.date_input("Your Level II exam date", value=current, min_value=min(today, current or today), key="trk-exam",
                               format="DD/MM/YYYY")
        if picked and picked != current and st.button("Save exam date", key="trk-exam-save"):
            tracker["cfa_exam"] = picked.isoformat()
            _save(progress)
            st.rerun()
        if exam_days is not None and exam_days > 0:
            st.markdown(f"**{exam_days} days to go.** One item set a day here is about "
                        f"{exam_days * 3} questions before the exam — use it alongside the CFA Institute "
                        "curriculum and question bank, not instead of them.")
        focus = pd.DataFrame(jt.cfa_focus(progress))
        focus["accuracy"] = focus["accuracy"].map(lambda a: f"{a:.0%}" if a is not None and a == a else "—")
        st.dataframe(focus.rename(columns={"topic": "Topic area (weakest first)", "answered": "Questions answered",
                                           "accuracy": "Accuracy", "weight": "Exam weight (approx.)"}),
                     hide_index=True, width="stretch")
        st.caption("Not covered by Vittantra item sets: Ethical and Professional Standards, Financial Statement "
                   "Analysis and Corporate Issuers (about a third of the exam) — practise these in the CFA "
                   "Institute question bank. Weights are approximate; check the current curriculum.")

    with evidence:
        st.markdown("A one-page record of what you have demonstrated on each desk, your best work and your CFA "
                    "practice — bring it to interviews or attach it to applications.")
        text = jt.evidence_pack(progress, today)
        st.markdown(text.replace("$", "\\$"))
        st.download_button("Download evidence pack (Markdown)", text, file_name="vittantra_evidence_pack.md",
                           key="trk-download")
