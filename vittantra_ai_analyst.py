"""
Vittantra
Day 73 — AI Analyst Intelligence Layer

Purpose
-------
Create a deterministic, explainable analyst layer above the existing
Vittantra portfolio-risk-governance-remediation-approval pipeline.

This module does NOT execute trades and does NOT override governance.
It reads the existing Day 67–70 CSV outputs and converts them into:
- executive portfolio brief
- key risk drivers
- priority instrument queue
- governance interpretation
- remediation interpretation
- approval / human-attention summary
- structured analyst responses for the Streamlit app

The module is intentionally defensive: optional or renamed columns do not
cause the whole analyst layer to fail when equivalent core fields exist.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

import numpy as np
import pandas as pd


BASE_DIR = Path(__file__).resolve().parent

FILES = {
    "risk_dashboard": BASE_DIR / "day67_portfolio_risk_dashboard.csv",
    "governance": BASE_DIR / "day68_instrument_governance_actions.csv",
    "remediation": BASE_DIR / "day69_portfolio_remediation_summary.csv",
    "approval": BASE_DIR / "day70_portfolio_approval_summary.csv",
}


# ============================================================
# GENERIC HELPERS
# ============================================================

def load_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(path)
    except Exception:
        return pd.DataFrame()


def first_value(
    df: pd.DataFrame,
    candidates: list[str],
    default: Any = None,
) -> Any:
    if df.empty:
        return default

    for col in candidates:
        if col in df.columns:
            series = df[col].dropna()
            if not series.empty:
                return series.iloc[0]

    return default


def find_column(
    df: pd.DataFrame,
    candidates: list[str],
) -> Optional[str]:
    for col in candidates:
        if col in df.columns:
            return col
    return None


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if pd.isna(value):
            return default
        number = float(value)
        return number if np.isfinite(number) else default
    except (TypeError, ValueError):
        return default


def safe_int(value: Any, default: int = 0) -> int:
    try:
        if pd.isna(value):
            return default
        return int(float(value))
    except (TypeError, ValueError):
        return default


def safe_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if pd.isna(value):
        return False
    return str(value).strip().upper() in {
        "TRUE", "1", "YES", "Y", "REQUIRED", "BLOCK", "BLOCKED"
    }


def pct(value: Any) -> str:
    return f"{safe_float(value) * 100:,.1f}%"


def clean(value: Any) -> str:
    if pd.isna(value):
        return ""
    return str(value).strip()


# ============================================================
# DATA MODEL
# ============================================================

@dataclass
class AnalystSnapshot:
    portfolio_status: str
    workflow_status: str
    instrument_count: int
    warning_count: int
    breach_count: int
    critical_count: int
    requires_review_count: int
    mean_risk_budget_utilization: float
    maximum_risk_budget_utilization: float
    decision_ticket_count: int
    pending_review_count: int
    dual_approval_required_count: int
    approval_queue_count: int
    risk_reduction_ticket_count: int
    immediate_priority_count: int
    automatic_execution_authorized_count: int
    maximum_estimated_post_remediation_utilization: float


# ============================================================
# ENGINE
# ============================================================

class VittantraAIAnalyst:
    """
    Deterministic analyst layer for Vittantra.

    The class derives narrative from existing model outputs.
    It does not invent market prices, fundamentals, news or forecasts.
    """

    def __init__(self, base_dir: Path | None = None) -> None:
        self.base_dir = base_dir or BASE_DIR

        self.risk = load_csv(
            self.base_dir / FILES["risk_dashboard"].name
        )
        self.governance = load_csv(
            self.base_dir / FILES["governance"].name
        )
        self.remediation = load_csv(
            self.base_dir / FILES["remediation"].name
        )
        self.approval = load_csv(
            self.base_dir / FILES["approval"].name
        )

        self.snapshot = self._build_snapshot()

    # --------------------------------------------------------
    # SNAPSHOT
    # --------------------------------------------------------

    def _build_snapshot(self) -> AnalystSnapshot:
        portfolio_status = clean(
            first_value(
                self.risk,
                ["portfolio_status"],
                "UNKNOWN",
            )
        ).upper()

        workflow_status = clean(
            first_value(
                self.approval,
                ["portfolio_workflow_status"],
                "UNKNOWN",
            )
        ).upper()

        current_max = safe_float(
            first_value(
                self.approval,
                ["maximum_current_risk_budget_utilization"],
                first_value(
                    self.risk,
                    ["maximum_risk_budget_utilization"],
                    0.0,
                ),
            )
        )

        return AnalystSnapshot(
            portfolio_status=portfolio_status,
            workflow_status=workflow_status,
            instrument_count=safe_int(
                first_value(
                    self.risk,
                    ["instrument_count"],
                    len(self.governance),
                )
            ),
            warning_count=safe_int(
                first_value(self.risk, ["warning_count"], 0)
            ),
            breach_count=safe_int(
                first_value(self.risk, ["breach_count"], 0)
            ),
            critical_count=safe_int(
                first_value(self.risk, ["critical_count"], 0)
            ),
            requires_review_count=safe_int(
                first_value(self.risk, ["requires_review_count"], 0)
            ),
            mean_risk_budget_utilization=safe_float(
                first_value(
                    self.risk,
                    ["mean_risk_budget_utilization"],
                    0.0,
                )
            ),
            maximum_risk_budget_utilization=current_max,
            decision_ticket_count=safe_int(
                first_value(
                    self.approval,
                    ["decision_ticket_count"],
                    0,
                )
            ),
            pending_review_count=safe_int(
                first_value(
                    self.approval,
                    ["pending_review_count"],
                    0,
                )
            ),
            dual_approval_required_count=safe_int(
                first_value(
                    self.approval,
                    ["dual_approval_required_count"],
                    0,
                )
            ),
            approval_queue_count=safe_int(
                first_value(
                    self.approval,
                    ["approval_queue_count"],
                    0,
                )
            ),
            risk_reduction_ticket_count=safe_int(
                first_value(
                    self.approval,
                    ["risk_reduction_ticket_count"],
                    0,
                )
            ),
            immediate_priority_count=safe_int(
                first_value(
                    self.approval,
                    ["immediate_priority_count"],
                    0,
                )
            ),
            automatic_execution_authorized_count=safe_int(
                first_value(
                    self.approval,
                    ["automatic_execution_authorized_count"],
                    0,
                )
            ),
            maximum_estimated_post_remediation_utilization=safe_float(
                first_value(
                    self.approval,
                    ["maximum_estimated_post_remediation_utilization"],
                    first_value(
                        self.remediation,
                        ["maximum_estimated_post_remediation_utilization"],
                        0.0,
                    ),
                )
            ),
        )

    # --------------------------------------------------------
    # INSTRUMENT DIAGNOSTICS
    # --------------------------------------------------------

    def priority_instruments(self, limit: int = 10) -> pd.DataFrame:
        if self.governance.empty:
            return pd.DataFrame()

        df = self.governance.copy()

        symbol_col = find_column(df, ["symbol", "ticker", "instrument"])
        asset_col = find_column(df, ["asset_class"])
        type_col = find_column(df, ["instrument_type"])
        util_col = find_column(df, ["risk_budget_utilization"])
        excess_col = find_column(df, ["risk_budget_excess"])
        status_col = find_column(df, ["governance_status"])
        action_col = find_column(df, ["governance_action"])
        reason_col = find_column(df, ["governance_reason"])
        review_col = find_column(df, ["requires_review"])
        block_col = find_column(df, ["block_incremental_risk"])

        if util_col:
            df[util_col] = pd.to_numeric(df[util_col], errors="coerce")
        if excess_col:
            df[excess_col] = pd.to_numeric(df[excess_col], errors="coerce")

        def score_row(row: pd.Series) -> float:
            score = 0.0

            if util_col:
                score += max(safe_float(row.get(util_col)), 0.0) * 10

            if excess_col:
                score += max(safe_float(row.get(excess_col)), 0.0) * 5

            if review_col and safe_bool(row.get(review_col)):
                score += 25

            if block_col and safe_bool(row.get(block_col)):
                score += 40

            status = clean(row.get(status_col, "")).upper() if status_col else ""
            if "CRITICAL" in status:
                score += 50
            elif "WARNING" in status or "WATCH" in status:
                score += 20

            return score

        df["_analyst_priority_score"] = df.apply(score_row, axis=1)

        cols = [
            c for c in [
                symbol_col,
                asset_col,
                type_col,
                util_col,
                excess_col,
                status_col,
                action_col,
                review_col,
                block_col,
                reason_col,
                "_analyst_priority_score",
            ] if c
        ]

        return (
            df[cols]
            .sort_values(
                "_analyst_priority_score",
                ascending=False,
            )
            .head(limit)
            .reset_index(drop=True)
        )

    def top_risk_drivers(self, limit: int = 5) -> pd.DataFrame:
        if self.governance.empty:
            return pd.DataFrame()

        df = self.governance.copy()

        symbol_col = find_column(df, ["symbol", "ticker", "instrument"])
        asset_col = find_column(df, ["asset_class"])
        contrib_col = find_column(df, ["modeled_risk_contribution"])
        util_col = find_column(df, ["risk_budget_utilization"])

        if not symbol_col:
            return pd.DataFrame()

        sort_col = None

        if contrib_col:
            df[contrib_col] = pd.to_numeric(
                df[contrib_col],
                errors="coerce",
            )
            df["_abs_contribution"] = df[contrib_col].abs()
            sort_col = "_abs_contribution"

        elif util_col:
            df[util_col] = pd.to_numeric(
                df[util_col],
                errors="coerce",
            )
            sort_col = util_col

        if not sort_col:
            return pd.DataFrame()

        cols = [
            c for c in [
                symbol_col,
                asset_col,
                contrib_col,
                util_col,
            ] if c
        ]

        out = (
            df
            .sort_values(sort_col, ascending=False)
            [cols]
            .head(limit)
            .reset_index(drop=True)
        )

        return out

    # --------------------------------------------------------
    # NARRATIVE
    # --------------------------------------------------------

    def executive_brief(self) -> list[str]:
        s = self.snapshot
        brief: list[str] = []

        brief.append(
            f"Portfolio state is {s.portfolio_status.replace('_', ' ')} "
            f"across {s.instrument_count} instrument(s)."
        )

        brief.append(
            f"Maximum modeled risk-budget utilization is "
            f"{pct(s.maximum_risk_budget_utilization)}; "
            f"mean utilization is {pct(s.mean_risk_budget_utilization)}."
        )

        if s.breach_count or s.critical_count:
            brief.append(
                f"The risk monitor reports {s.breach_count} breach(es) "
                f"and {s.critical_count} critical item(s)."
            )

        brief.append(
            f"Governance workflow is "
            f"{s.workflow_status.replace('_', ' ')} with "
            f"{s.approval_queue_count} item(s) in the approval queue."
        )

        if s.risk_reduction_ticket_count:
            brief.append(
                f"{s.risk_reduction_ticket_count} risk-reduction "
                f"ticket(s) are active; "
                f"{s.immediate_priority_count} item(s) are immediate priority."
            )

        if s.maximum_estimated_post_remediation_utilization > 0:
            brief.append(
                f"Modeled remediation reduces maximum utilization to "
                f"{pct(s.maximum_estimated_post_remediation_utilization)}."
            )

        if s.automatic_execution_authorized_count == 0:
            brief.append(
                "Automatic execution remains disabled; "
                "human approval is still required."
            )
        else:
            brief.append(
                f"{s.automatic_execution_authorized_count} automatic "
                f"execution authorization(s) are present and require review."
            )

        return brief

    def human_attention_items(self) -> list[str]:
        s = self.snapshot
        items: list[str] = []

        if s.portfolio_status == "CRITICAL":
            items.append(
                "Portfolio is in a CRITICAL state and should remain under "
                "human risk/governance review."
            )

        if s.maximum_risk_budget_utilization > 1.0:
            items.append(
                f"Maximum risk-budget utilization is "
                f"{pct(s.maximum_risk_budget_utilization)}, above 100%."
            )

        if s.pending_review_count:
            items.append(
                f"{s.pending_review_count} decision ticket(s) remain pending."
            )

        if s.dual_approval_required_count:
            items.append(
                f"{s.dual_approval_required_count} item(s) require dual approval."
            )

        if s.immediate_priority_count:
            items.append(
                f"{s.immediate_priority_count} item(s) are marked immediate priority."
            )

        if not items:
            items.append(
                "No portfolio-level escalation is visible in the loaded outputs."
            )

        return items

    def governance_context(self) -> list[str]:
        items: list[str] = []

        if self.governance.empty:
            return ["Governance dataset is unavailable."]

        status_col = find_column(
            self.governance,
            ["governance_status"],
        )
        action_col = find_column(
            self.governance,
            ["governance_action"],
        )
        review_col = find_column(
            self.governance,
            ["requires_review"],
        )
        block_col = find_column(
            self.governance,
            ["block_incremental_risk"],
        )

        if status_col:
            counts = (
                self.governance[status_col]
                .astype(str)
                .value_counts()
                .to_dict()
            )
            items.append(
                "Governance status distribution: "
                + ", ".join(
                    f"{k}={v}" for k, v in counts.items()
                )
            )

        if action_col:
            counts = (
                self.governance[action_col]
                .astype(str)
                .value_counts()
                .to_dict()
            )
            items.append(
                "Governance action distribution: "
                + ", ".join(
                    f"{k}={v}" for k, v in counts.items()
                )
            )

        if review_col:
            count = int(
                self.governance[review_col]
                .map(safe_bool)
                .sum()
            )
            items.append(
                f"{count} instrument(s) require human review."
            )

        if block_col:
            count = int(
                self.governance[block_col]
                .map(safe_bool)
                .sum()
            )
            items.append(
                f"{count} instrument(s) are flagged to block incremental risk."
            )

        return items

    def remediation_context(self) -> list[str]:
        s = self.snapshot
        items: list[str] = []

        current_u = s.maximum_risk_budget_utilization
        post_u = s.maximum_estimated_post_remediation_utilization

        if current_u > 0 and post_u >= 0:
            reduction = current_u - post_u

            items.append(
                f"Modeled maximum utilization changes from "
                f"{pct(current_u)} to {pct(post_u)}."
            )

            items.append(
                f"That is a modeled reduction of "
                f"{reduction * 100:,.1f} percentage points."
            )

        if s.risk_reduction_ticket_count:
            items.append(
                f"{s.risk_reduction_ticket_count} risk-reduction "
                f"ticket(s) remain in the workflow."
            )

        return items or [
            "No portfolio-level remediation context is available."
        ]

    # --------------------------------------------------------
    # QUERY INTERFACE
    # --------------------------------------------------------

    def answer(self, question: str) -> str:
        q = clean(question).lower()

        if not q:
            return "Ask a portfolio, risk, governance, remediation or approval question."

        s = self.snapshot

        if "why" in q and "critical" in q:
            parts = [
                f"The loaded portfolio state is {s.portfolio_status}.",
                (
                    f"Maximum modeled risk-budget utilization is "
                    f"{pct(s.maximum_risk_budget_utilization)}."
                ),
                (
                    f"The risk monitor reports {s.breach_count} breach(es) "
                    f"and {s.critical_count} critical item(s)."
                ),
                (
                    f"The workflow is {s.workflow_status.replace('_', ' ')}."
                ),
            ]

            if s.risk_reduction_ticket_count:
                parts.append(
                    f"{s.risk_reduction_ticket_count} risk-reduction "
                    f"ticket(s) are active."
                )

            return " ".join(parts)

        if "approval" in q or "workflow" in q:
            return (
                f"Workflow status is {s.workflow_status.replace('_', ' ')}. "
                f"There are {s.approval_queue_count} item(s) in the approval queue, "
                f"{s.pending_review_count} pending decision(s), and "
                f"{s.dual_approval_required_count} item(s) requiring dual approval. "
                f"Automatic execution authorization count is "
                f"{s.automatic_execution_authorized_count}."
            )

        if "remediation" in q or "reduce" in q:
            return " ".join(self.remediation_context())

        if "risk" in q or "portfolio" in q:
            return (
                f"Portfolio status is {s.portfolio_status}. "
                f"Mean risk-budget utilization is "
                f"{pct(s.mean_risk_budget_utilization)} and maximum utilization is "
                f"{pct(s.maximum_risk_budget_utilization)}. "
                f"The monitor reports {s.breach_count} breach(es), "
                f"{s.critical_count} critical item(s), and "
                f"{s.requires_review_count} item(s) requiring review."
            )

        if "attention" in q or "review" in q or "priority" in q:
            return " ".join(self.human_attention_items())

        return (
            "The AI Risk Analyst answers portfolio risk, governance, "
            "remediation, approval/workflow and human-attention questions using "
            "the loaded Vittantra outputs. It does not invent external market facts. For research, markets and advisory questions, use the Copilot."
        )


# ============================================================
# STREAMLIT RENDERER
# ============================================================

def render_ai_analyst() -> None:
    """
    Render Day 73 inside vittantra_app.py.

    Usage in main app:
        from vittantra_ai_analyst import render_ai_analyst

        elif page == "AI Analyst":
            render_ai_analyst()
    """

    import streamlit as st

    analyst = VittantraAIAnalyst()
    s = analyst.snapshot

    st.markdown("### Vittantra AI Analyst")
    st.caption(
        "Explainable intelligence generated from Vittantra's "
        "risk, governance, remediation and approval outputs."
    )

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Portfolio State", s.portfolio_status.replace("_", " "))
    c2.metric("Max Risk Utilization", pct(s.maximum_risk_budget_utilization))
    c3.metric("Approval Queue", s.approval_queue_count)
    c4.metric("Immediate Priority", s.immediate_priority_count)

    st.divider()

    left, right = st.columns([1.3, 1])

    with left:
        st.markdown("#### Executive Brief")
        for item in analyst.executive_brief():
            st.write(f"• {item}")

    with right:
        st.markdown("#### Human Attention")
        for item in analyst.human_attention_items():
            st.warning(item)

    st.divider()

    tab1, tab2, tab3, tab4 = st.tabs(
        [
            "Risk Drivers",
            "Priority Instruments",
            "Governance",
            "Remediation",
        ]
    )

    with tab1:
        drivers = analyst.top_risk_drivers()
        if drivers.empty:
            st.info("Risk-driver detail is unavailable.")
        else:
            st.dataframe(
                drivers,
                width="stretch",
                hide_index=True,
            )

    with tab2:
        priority = analyst.priority_instruments()
        if priority.empty:
            st.info("Priority-instrument detail is unavailable.")
        else:
            st.dataframe(
                priority,
                width="stretch",
                hide_index=True,
            )

    with tab3:
        for item in analyst.governance_context():
            st.write(f"• {item}")

    with tab4:
        for item in analyst.remediation_context():
            st.write(f"• {item}")

    st.divider()

    st.markdown("#### Ask Vittantra")

    question = st.text_input(
        "Question",
        placeholder=(
            "Why is the portfolio critical? "
            "What requires human attention? "
            "What is the approval status?"
        ),
        label_visibility="collapsed",
    )

    if question:
        st.markdown("##### Analyst Response")
        st.write(analyst.answer(question))

    st.caption(
        "The AI Risk Analyst is a deterministic explanation layer over Vittantra's risk "
        "outputs. It does not fetch external market facts and does not execute trades."
    )


# ============================================================
# CLI VALIDATION
# ============================================================

def main() -> None:
    analyst = VittantraAIAnalyst()

    print("=" * 78)
    print("VITTANTRA — DAY 73 AI ANALYST")
    print("=" * 78)

    print("\nEXECUTIVE BRIEF")
    print("-" * 78)
    for item in analyst.executive_brief():
        print(f"- {item}")

    print("\nHUMAN ATTENTION")
    print("-" * 78)
    for item in analyst.human_attention_items():
        print(f"- {item}")

    print("\nTOP RISK DRIVERS")
    print("-" * 78)
    drivers = analyst.top_risk_drivers()
    print(
        drivers.to_string(index=False)
        if not drivers.empty
        else "Unavailable"
    )

    print("\nPRIORITY INSTRUMENTS")
    print("-" * 78)
    priority = analyst.priority_instruments()
    print(
        priority.to_string(index=False)
        if not priority.empty
        else "Unavailable"
    )

    print("\nDay 73 AI Analyst complete.")
    print("=" * 78)


if __name__ == "__main__":
    main()
