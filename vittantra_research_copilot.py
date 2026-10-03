"""
VITTANTRA
Day 74 — AI Research Copilot

Natural-language research and portfolio querying over Vittantra's own
risk, governance, remediation, and approval outputs.

Design principles
-----------------
1. Ground answers in local Vittantra CSV outputs.
2. Never invent unavailable portfolio facts.
3. Separate observed data from interpretation.
4. Preserve human review and approval.
5. Do not execute trades or alter portfolio state.

Standalone validation:
    python vittantra_research_copilot.py

Streamlit integration:
    from vittantra_research_copilot import render_research_copilot
    render_research_copilot()
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional
import re

import pandas as pd


BASE_DIR = Path(__file__).resolve().parent

FILES = {
    "risk_dashboard": BASE_DIR / "day67_portfolio_risk_dashboard.csv",
    "governance": BASE_DIR / "day68_instrument_governance_actions.csv",
    "remediation": BASE_DIR / "day69_portfolio_remediation_summary.csv",
    "approval": BASE_DIR / "day70_portfolio_approval_summary.csv",
}


# ============================================================
# BASIC HELPERS
# ============================================================

def load_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(path)
    except Exception:
        return pd.DataFrame()


def find_column(df: pd.DataFrame, candidates: list[str]) -> Optional[str]:
    for candidate in candidates:
        if candidate in df.columns:
            return candidate
    return None


def first_value(
    df: pd.DataFrame,
    candidates: list[str],
    default: Any = None,
) -> Any:
    if df.empty:
        return default

    for column in candidates:
        if column in df.columns:
            values = df[column].dropna()
            if not values.empty:
                return values.iloc[0]

    return default


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if pd.isna(value):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def safe_int(value: Any, default: int = 0) -> int:
    try:
        if pd.isna(value):
            return default
        return int(float(value))
    except (TypeError, ValueError):
        return default


def as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value

    text = str(value).strip().upper()
    return text in {
        "TRUE",
        "1",
        "YES",
        "Y",
        "REQUIRED",
        "BLOCK",
        "BLOCKED",
    }


def pct(value: Any) -> str:
    return f"{safe_float(value) * 100:,.1f}%"


def clean_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).replace("_", " ").strip()


def normalize_question(question: str) -> str:
    return re.sub(r"\s+", " ", question.lower().strip())


# ============================================================
# DATA MODEL
# ============================================================

@dataclass
class CopilotData:
    risk: pd.DataFrame
    governance: pd.DataFrame
    remediation: pd.DataFrame
    approval: pd.DataFrame

    @classmethod
    def load(cls) -> "CopilotData":
        return cls(
            risk=load_csv(FILES["risk_dashboard"]),
            governance=load_csv(FILES["governance"]),
            remediation=load_csv(FILES["remediation"]),
            approval=load_csv(FILES["approval"]),
        )

    @property
    def available_sources(self) -> list[str]:
        sources = []
        if not self.risk.empty:
            sources.append("Day 67 Risk Dashboard")
        if not self.governance.empty:
            sources.append("Day 68 Governance Actions")
        if not self.remediation.empty:
            sources.append("Day 69 Remediation Summary")
        if not self.approval.empty:
            sources.append("Day 70 Approval Workflow")
        return sources


@dataclass
class CopilotAnswer:
    title: str
    summary: str
    evidence: list[str]
    attention: list[str]
    source_names: list[str]
    intent: str

    def to_text(self) -> str:
        lines = [
            self.title,
            "",
            self.summary,
            "",
            "Evidence:",
        ]

        if self.evidence:
            lines.extend(f"- {item}" for item in self.evidence)
        else:
            lines.append("- No supporting portfolio evidence was available.")

        if self.attention:
            lines.extend(["", "Human attention:"])
            lines.extend(f"- {item}" for item in self.attention)

        if self.source_names:
            lines.extend(["", "Sources:"])
            lines.extend(f"- {item}" for item in self.source_names)

        return "\n".join(lines)


# ============================================================
# COPILOT ENGINE
# ============================================================

class VittantraResearchCopilot:
    """
    Deterministic research copilot grounded in Vittantra's local outputs.

    Day 74 intentionally does not require an external LLM/API. Questions
    are routed to evidence-backed analytical handlers.
    """

    def __init__(self, data: Optional[CopilotData] = None) -> None:
        self.data = data or CopilotData.load()

    # --------------------------------------------------------
    # Portfolio state
    # --------------------------------------------------------

    def portfolio_status(self) -> str:
        return str(
            first_value(
                self.data.risk,
                ["portfolio_status"],
                "UNKNOWN",
            )
        )

    def instrument_count(self) -> int:
        count = safe_int(
            first_value(
                self.data.risk,
                ["instrument_count"],
                0,
            )
        )

        if count == 0 and not self.data.governance.empty:
            symbol_col = find_column(
                self.data.governance,
                ["symbol", "ticker", "instrument"],
            )
            if symbol_col:
                count = int(self.data.governance[symbol_col].nunique())
            else:
                count = len(self.data.governance)

        return count

    def mean_utilization(self) -> float:
        value = safe_float(
            first_value(
                self.data.risk,
                ["mean_risk_budget_utilization"],
                0.0,
            )
        )

        if value == 0 and not self.data.governance.empty:
            col = find_column(
                self.data.governance,
                ["risk_budget_utilization"],
            )
            if col:
                series = pd.to_numeric(
                    self.data.governance[col],
                    errors="coerce",
                ).dropna()
                if not series.empty:
                    value = safe_float(series.mean())

        return value

    def max_utilization(self) -> float:
        value = safe_float(
            first_value(
                self.data.approval,
                ["maximum_current_risk_budget_utilization"],
                0.0,
            )
        )

        if value == 0:
            value = safe_float(
                first_value(
                    self.data.risk,
                    ["maximum_risk_budget_utilization"],
                    0.0,
                )
            )

        if value == 0 and not self.data.governance.empty:
            col = find_column(
                self.data.governance,
                ["risk_budget_utilization"],
            )
            if col:
                series = pd.to_numeric(
                    self.data.governance[col],
                    errors="coerce",
                ).dropna()
                if not series.empty:
                    value = safe_float(series.max())

        return value

    def post_remediation_utilization(self) -> float:
        return safe_float(
            first_value(
                self.data.approval,
                ["maximum_estimated_post_remediation_utilization"],
                0.0,
            )
        )

    def workflow_status(self) -> str:
        return str(
            first_value(
                self.data.approval,
                ["portfolio_workflow_status"],
                "UNKNOWN",
            )
        )

    def approval_queue(self) -> int:
        return safe_int(
            first_value(
                self.data.approval,
                ["approval_queue_count"],
                0,
            )
        )

    def immediate_priority_count(self) -> int:
        return safe_int(
            first_value(
                self.data.approval,
                ["immediate_priority_count"],
                0,
            )
        )

    def dual_approval_count(self) -> int:
        return safe_int(
            first_value(
                self.data.approval,
                ["dual_approval_required_count"],
                0,
            )
        )

    def risk_reduction_ticket_count(self) -> int:
        return safe_int(
            first_value(
                self.data.approval,
                ["risk_reduction_ticket_count"],
                0,
            )
        )

    def automatic_execution_count(self) -> int:
        return safe_int(
            first_value(
                self.data.approval,
                ["automatic_execution_authorized_count"],
                0,
            )
        )

    # --------------------------------------------------------
    # Instrument analysis
    # --------------------------------------------------------

    def instrument_table(self) -> pd.DataFrame:
        if self.data.governance.empty:
            return pd.DataFrame()

        df = self.data.governance.copy()

        numeric_candidates = [
            "risk_budget",
            "modeled_risk_contribution",
            "risk_budget_utilization",
            "risk_budget_excess",
        ]

        for col in numeric_candidates:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")

        return df

    def highest_utilization(self, n: int = 5) -> pd.DataFrame:
        df = self.instrument_table()
        if df.empty:
            return pd.DataFrame()

        util_col = find_column(df, ["risk_budget_utilization"])
        if not util_col:
            return pd.DataFrame()

        return (
            df.dropna(subset=[util_col])
            .sort_values(util_col, ascending=False)
            .head(n)
            .copy()
        )

    def highest_risk_contributors(self, n: int = 5) -> pd.DataFrame:
        df = self.instrument_table()
        if df.empty:
            return pd.DataFrame()

        risk_col = find_column(df, ["modeled_risk_contribution"])
        if not risk_col:
            return pd.DataFrame()

        result = df.dropna(subset=[risk_col]).copy()
        result["_absolute_risk"] = result[risk_col].abs()

        return (
            result.sort_values("_absolute_risk", ascending=False)
            .head(n)
            .drop(columns=["_absolute_risk"])
        )

    def breached_instruments(self) -> pd.DataFrame:
        df = self.instrument_table()
        if df.empty:
            return pd.DataFrame()

        util_col = find_column(df, ["risk_budget_utilization"])
        if not util_col:
            return pd.DataFrame()

        return (
            df[df[util_col] > 1.0]
            .sort_values(util_col, ascending=False)
            .copy()
        )

    def review_instruments(self) -> pd.DataFrame:
        df = self.instrument_table()
        if df.empty:
            return pd.DataFrame()

        review_col = find_column(df, ["requires_review"])
        block_col = find_column(df, ["block_incremental_risk"])

        if not review_col and not block_col:
            return pd.DataFrame()

        mask = pd.Series(False, index=df.index)

        if review_col:
            mask = mask | df[review_col].map(as_bool)

        if block_col:
            mask = mask | df[block_col].map(as_bool)

        util_col = find_column(df, ["risk_budget_utilization"])

        result = df[mask].copy()

        if util_col and not result.empty:
            result = result.sort_values(util_col, ascending=False)

        return result

    def concentration_statistics(self) -> dict[str, float]:
        df = self.instrument_table()

        if df.empty:
            return {
                "top1": 0.0,
                "top3": 0.0,
                "hhi": 0.0,
                "effective_positions": 0.0,
            }

        risk_col = find_column(df, ["modeled_risk_contribution"])

        if not risk_col:
            return {
                "top1": 0.0,
                "top3": 0.0,
                "hhi": 0.0,
                "effective_positions": 0.0,
            }

        values = pd.to_numeric(
            df[risk_col],
            errors="coerce",
        ).dropna().abs()

        total = safe_float(values.sum())

        if total <= 0:
            return {
                "top1": 0.0,
                "top3": 0.0,
                "hhi": 0.0,
                "effective_positions": 0.0,
            }

        shares = (values / total).sort_values(ascending=False)
        hhi = safe_float((shares ** 2).sum())

        return {
            "top1": safe_float(shares.iloc[0]),
            "top3": safe_float(shares.head(3).sum()),
            "hhi": hhi,
            "effective_positions": 1 / hhi if hhi > 0 else 0.0,
        }

    # --------------------------------------------------------
    # Intent routing
    # --------------------------------------------------------

    def classify_intent(self, question: str) -> str:
        q = normalize_question(question)

        if any(
            phrase in q
            for phrase in [
                "which positions contribute",
                "which position contributes",
                "risk contributor",
                "risk contribution",
                "contribute the most risk",
                "largest risk",
                "most risk",
            ]
        ):
            return "risk_contributors"

        if any(
            phrase in q
            for phrase in [
                "immediate review",
                "require review",
                "requires review",
                "need review",
                "human review",
                "blocked",
                "block incremental",
                "priority",
            ]
        ):
            return "review"

        if any(
            phrase in q
            for phrase in [
                "approval",
                "workflow",
                "dual approval",
                "decision ticket",
            ]
        ):
            return "approval"

        if any(
            phrase in q
            for phrase in [
                "remediation",
                "reduce risk",
                "below the risk budget",
                "below risk budget",
                "get below",
                "what would need to change",
            ]
        ):
            return "remediation"

        if any(
            phrase in q
            for phrase in [
                "concentration",
                "top 3",
                "top three",
                "effective risk",
                "diversif",
            ]
        ):
            return "concentration"

        if any(
            phrase in q
            for phrase in [
                "breach",
                "above budget",
                "over budget",
                "utilization",
                "highest utilization",
            ]
        ):
            return "utilization"

        if any(
            phrase in q
            for phrase in [
                "why is the portfolio critical",
                "why critical",
                "portfolio critical",
                "portfolio state",
                "portfolio status",
                "explain the portfolio",
                "explain risk",
                "portfolio risk",
            ]
        ):
            return "portfolio"

        return "overview"

    # --------------------------------------------------------
    # Answer builders
    # --------------------------------------------------------

    def answer(self, question: str) -> CopilotAnswer:
        intent = self.classify_intent(question)

        handlers = {
            "portfolio": self._answer_portfolio,
            "risk_contributors": self._answer_risk_contributors,
            "review": self._answer_review,
            "approval": self._answer_approval,
            "remediation": self._answer_remediation,
            "concentration": self._answer_concentration,
            "utilization": self._answer_utilization,
            "overview": self._answer_overview,
        }

        return handlers[intent]()

    def _base_attention(self) -> list[str]:
        attention = []

        if self.max_utilization() > 1.0:
            attention.append(
                f"Maximum modeled risk-budget utilization is "
                f"{pct(self.max_utilization())}, above 100%."
            )

        if self.portfolio_status().upper() == "CRITICAL":
            attention.append(
                "Portfolio state is CRITICAL; Vittantra keeps the "
                "decision under human risk/governance review."
            )

        if self.automatic_execution_count() == 0:
            attention.append(
                "Automatic execution authorization count is zero."
            )
        else:
            attention.append(
                f"{self.automatic_execution_count()} automatic execution "
                f"authorization(s) are present in the loaded workflow output."
            )

        return attention

    def _answer_portfolio(self) -> CopilotAnswer:
        evidence = [
            f"Portfolio status: {clean_text(self.portfolio_status())}.",
            f"Instrument count: {self.instrument_count()}.",
            f"Mean modeled risk-budget utilization: {pct(self.mean_utilization())}.",
            f"Maximum modeled risk-budget utilization: {pct(self.max_utilization())}.",
            f"Workflow: {clean_text(self.workflow_status())}.",
            f"Approval queue: {self.approval_queue()}.",
            f"Immediate-priority items: {self.immediate_priority_count()}.",
        ]

        summary = (
            f"The loaded Vittantra outputs classify the portfolio as "
            f"{clean_text(self.portfolio_status())}. The strongest portfolio-level "
            f"risk signal is maximum modeled risk-budget utilization of "
            f"{pct(self.max_utilization())}. This is a description of the model "
            f"outputs, not an independent investment recommendation."
        )

        return CopilotAnswer(
            title="Portfolio Risk Explanation",
            summary=summary,
            evidence=evidence,
            attention=self._base_attention(),
            source_names=self.data.available_sources,
            intent="portfolio",
        )

    def _answer_risk_contributors(self) -> CopilotAnswer:
        table = self.highest_risk_contributors(5)
        evidence = []

        if table.empty:
            summary = (
                "The loaded files do not provide enough instrument-level "
                "modeled-risk contribution data to rank contributors."
            )
        else:
            symbol_col = find_column(
                table,
                ["symbol", "ticker", "instrument"],
            )
            risk_col = find_column(
                table,
                ["modeled_risk_contribution"],
            )
            util_col = find_column(
                table,
                ["risk_budget_utilization"],
            )

            for _, row in table.iterrows():
                symbol = (
                    clean_text(row[symbol_col])
                    if symbol_col
                    else "Unnamed instrument"
                )

                parts = []

                if risk_col:
                    parts.append(
                        f"modeled risk contribution "
                        f"{safe_float(row[risk_col]):,.4f}"
                    )

                if util_col:
                    parts.append(
                        f"risk-budget utilization "
                        f"{pct(row[util_col])}"
                    )

                evidence.append(
                    f"{symbol}: " + ", ".join(parts) + "."
                )

            summary = (
                "These are the largest instrument-level absolute modeled-risk "
                "contributors in the loaded Day 68 governance dataset."
            )

        return CopilotAnswer(
            title="Largest Modeled-Risk Contributors",
            summary=summary,
            evidence=evidence,
            attention=self._base_attention(),
            source_names=[
                s for s in self.data.available_sources
                if "Governance" in s or "Risk" in s
            ],
            intent="risk_contributors",
        )

    def _answer_review(self) -> CopilotAnswer:
        table = self.review_instruments()
        evidence = []

        if table.empty:
            summary = (
                "No instrument-level review/block flags could be identified "
                "from the loaded governance output."
            )
        else:
            symbol_col = find_column(
                table,
                ["symbol", "ticker", "instrument"],
            )
            util_col = find_column(
                table,
                ["risk_budget_utilization"],
            )
            action_col = find_column(
                table,
                ["governance_action"],
            )
            reason_col = find_column(
                table,
                ["governance_reason"],
            )

            for _, row in table.iterrows():
                symbol = (
                    clean_text(row[symbol_col])
                    if symbol_col
                    else "Unnamed instrument"
                )

                details = []

                if util_col:
                    details.append(f"utilization {pct(row[util_col])}")

                if action_col:
                    details.append(
                        f"action: {clean_text(row[action_col])}"
                    )

                if reason_col:
                    reason = clean_text(row[reason_col])
                    if reason and reason.lower() != "nan":
                        details.append(f"reason: {reason}")

                evidence.append(
                    f"{symbol}: " + "; ".join(details) + "."
                )

            summary = (
                f"{len(table)} instrument(s) are flagged by the loaded "
                f"governance data for review and/or incremental-risk control."
            )

        return CopilotAnswer(
            title="Human Review Queue",
            summary=summary,
            evidence=evidence,
            attention=self._base_attention(),
            source_names=[
                s for s in self.data.available_sources
                if "Governance" in s or "Approval" in s
            ],
            intent="review",
        )

    def _answer_approval(self) -> CopilotAnswer:
        evidence = [
            f"Workflow status: {clean_text(self.workflow_status())}.",
            f"Approval queue: {self.approval_queue()}.",
            f"Immediate-priority count: {self.immediate_priority_count()}.",
            f"Dual approvals required: {self.dual_approval_count()}.",
            f"Risk-reduction tickets: {self.risk_reduction_ticket_count()}.",
            f"Automatic execution authorizations: "
            f"{self.automatic_execution_count()}.",
        ]

        summary = (
            f"The current workflow is "
            f"{clean_text(self.workflow_status())}. Vittantra is reporting "
            f"workflow state only; it does not approve or execute trades."
        )

        return CopilotAnswer(
            title="Approval & Governance Status",
            summary=summary,
            evidence=evidence,
            attention=self._base_attention(),
            source_names=[
                s for s in self.data.available_sources
                if "Approval" in s or "Governance" in s
            ],
            intent="approval",
        )

    def _answer_remediation(self) -> CopilotAnswer:
        current = self.max_utilization()
        post = self.post_remediation_utilization()

        evidence = [
            f"Current maximum utilization: {pct(current)}.",
        ]

        if post > 0:
            evidence.append(
                f"Estimated post-remediation maximum utilization: {pct(post)}."
            )

            change = current - post
            evidence.append(
                f"Modeled change: {change * 100:,.1f} percentage points."
            )

        evidence.append(
            f"Risk-reduction tickets: {self.risk_reduction_ticket_count()}."
        )

        if post > 1.0:
            summary = (
                "The loaded remediation/approval outputs still estimate maximum "
                "risk-budget utilization above 100% after remediation. The Day 74 "
                "copilot will not invent additional trades or position sizes to "
                "force the portfolio below budget."
            )
        elif post > 0:
            summary = (
                "The loaded remediation outputs estimate maximum utilization "
                "at or below 100% after the modeled remediation process. Any "
                "implementation remains subject to the approval workflow."
            )
        else:
            summary = (
                "The loaded outputs do not provide a usable post-remediation "
                "utilization estimate. Vittantra therefore cannot quantify the "
                "change required to reach the modeled risk budget from these "
                "files alone."
            )

        return CopilotAnswer(
            title="Risk Remediation Analysis",
            summary=summary,
            evidence=evidence,
            attention=self._base_attention(),
            source_names=[
                s for s in self.data.available_sources
                if "Remediation" in s or "Approval" in s
            ],
            intent="remediation",
        )

    def _answer_concentration(self) -> CopilotAnswer:
        stats = self.concentration_statistics()

        if stats["effective_positions"] == 0:
            summary = (
                "Instrument-level modeled-risk contribution data are not "
                "available in a form that supports concentration analysis."
            )
            evidence = []
        else:
            summary = (
                "Concentration is calculated from each instrument's absolute "
                "modeled-risk contribution in the loaded governance dataset."
            )
            evidence = [
                f"Largest risk share: {pct(stats['top1'])}.",
                f"Top-three risk share: {pct(stats['top3'])}.",
                f"HHI of modeled-risk shares: {stats['hhi']:,.4f}.",
                f"Effective risk positions: "
                f"{stats['effective_positions']:,.2f}.",
            ]

        return CopilotAnswer(
            title="Portfolio Risk Concentration",
            summary=summary,
            evidence=evidence,
            attention=self._base_attention(),
            source_names=[
                s for s in self.data.available_sources
                if "Governance" in s
            ],
            intent="concentration",
        )

    def _answer_utilization(self) -> CopilotAnswer:
        table = self.highest_utilization(5)
        breaches = self.breached_instruments()
        evidence = [
            f"Mean modeled utilization: {pct(self.mean_utilization())}.",
            f"Maximum modeled utilization: {pct(self.max_utilization())}.",
            f"Instrument-level observations above 100%: {len(breaches)}.",
        ]

        if not table.empty:
            symbol_col = find_column(
                table,
                ["symbol", "ticker", "instrument"],
            )
            util_col = find_column(
                table,
                ["risk_budget_utilization"],
            )

            for _, row in table.iterrows():
                symbol = (
                    clean_text(row[symbol_col])
                    if symbol_col
                    else "Unnamed instrument"
                )
                evidence.append(
                    f"{symbol}: {pct(row[util_col])} utilization."
                )

        summary = (
            "This view compares modeled risk-budget utilization across the "
            "loaded portfolio outputs. A value above 100% indicates modeled "
            "utilization above the assigned risk budget."
        )

        return CopilotAnswer(
            title="Risk-Budget Utilization",
            summary=summary,
            evidence=evidence,
            attention=self._base_attention(),
            source_names=[
                s for s in self.data.available_sources
                if "Risk" in s or "Governance" in s
            ],
            intent="utilization",
        )

    def _answer_overview(self) -> CopilotAnswer:
        evidence = [
            f"Portfolio status: {clean_text(self.portfolio_status())}.",
            f"Maximum modeled utilization: {pct(self.max_utilization())}.",
            f"Workflow: {clean_text(self.workflow_status())}.",
            f"Approval queue: {self.approval_queue()}.",
        ]

        summary = (
            "Day 74 can answer evidence-backed questions about portfolio state, "
            "risk utilization, modeled-risk contributors, concentration, "
            "governance review, remediation and approvals. The question did "
            "not map to a more specific supported analytical intent."
        )

        return CopilotAnswer(
            title="Vittantra Research Copilot",
            summary=summary,
            evidence=evidence,
            attention=self._base_attention(),
            source_names=self.data.available_sources,
            intent="overview",
        )

    # --------------------------------------------------------
    # Suggested questions
    # --------------------------------------------------------

    @staticmethod
    def suggested_questions() -> list[str]:
        return [
            "Why is the portfolio critical?",
            "Which positions contribute the most risk?",
            "Which positions require immediate review?",
            "Which instruments have the highest risk-budget utilization?",
            "What is the current approval status?",
            "What would need to change to get below the risk budget?",
            "How concentrated is the portfolio's modeled risk?",
        ]


# ============================================================
# STREAMLIT RENDERER
# ============================================================

def render_research_copilot() -> None:
    """
    Render Day 74 inside the existing Vittantra Streamlit application.

    Streamlit is imported here so the analytical engine remains usable
    and testable as a normal Python module.
    """
    import streamlit as st

    copilot = VittantraResearchCopilot()

    st.markdown("### Vittantra Research Copilot")
    st.caption(
        "Day 74 — natural-language portfolio research grounded in "
        "Vittantra's risk, governance, remediation and approval outputs."
    )

    sources = copilot.data.available_sources

    if sources:
        st.success(
            f"Connected to {len(sources)} Vittantra analytical source(s)."
        )
    else:
        st.error(
            "No supported Vittantra output files are currently available."
        )
        return

    c1, c2, c3, c4 = st.columns(4)

    c1.metric(
        "Portfolio State",
        clean_text(copilot.portfolio_status()),
    )
    c2.metric(
        "Max Risk Utilization",
        pct(copilot.max_utilization()),
    )
    c3.metric(
        "Approval Queue",
        copilot.approval_queue(),
    )
    c4.metric(
        "Immediate Priority",
        copilot.immediate_priority_count(),
    )

    st.divider()

    st.markdown("#### Ask Vittantra")

    question = st.text_input(
        "Research question",
        placeholder="Example: Which positions contribute the most risk?",
        key="day74_research_question",
    )

    ask_clicked = st.button(
        "Analyze",
        type="primary",
        key="day74_analyze_button",
    )

    if question and (ask_clicked or question):
        answer = copilot.answer(question)

        st.markdown(f"#### {answer.title}")
        st.write(answer.summary)

        if answer.evidence:
            st.markdown("##### Evidence")
            for item in answer.evidence:
                st.write(f"• {item}")

        if answer.attention:
            st.markdown("##### Human Attention")
            for item in answer.attention:
                st.warning(item)

        with st.expander("Data provenance", expanded=False):
            st.write(
                "Answer intent:",
                answer.intent.replace("_", " ").title(),
            )
            st.write("Loaded sources:")
            for source in answer.source_names:
                st.write(f"• {source}")

    st.divider()

    st.markdown("#### Suggested Questions")

    for item in copilot.suggested_questions():
        st.write(f"• {item}")

    st.info(
        "Day 74 is a research and decision-support layer. It does not "
        "place orders, modify portfolio state, approve decisions, or "
        "invent unavailable portfolio facts."
    )


# ============================================================
# STANDALONE VALIDATION
# ============================================================

def main() -> None:
    copilot = VittantraResearchCopilot()

    print("=" * 78)
    print("VITTANTRA — DAY 74 RESEARCH COPILOT")
    print("=" * 78)

    print("\nConnected sources:")
    if copilot.data.available_sources:
        for source in copilot.data.available_sources:
            print(f"- {source}")
    else:
        print("- None")

    print("\nPortfolio snapshot:")
    print(f"Status: {clean_text(copilot.portfolio_status())}")
    print(f"Instruments: {copilot.instrument_count()}")
    print(f"Mean utilization: {pct(copilot.mean_utilization())}")
    print(f"Maximum utilization: {pct(copilot.max_utilization())}")
    print(f"Workflow: {clean_text(copilot.workflow_status())}")
    print(f"Approval queue: {copilot.approval_queue()}")
    print(
        f"Automatic execution authorizations: "
        f"{copilot.automatic_execution_count()}"
    )

    print("\nValidation questions:")

    tests = [
        "Why is the portfolio critical?",
        "Which positions contribute the most risk?",
        "Which positions require immediate review?",
        "What is the current approval status?",
        "What would need to change to get below the risk budget?",
    ]

    for question in tests:
        answer = copilot.answer(question)
        print("\n" + "-" * 78)
        print(f"Q: {question}")
        print(f"Intent: {answer.intent}")
        print(f"A: {answer.summary}")

    print("\n" + "=" * 78)
    print("Day 74 Research Copilot validation complete.")
    print("No trades were submitted or executed.")
    print("=" * 78)


if __name__ == "__main__":
    main()
