"""
Day 85 — Vittantra Copilot (evidence-grounded, across all desks)

Ask in plain English; the answer is built only from Vittantra's own outputs,
with every statement cited to its source file and field.

How it works
------------
1. Knowledge base: every output (research notes, valuations, ratings, model
   portfolio, attribution, what-if tickets, macro drivers, world brief,
   economic dashboard, advisory clients, risk governance) is turned into
   small evidence records: (desk, entity, statement, source, field, value).
2. Retrieval: the question is matched to records by entity (ticker, company,
   client, sleeve, theme) and by topic words. If nothing relevant scores
   above a threshold, the copilot says so — it does not guess.
3. Answer: a template answer lists the evidence with citations. Optionally a
   free local model (Ollama, set VITTANTRA_LLM=ollama) rewrites it in plain
   language; the rewrite is accepted only if every number in it appears in
   the evidence, otherwise the template answer is used.
4. Guardrails: requests to trade or execute are refused (Vittantra never
   executes); "should I buy" questions get the research view and a reminder
   that decisions go through the approval workflow to a human.

No paid APIs. No invented data.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Dict, List, Optional

import pandas as pd


BASE_DIR = Path(__file__).resolve().parent
MIN_SCORE = 2.0
MAX_EVIDENCE = 8

STOPWORDS = set("""a an the is are was were be been of to in on for and or with what which who whom why how
does do did can could should would will about tell me show give my our your this that these those it its as at by
from vs versus than then there their them they please much many any some most more less""".split())

TOPICS = {
    "valuation": ["valuation", "value", "worth", "fair", "intrinsic", "dcf", "cheap", "expensive", "overvalued",
                  "undervalued", "upside", "price", "target", "wacc", "growth", "implied", "ddm", "residual"],
    "rating": ["rating", "rated", "score", "overweight", "underweight", "neutral", "pillar", "factor", "rank",
               "recommend", "recommendation", "buy", "sell", "hold"],
    "bull": ["bull", "positive", "strength", "strengths", "why", "case", "thesis", "good"],
    "bear": ["bear", "negative", "risk", "risks", "weakness", "weaknesses", "concern", "concerns", "bad", "downside"],
    "portfolio": ["portfolio", "model", "weight", "weights", "holding", "holdings", "optimizer", "tracking", "alpha",
                  "active", "benchmark", "information", "ir"],
    "attribution": ["attribution", "allocation", "selection", "outperform", "outperformed", "underperform",
                    "performance", "beat", "lag", "sector", "brinson"],
    "macro": ["macro", "rates", "rate", "yield", "yields", "inflation", "credit", "spread", "spreads", "dollar",
              "oil", "fed", "economy", "economic", "cpi", "jobs", "gdp", "moved", "drivers", "driver"],
    "news": ["news", "headline", "headlines", "happening", "world", "week", "calendar", "upcoming", "coming", "event"],
    "advisory": ["client", "clients", "suitability", "suitable", "goal", "goals", "retirement", "profile",
                 "questionnaire", "allocation", "monte", "carlo", "probability", "ips", "advisor"],
    "risk": ["risk", "var", "volatility", "governance", "breach", "budget", "remediation", "approval", "ticket",
             "tickets", "utilization", "concentration", "stress", "scenario"],
}

TOPIC_DESK = {"valuation": "Research", "rating": "Research", "bull": "Research", "bear": "Research",
              "portfolio": "Portfolio", "attribution": "Portfolio", "macro": "Markets", "news": "Markets",
              "advisory": "Advisory", "risk": "Risk"}
OPPOSITE = {"bull": "bear", "bear": "bull"}

TRADE_REQUEST = re.compile(r"\b(execute|place|submit|send)\b.*\b(order|trade|trades)\b|\b(buy|sell|short)\b.*\bfor me\b"
                           r"|\btrade (it|this|them) (now|for me)\b", re.IGNORECASE)
ADVICE_REQUEST = re.compile(r"\bshould i (buy|sell|invest|short)\b", re.IGNORECASE)


@dataclass
class Evidence:
    desk: str
    entity: str
    statement: str
    source: str
    field: str
    value: str
    keywords: set = field(default_factory=set)
    topic: str = ""


@dataclass
class Answer:
    question: str
    text: str
    evidence: List[Evidence]
    grounded: bool
    mode: str            # "template", "llm", "refused", "no_data"

    def citations(self) -> List[str]:
        return [f"[{i}] {e.source} → {e.field} = {e.value}" for i, e in enumerate(self.evidence, start=1)]


def _words(text: str) -> List[str]:
    return [w for w in re.findall(r"[a-z0-9][a-z0-9\-\.&=]*", text.lower()) if w not in STOPWORDS]


def _fmt(value) -> str:
    if isinstance(value, float):
        return f"{value:.4g}"
    return str(value)


# ==============================================================
# KNOWLEDGE BASE
# ==============================================================

class KnowledgeBase:
    def __init__(self, base: Path = BASE_DIR):
        self.base = Path(base)
        self.records: List[Evidence] = []
        self.entities: Dict[str, str] = {}          # alias (lower) → entity id
        self.sources: List[str] = []
        for loader in (self._research, self._valuation, self._ratings, self._portfolio, self._attribution,
                       self._macro, self._news, self._economy, self._advisory, self._risk):
            try:
                loader()
            except Exception:
                continue

    def _csv(self, name: str) -> Optional[pd.DataFrame]:
        path = self.base / name
        if not path.exists():
            return None
        self.sources.append(name)
        return pd.read_csv(path)

    def add(self, desk, entity, statement, source, field_name, value, *topics):
        words = set(_words(statement)) | set(topics) | {entity.lower()}
        for topic in topics:
            words |= set(TOPICS.get(topic, []))
        self.records.append(Evidence(desk, entity, statement, source, field_name, _fmt(value), words,
                                     topics[0] if topics else ""))

    def alias(self, entity: str, *names):
        for name in (entity, *names):
            if isinstance(name, str) and name.strip():
                self.entities[name.lower()] = entity
                first = name.lower().split(" —")[0].split(" (")[0]
                self.entities.setdefault(first, entity)

    # ---- loaders --------------------------------------------------------
    def _research(self):
        claims = self._csv("day78_research_claims.csv")
        summary = self._csv("day78_report_summary.csv")
        if summary is not None:
            for r in summary.itertuples():
                self.alias(r.ticker, r.name)
        if claims is None:
            return
        section_topic = {"Thesis": "rating", "Valuation": "valuation", "Bull case": "bull", "Bear case": "bear",
                         "Risks and limits": "bear"}
        for r in claims.itertuples():
            self.add("Research", r.ticker, f"{r.ticker} ({r.section}): {r.claim}", r.source_file, r.field, r.value,
                     section_topic.get(r.section, "rating"))

    def _valuation(self):
        v = self._csv("day78_valuation.csv")
        if v is None:
            return
        noted = {e.entity for e in self.records if e.source == "day78_research_claims.csv" and e.topic == "valuation"}
        for r in v.dropna(subset=["fair_value"]).itertuples():
            if r.ticker in noted:            # the research note already states the valuation
                continue
            self.add("Research", r.ticker, f"{r.ticker}: {r.primary_model} intrinsic value ${r.fair_value:,.2f} vs price "
                     f"${r.price:,.2f} ({r.upside:+.0%}), {r.valuation_signal}; WACC {r.wacc:.1%}.",
                     "day78_valuation.csv", "fair_value", r.fair_value, "valuation")

    def _ratings(self):
        r = self._csv("day77_current_ratings.csv")
        ic = self._csv("day77_ic_summary.csv")
        if r is not None:
            for x in r.itertuples():
                self.alias(x.ticker, x.name)
                self.add("Research", x.ticker, f"{x.ticker} ({x.name}) is rated {x.rating} with IC-weighted score "
                         f"{x.composite_ic_weighted:.0f}/100; strongest pillar {x.strongest_pillar}, weakest "
                         f"{x.weakest_pillar}.", "day77_current_ratings.csv", "rating", x.rating, "rating")
            top = r.sort_values("composite_ic_weighted", ascending=False).head(5)
            self.add("Research", "universe", "Top-rated stocks now: " + ", ".join(
                f"{t.ticker} ({t.composite_ic_weighted:.0f})" for t in top.itertuples()) + ".",
                "day77_current_ratings.csv", "composite_ic_weighted", float(top.iloc[0]["composite_ic_weighted"]),
                "rating", "portfolio")
        if ic is not None:
            for x in ic.dropna(subset=["mean_ic"]).itertuples():
                self.add("Research", "signals", f"Signal {x.signal}: mean IC {x.mean_ic:.3f}, t-stat {x.ic_t_stat:.2f} "
                         f"over {x.dates} dates.", "day77_ic_summary.csv", "mean_ic", x.mean_ic, "rating")

    def _portfolio(self):
        s = self._csv("day79_portfolio_summary.csv")
        p = self._csv("day79_model_portfolio.csv")
        if s is not None:
            x = s.iloc[0]
            self.add("Portfolio", "model portfolio", f"Model portfolio: {int(x['holdings'])} holdings, expected active "
                     f"return {x['expected_active_return']:+.2%} a year, tracking error {x['tracking_error']:.2%} "
                     f"(budget {x['tracking_error_budget']:.0%}), IR {x['information_ratio']:.2f}, beta "
                     f"{x['beta_to_benchmark']:.2f}; status {x['approval_status']}.", "day79_portfolio_summary.csv",
                     "expected_active_return", x["expected_active_return"], "portfolio")
        if p is not None:
            held = p[p["weight"] > 0].sort_values("risk_share", ascending=False)
            top = held.head(3)
            self.add("Portfolio", "model portfolio", "Largest sources of model-portfolio risk: " + ", ".join(
                f"{r.ticker} {r.risk_share:.1%} of risk at {r.weight:.1%} weight" for r in top.itertuples()) + ".",
                "day79_model_portfolio.csv", "risk_share", float(top.iloc[0]["risk_share"]), "risk", "portfolio")
            for r in held.itertuples():
                self.add("Portfolio", r.ticker, f"{r.ticker} is {r.weight:.1%} of the model portfolio (benchmark "
                         f"{r.benchmark_weight:.1%}, {r.risk_share:.1%} of portfolio risk).",
                         "day79_model_portfolio.csv", "weight", r.weight, "portfolio")

    def _attribution(self):
        s = self._csv("day80_attribution_summary.csv")
        sectors = self._csv("day80_brinson_by_sector.csv")
        if s is not None:
            x = s.iloc[0]
            self.add("Portfolio", "attribution", f"Backtested research portfolio {x['portfolio_cumulative']:+.1%} vs "
                     f"benchmark {x['benchmark_cumulative']:+.1%} ({x['start']} to {x['end']}): allocation "
                     f"{x['allocation_linked']:+.1%}, selection {x['selection_linked']:+.1%}, interaction "
                     f"{x['interaction_linked']:+.1%}, costs {x['costs_linked']:+.1%}.", "day80_attribution_summary.csv",
                     "active_cumulative", x["active_cumulative"], "attribution")
        if sectors is not None:
            for r in sectors.itertuples():
                self.add("Portfolio", r.sector, f"Attribution, {r.sector}: total {r.total:+.2%} (allocation "
                         f"{r.allocation:+.2%}, selection {r.selection:+.2%}).", "day80_brinson_by_sector.csv",
                         "total", r.total, "attribution")

    def _macro(self):
        stories = self._csv("day76d_macro_narrative.csv")
        moves = self._csv("day76d_factor_moves.csv")
        if stories is not None:
            for r in stories.itertuples():
                self.alias(r.symbol)
                self.add("Markets", r.asset_class, f"{r.asset_class} ({r.symbol}): {r.story}",
                         "day76d_macro_narrative.csv", "story", r.symbol, "macro")
        if moves is not None:
            for r in moves[moves["window"] == "1 month"].itertuples():
                unit = f"{r.move * 100:+.0f} bp" if r.unit == "percentage points" else f"{r.move:+.1%}"
                factor_words = r.factor.replace("_", " ")
                label = r.label.lower() if factor_words in r.label.lower() else f"{r.label.lower()} ({factor_words})"
                self.add("Markets", r.label, f"Over the last month, {label} moved {unit}.",
                         "day76d_factor_moves.csv", "move", r.move, "macro", "macro_factor")

    def _news(self):
        brief = self._csv("day78b_brief.csv")
        calendar = self._csv("day78b_calendar.csv")
        if brief is not None:
            for r in brief.itertuples():
                text = f"This week, {r.theme}: {r.data_move}."
                if r.headline_count:
                    text += " Headlines: " + str(r.top_headlines).replace(" || ", "; ")
                self.add("Markets", r.theme, text, "day78b_brief.csv", "data_move", r.data_move, "news", "macro")
        if calendar is not None:
            for r in calendar.itertuples():
                self.add("Markets", "calendar", f"Coming up: {r.event} on {r.date}.", "day78b_calendar.csv", "date",
                         r.date, "news")

    def _economy(self):
        e = self._csv("day76c_economic_dashboard.csv")
        if e is None:
            return
        for r in e.itertuples():
            self.add("Markets", r.indicator, f"{r.indicator}: latest {r.latest:.2f} (previous {r.previous:.2f}, a year "
                     f"ago {r.year_ago:.2f}; period {r.release_period}).", "day76c_economic_dashboard.csv", "latest",
                     r.latest, "macro")

    def _advisory(self):
        p = self._csv("day82_client_profiles.csv")
        g = self._csv("day84_goal_summary.csv")
        if p is None:
            return
        goals = g.set_index("client_id") if g is not None else pd.DataFrame()
        for r in p.itertuples():
            self.alias(r.client_id, r.name)
            prob = goals.at[r.client_id, "probability"] if r.client_id in goals.index else None
            text = (f"{r.name} ({r.client_id}): profile {r.profile_name}, recommended portfolio expected return "
                    f"{r.expected_return:.1%}, volatility {r.volatility:.1%}, suitability {r.suitability}")
            text += f", goal probability {prob:.0%}." if prob is not None else "."
            self.add("Advisory", r.client_id, text, "day82_client_profiles.csv", "suitability", r.suitability,
                     "advisory")

    def _risk(self):
        from vittantra_research_copilot import VittantraResearchCopilot
        copilot = VittantraResearchCopilot()
        if copilot.data.risk.empty and copilot.data.approval.empty:
            return
        self.sources.append("day67–day70 risk governance")
        self.add("Risk", "risk governance", f"Portfolio risk status {copilot.portfolio_status()}; maximum risk-budget "
                 f"utilization {copilot.max_utilization():.1%}; workflow {copilot.workflow_status()} with "
                 f"{copilot.approval_queue()} tickets in the approval queue; automatic execution "
                 f"{copilot.automatic_execution_count()}.", "day67/day70 summaries", "portfolio_status",
                 copilot.portfolio_status(), "risk")
        for row in copilot.highest_risk_contributors(5).itertuples(index=False):
            values = row._asdict()
            symbol = next((str(v) for k, v in values.items() if k in ("symbol", "ticker", "instrument")), None)
            share = next((v for k, v in values.items() if "contribution" in k), None)
            if symbol is not None and share is not None:
                self.add("Risk", symbol, f"{symbol} contributes {float(share):.1%} of modeled portfolio risk.",
                         "day68 governance", "modeled_risk_contribution", share, "risk")

    # ---- retrieval -------------------------------------------------------
    def entities_in(self, question: str) -> List[str]:
        q = " " + re.sub(r"[^a-z0-9\-\.&= ]", " ", question.lower()) + " "
        found = []
        for alias in sorted(self.entities, key=len, reverse=True):
            if len(alias) < 2:
                continue
            if f" {alias} " in q and self.entities[alias] not in found:
                found.append(self.entities[alias])
        return found

    def search(self, question: str, k: int = MAX_EVIDENCE) -> List[Evidence]:
        words = set(_words(question))
        entities = self.entities_in(question)
        topics = {t for t, keys in TOPICS.items() if words & set(keys)}
        # "bear case" / "bull case" ask for one side only
        side = "bear" if words & {"bear", "risks", "weakness", "weaknesses", "concerns", "downside"} else \
            "bull" if words & {"bull", "strengths", "positive"} else None
        portfolio_level = not entities and topics & {"portfolio", "risk"} and "portfolio" in words
        scored = []
        for e in self.records:
            score = 0.0
            if entities:
                if e.entity in entities:
                    score += 5
                elif e.entity not in ("universe", "signals"):
                    continue
            score += len(words & e.keywords) * 0.6
            score += sum(1.0 for t in topics if words & set(TOPICS[t]) and e.keywords & set(TOPICS[t]))
            score += sum(1.5 for t in topics if TOPIC_DESK.get(t) == e.desk)
            if side:
                if e.topic == OPPOSITE[side]:
                    continue                      # a bear-case question gets no bull points, and vice versa
                score += 3 if e.topic == side else 0
            if e.topic == "macro" and "macro_factor" in e.keywords and words & {"rates", "rate", "credit", "dollar",
                                                                              "oil", "inflation", "yields", "spreads"}:
                score += 2 * len(words & set(_words(e.statement)) & {"rates", "rate", "credit", "dollar", "oil",
                                                                     "inflation", "yields", "spreads", "interest"})
            if portfolio_level:
                score += 4 if e.desk in ("Portfolio", "Risk") else -4
            if score >= MIN_SCORE:
                scored.append((score, e))
        scored.sort(key=lambda x: -x[0])
        return [e for _, e in scored[:k]]


# ==============================================================
# COPILOT
# ==============================================================

def numbers_in(text: str) -> set:
    return {n.rstrip(".") for n in re.findall(r"-?\d[\d,]*\.?\d*", text) if any(ch.isdigit() for ch in n)}


def is_grounded(text: str, evidence: List[Evidence]) -> bool:
    """Every number in the text must appear in the evidence (citation indices allowed)."""
    source = " ".join(e.statement + " " + e.value for e in evidence)
    allowed = numbers_in(source) | {str(i) for i in range(1, len(evidence) + 1)}
    normalized = {n.replace(",", "") for n in allowed} | allowed
    return all(n in normalized or n.replace(",", "") in normalized for n in numbers_in(text))


def ollama_rewrite(question: str, draft: str) -> Optional[str]:
    """Optional free local model (Ollama). Returns None when unavailable."""
    if os.getenv("VITTANTRA_LLM", "").lower() != "ollama":
        return None
    try:
        import requests
        prompt = ("You are Vittantra's research copilot. Rewrite the EVIDENCE below as a short, clear answer to the "
                  "QUESTION for a finance professional. Use ONLY facts and numbers from the evidence, keep the [n] "
                  "citations, add no new numbers, and do not recommend trades.\n\n"
                  f"QUESTION: {question}\n\nEVIDENCE:\n{draft}\n\nANSWER:")
        response = requests.post("http://localhost:11434/api/generate", timeout=60, json={
            "model": os.getenv("VITTANTRA_LLM_MODEL", "llama3.2"), "prompt": prompt, "stream": False,
            "options": {"temperature": 0.1}})
        response.raise_for_status()
        return response.json().get("response", "").strip() or None
    except Exception:
        return None


class Copilot:
    def __init__(self, kb: Optional[KnowledgeBase] = None,
                 rewriter: Callable[[str, str], Optional[str]] = ollama_rewrite):
        self.kb = kb or KnowledgeBase()
        self.rewriter = rewriter

    def ask(self, question: str) -> Answer:
        question = question.strip()
        if TRADE_REQUEST.search(question):
            return Answer(question, "Vittantra does not place, submit or execute trades. It produces research and "
                          "proposals that go through the approval workflow to a human decision-maker.",
                          [], True, "refused")
        evidence = self.kb.search(question)
        if not evidence:
            covered = ", ".join(sorted({e.desk for e in self.kb.records})) or "none loaded"
            return Answer(question, "Vittantra's data does not support an answer to that, so I won't guess. "
                          f"Desks with data loaded: {covered}. Try naming a stock, client, asset class or topic.",
                          [], True, "no_data")
        lines = [f"- {e.statement} [{i}]" for i, e in enumerate(evidence, start=1)]
        intro = "Here is what Vittantra's data shows:"
        if ADVICE_REQUEST.search(question):
            intro = ("Vittantra gives research, not personal trade instructions. The research view, for a human to "
                     "decide through the approval workflow:")
        draft = intro + "\n" + "\n".join(lines)
        rewritten = self.rewriter(question, draft) if self.rewriter else None
        if rewritten and is_grounded(rewritten, evidence):
            return Answer(question, rewritten, evidence, True, "llm")
        return Answer(question, draft, evidence, True, "template")

    @staticmethod
    def suggested_questions() -> List[str]:
        return ["What is NVDA worth and why?", "What is the bear case for Apple?",
                "What drove the research portfolio's outperformance?", "What moved rates and credit this month?",
                "What is happening in the world this week?", "Is sample client B's plan suitable?",
                "What are the biggest risks in the portfolio?", "Which stocks are top rated?"]


# ==============================================================
# APP PAGE
# ==============================================================

def render_copilot() -> None:
    import streamlit as st

    @st.cache_resource(ttl=300, show_spinner="Loading Vittantra's evidence…")
    def _copilot():
        return Copilot()

    copilot = _copilot()
    st.markdown("### Vittantra Copilot")
    st.caption(f"Answers only from Vittantra's own data — {len(copilot.kb.records):,} evidence records from "
               f"{len(set(copilot.kb.sources))} sources — with citations. It says so when the data does not cover a "
               "question, and it never executes trades.")
    mode = "local model (Ollama) with number check" if os.getenv("VITTANTRA_LLM", "").lower() == "ollama" \
        else "evidence templates (set VITTANTRA_LLM=ollama for a free local model)"
    st.caption(f"Answer mode: {mode}.")
    history = st.session_state.setdefault("copilot_history", [])
    cols = st.columns(4)
    for i, q in enumerate(Copilot.suggested_questions()):
        if cols[i % 4].button(q, key=f"suggest-{i}", width="stretch"):
            history.append(copilot.ask(q))
    question = st.chat_input("Ask about a stock, the portfolio, markets, a client or risk…")
    if question:
        history.append(copilot.ask(question))
    for answer in history[-6:][::-1]:
        with st.chat_message("user"):
            st.write(answer.question)
        with st.chat_message("assistant"):
            st.markdown(answer.text.replace("$", "\\$"))
            if answer.evidence:
                with st.expander(f"Evidence ({len(answer.evidence)})"):
                    for line in answer.citations():
                        st.caption(line.replace("$", "\\$"))
    if history and st.button("Clear conversation"):
        st.session_state["copilot_history"] = []
        st.rerun()


if __name__ == "__main__":
    bot = Copilot()
    print(f"Knowledge base: {len(bot.kb.records)} records from {len(set(bot.kb.sources))} sources\n")
    for q in Copilot.suggested_questions() + ["Buy 100 shares of AAPL for me", "What is the weather in Paris?",
                                              "Should I buy NVDA?"]:
        a = bot.ask(q)
        print(f"Q: {q}\n[{a.mode}] {a.text[:600]}\n")
    print("Day 85 copilot complete. Answers are grounded in Vittantra data; nothing is executed.")
