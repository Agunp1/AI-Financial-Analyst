"""
Day 78 — Evidence-Linked Stock Research Reports

Builds an equity research note for every rated stock from Vittantra's own
outputs. Every claim carries its evidence: the source file, the field and the
value. If a data point is missing, no claim is made about it — the report
says what is unknown instead of guessing.

Report structure (the standard sell-side / buy-side note):
    1. Rating and thesis      Day 77 multi-factor rating, IC-weighted score
    2. Valuation              Day 78 primary model, cross-checks, reverse DCF
    3. Bull case              evidence that supports the stock
    4. Bear case              evidence against it
    5. Key risks and limits   data gaps, model limitations, what would change the view

Inputs : day77_current_ratings.csv, day77_ic_summary.csv,
         day76_fundamental_metrics.csv, day76_fundamental_scores.csv,
         day78_valuation.csv
Outputs: day78_research_claims.csv     one row per claim with evidence
         day78_report_summary.csv      one row per stock
         day78_report_validation_summary.csv

Research notes, not recommendations. No trades are submitted or executed.
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional

import numpy as np
import pandas as pd


BASE_DIR = Path(__file__).resolve().parent

RATINGS = "day77_current_ratings.csv"
IC_SUMMARY = "day77_ic_summary.csv"
METRICS = "day76_fundamental_metrics.csv"
SCORES = "day76_fundamental_scores.csv"
VALUATION = "day78_valuation.csv"

OUTPUT_CLAIMS = "day78_research_claims.csv"
OUTPUT_SUMMARY = "day78_report_summary.csv"
OUTPUT_VALIDATION = "day78_report_validation_summary.csv"

SECTIONS = ["Thesis", "Valuation", "Bull case", "Bear case", "Risks and limits"]
FORBIDDEN_WORDS = ("guaranteed", "risk-free return", "will rise", "will fall", "cannot lose", "sure thing")

PILLAR_TEXT = {
    "fundamental": "fundamentals (value, growth, quality, balance sheet)",
    "technical": "price trend and momentum",
    "quant": "the machine-learning return forecast",
    "economic": "fit with the current macro regime",
    "risk": "low volatility",
}

PILLAR_BULL = {
    "fundamental": "Strong fundamentals versus peers: score {:.0f}/100.",
    "technical": "Positive price trend and momentum: score {:.0f}/100.",
    "quant": "The machine-learning model ranks it near the top for the next 20 days: score {:.0f}/100.",
    "economic": "Well suited to the current macro regime: score {:.0f}/100.",
    "risk": "Steadier than most peers (low volatility): score {:.0f}/100.",
}
PILLAR_BEAR = {
    "fundamental": "Weak fundamentals versus peers: score {:.0f}/100.",
    "technical": "Poor price trend and momentum: score {:.0f}/100.",
    "quant": "The machine-learning model ranks it near the bottom for the next 20 days: score {:.0f}/100.",
    "economic": "Poorly suited to the current macro regime: score {:.0f}/100.",
    "risk": "More volatile than most peers: risk score {:.0f}/100.",
}


def _value(frame: Optional[pd.DataFrame], ticker: str, field: str) -> Optional[float]:
    if frame is None or ticker not in frame.index or field not in frame.columns:
        return None
    value = frame.at[ticker, field]
    if isinstance(value, str):
        return value
    try:
        value = float(value)
    except (TypeError, ValueError):
        return None
    return value if np.isfinite(value) else None


def _load(base: Path, name: str, index: str = "ticker") -> Optional[pd.DataFrame]:
    path = base / name
    if not path.exists():
        return None
    df = pd.read_csv(path)
    return df.drop_duplicates(index).set_index(index) if index in df.columns else df


class Report:
    """Collects claims; a claim is only added when its evidence value exists."""

    def __init__(self, ticker: str):
        self.ticker = ticker
        self.claims: List[dict] = []

    def add(self, section: str, claim: str, source: str, field: str, value) -> None:
        if value is None or (isinstance(value, float) and not np.isfinite(value)):
            return
        shown = value if isinstance(value, str) else round(float(value), 4)
        self.claims.append({"ticker": self.ticker, "section": section, "claim": claim,
                            "source_file": source, "field": field, "value": shown})


def build_report(ticker: str, data: Dict[str, Optional[pd.DataFrame]]) -> Report:
    ratings, metrics, scores = data["ratings"], data["metrics"], data["scores"]
    valuation, ic = data["valuation"], data["ic"]
    r = Report(ticker)
    v = lambda frame, field: _value(frame, ticker, field)  # noqa: E731

    # 1. Thesis -----------------------------------------------------------
    rating, score = v(ratings, "rating"), v(ratings, "composite_ic_weighted")
    if rating is not None:
        r.add("Thesis", f"Multi-factor rating: {rating}"
              + (f" (IC-weighted score {score:.0f}/100)." if score is not None else "."),
              RATINGS, "rating", rating)
    strongest, weakest = v(ratings, "strongest_pillar"), v(ratings, "weakest_pillar")
    if strongest is not None:
        r.add("Thesis", f"Strongest pillar: {PILLAR_TEXT.get(strongest, strongest)} "
              f"(score {v(ratings, strongest) or 0:.0f}).", RATINGS, strongest, v(ratings, strongest))
    if weakest is not None:
        r.add("Thesis", f"Weakest pillar: {PILLAR_TEXT.get(weakest, weakest)} "
              f"(score {v(ratings, weakest) or 0:.0f}).", RATINGS, weakest, v(ratings, weakest))
    if ic is not None and "mean_ic" in ic.columns:
        predictive = [(p, ic.at[p, "mean_ic"], ic.at[p, "ic_t_stat"]) for p in PILLAR_TEXT
                      if p in ic.index and pd.notna(ic.at[p, "mean_ic"]) and ic.at[p, "ic_t_stat"] >= 2]
        if predictive:
            text = ", ".join(f"{p} (IC {m:.2f}, t {t:.1f})" for p, m, t in predictive)
            r.add("Thesis", f"The rating weights pillars by past predictive power; statistically meaningful so far: "
                  f"{text}.", IC_SUMMARY, "mean_ic", float(predictive[0][1]))

    # 2. Valuation ----------------------------------------------------------
    price, fair = v(valuation, "price"), v(valuation, "fair_value")
    model, upside = v(valuation, "primary_model"), v(valuation, "upside")
    if fair is not None and price is not None:
        r.add("Valuation", f"{model} intrinsic value ${fair:,.2f} vs price ${price:,.2f} "
              f"({upside:+.0%}): {v(valuation, 'valuation_signal')}.", VALUATION, "fair_value", fair)
        checks = [(m, v(valuation, f"{m.lower()}_value")) for m in ("DCF", "RI", "DDM") if m != model]
        checks = [(m, x) for m, x in checks if x is not None]
        if checks:
            r.add("Valuation", "Cross-checks: " + ", ".join(f"{m} ${x:,.2f}" for m, x in checks) + ".",
                  VALUATION, "models_used", v(valuation, "models_used"))
    w, re_ = v(valuation, "wacc"), v(valuation, "cost_of_equity")
    if w is not None:
        r.add("Valuation", f"Discount rates: WACC {w:.1%}, cost of equity {re_:.1%} "
              f"(adjusted beta {v(valuation, 'beta_adjusted'):.2f}, synthetic rating "
              f"{v(valuation, 'synthetic_rating')}).", VALUATION, "wacc", w)
    implied, base_growth = v(valuation, "implied_growth"), v(valuation, "dcf_initial_growth")
    if implied is not None and base_growth is not None:
        r.add("Valuation", f"Reverse DCF: the price implies {implied:.1%} a year growth for five years "
              f"(then fading), vs {base_growth:.1%} assumed from recent revenue growth.",
              VALUATION, "implied_growth", implied)
        if implied > base_growth + 0.05:
            r.add("Bear case", f"High expectations priced in: the market needs {implied:.0%} growth vs "
                  f"{base_growth:.0%} recently.", VALUATION, "implied_growth", implied)
        elif implied < base_growth - 0.05:
            r.add("Bull case", f"Low expectations priced in: the price needs only {implied:.0%} growth vs "
                  f"{base_growth:.0%} recently.", VALUATION, "implied_growth", implied)
    if upside is not None:
        if upside > 0.15:
            r.add("Bull case", f"Trades {upside:.0%} below its {model} value.", VALUATION, "upside", upside)
        elif upside < -0.15:
            r.add("Bear case", f"Trades {-upside:.0%} above its {model} value.", VALUATION, "upside", upside)

    # 3–4. Bull and bear evidence ----------------------------------------
    for pillar in PILLAR_TEXT:
        s = v(ratings, pillar)
        if s is None:
            continue
        if s >= 70:
            r.add("Bull case", PILLAR_BULL[pillar].format(s), RATINGS, pillar, s)
        elif s <= 30:
            r.add("Bear case", PILLAR_BEAR[pillar].format(s), RATINGS, pillar, s)

    rules = [
        ("revenue_growth", lambda x: x > 0.10, "Bull case", "Revenue growing {:.0%} a year (TTM)."),
        ("revenue_growth", lambda x: x < 0, "Bear case", "Revenue shrinking {:.0%} a year (TTM)."),
        ("roe", lambda x: x > 0.20, "Bull case", "High return on equity: {:.0%}."),
        ("roe", lambda x: x < 0.05, "Bear case", "Low return on equity: {:.0%}."),
        ("operating_margin", lambda x: x > 0.25, "Bull case", "Strong operating margin: {:.0%}."),
        ("fcf_yield", lambda x: x > 0.05, "Bull case", "Free-cash-flow yield {:.1%}: cash generation is high "
                                                        "relative to price."),
        ("fcf_yield", lambda x: x < 0.015, "Bear case", "Free-cash-flow yield only {:.1%}."),
        ("debt_to_equity", lambda x: x > 2, "Bear case", "High leverage: debt/equity {:.1f}x."),
        ("interest_coverage", lambda x: x < 3, "Bear case", "Thin interest coverage: {:.1f}x."),
        ("interest_coverage", lambda x: x > 15, "Bull case", "Very comfortable interest coverage: {:.0f}x."),
        ("accruals_ratio", lambda x: x > 0.05, "Bear case", "Earnings run ahead of cash flow (accruals {:.1%} of "
                                                           "assets): an earnings-quality warning."),
        ("pe_ratio", lambda x: x > 40, "Bear case", "Expensive on earnings: P/E {:.0f}x."),
        ("pe_ratio", lambda x: 0 < x < 12, "Bull case", "Cheap on earnings: P/E {:.0f}x."),
    ]
    for field, test, section, template in rules:
        x = v(metrics, field)
        if x is not None and test(x):
            r.add(section, template.format(x), METRICS, field, x)

    vol, beta = v(ratings, "volatility_1y"), v(ratings, "beta")
    if vol is not None and vol > 0.40:
        r.add("Bear case", f"Volatile: {vol:.0%} annualized volatility over the past year.", RATINGS,
              "volatility_1y", vol)

    # 5. Risks and limits ----------------------------------------------------
    notes = v(valuation, "notes")
    if isinstance(notes, str) and notes:
        for note in notes.split(" | "):
            r.add("Risks and limits", note[0].upper() + note[1:] + ".", VALUATION, "notes", note)
    if beta is not None:
        r.add("Risks and limits", f"Market sensitivity: beta {beta:.2f} — a 10% market fall has historically "
              f"meant about {beta * 10:.0f}% for this stock.", RATINGS, "beta", beta)
    filed = v(metrics, "latest_filing_date")
    if isinstance(filed, str):
        r.add("Risks and limits", f"Fundamentals as of the filing dated {filed}; later news is not reflected.",
              METRICS, "latest_filing_date", filed)
    missing = [label for field, label in (("fair_value", "intrinsic value"), ("rating", "multi-factor rating"),
                                          ("roe", "return on equity"), ("revenue_growth", "revenue growth"))
               if v(valuation if field == "fair_value" else ratings if field == "rating" else metrics, field) is None]
    if missing:
        r.add("Risks and limits", "Not available from Vittantra data: " + ", ".join(missing)
              + ". No view is given on these.", "—", "missing", ", ".join(missing))
    regime = v(ratings, "regime")
    if isinstance(regime, str):
        r.add("Risks and limits", f"Macro regime at rating time: {regime.replace('_', '-')}. A regime change shifts "
              "the economic pillar.", RATINGS, "regime", regime)
    return r


def report_markdown(ticker: str, claims: pd.DataFrame, summary: Optional[pd.Series] = None) -> str:
    """Render one stock's note as Markdown with numbered evidence references."""
    rows = claims[claims["ticker"] == ticker]
    title = f"# {ticker}" + (f" — {summary['name']}" if summary is not None and pd.notna(summary.get("name")) else "")
    lines = [title, ""]
    if summary is not None:
        lines.append(f"*{summary.get('sector', '')} · Rating: **{summary.get('rating', 'n/a')}** · "
                     f"As of {summary.get('as_of', '')}*")
        lines.append("")
    refs = []
    for section in SECTIONS:
        part = rows[rows["section"] == section]
        if part.empty:
            continue
        lines.append(f"## {section}")
        for row in part.itertuples():
            refs.append(f"{row.source_file} → {row.field} = {row.value}")
            lines.append(f"- {row.claim} [{len(refs)}]")
        lines.append("")
    lines.append("## Evidence")
    lines += [f"{i}. {ref}" for i, ref in enumerate(refs, start=1)]
    lines += ["", "*Research note generated from Vittantra data. Not a recommendation; intrinsic values are model "
                  "estimates under stated assumptions. Decisions go through the approval workflow to a human.*"]
    return "\n".join(lines)


def validate_reports(claims: pd.DataFrame, summary: pd.DataFrame, rated: int) -> pd.DataFrame:
    checks = []

    def add(name, passed, details):
        checks.append({"check": name, "passed": bool(passed), "details": details})

    add("A report for every rated stock", len(summary) >= rated, f"{len(summary)} of {rated}")
    add("Every claim has evidence", claims[["source_file", "field", "value"]].notna().all().all() if len(claims)
        else False, f"{len(claims)} claims")
    has_both = summary[(summary["bull_points"] > 0) & (summary["bear_points"] > 0)]
    add("Balanced: bull and bear case for most stocks", len(has_both) >= 0.7 * len(summary),
        f"{len(has_both)} of {len(summary)} have both")
    text = " ".join(claims["claim"]).lower() if len(claims) else ""
    bad = [w for w in FORBIDDEN_WORDS if w in text]
    add("No promises or certainty language", not bad, "none found" if not bad else ", ".join(bad))
    add("Risks section in every report", (summary["risk_points"] > 0).all(), "limits and data gaps disclosed")
    df = pd.DataFrame(checks)
    df["passed_tests"] = int(df["passed"].sum())
    df["total_tests"] = len(df)
    df["pass_rate"] = df["passed_tests"] / df["total_tests"]
    return df


def run_reports(base: Path = BASE_DIR, out_dir: Optional[Path] = None, verbose: bool = True):
    out_dir = Path(out_dir or base)
    data = {"ratings": _load(base, RATINGS), "metrics": _load(base, METRICS), "scores": _load(base, SCORES),
            "valuation": _load(base, VALUATION), "ic": _load(base, IC_SUMMARY, index="signal")}
    if data["ratings"] is None:
        raise SystemExit("Run `python multi_factor_rating.py` and `python valuation_engine.py` first.")
    tickers = list(data["ratings"].index)
    claims = pd.DataFrame([c for t in tickers for c in build_report(t, data).claims])
    summary_rows = []
    for t in tickers:
        own = claims[claims["ticker"] == t]
        val = data["valuation"]
        summary_rows.append({
            "ticker": t, "name": _value(data["ratings"], t, "name"), "sector": _value(data["ratings"], t, "sector"),
            "rating": _value(data["ratings"], t, "rating"), "score": _value(data["ratings"], t, "composite_ic_weighted"),
            "price": _value(val, t, "price"), "fair_value": _value(val, t, "fair_value"),
            "upside": _value(val, t, "upside"), "primary_model": _value(val, t, "primary_model"),
            "valuation_signal": _value(val, t, "valuation_signal"), "implied_growth": _value(val, t, "implied_growth"),
            "bull_points": int((own["section"] == "Bull case").sum()),
            "bear_points": int((own["section"] == "Bear case").sum()),
            "risk_points": int((own["section"] == "Risks and limits").sum()),
            "claims": len(own), "as_of": _value(data["ratings"], t, "as_of"),
        })
    summary = pd.DataFrame(summary_rows)
    validation = validate_reports(claims, summary, len(tickers))
    claims.to_csv(out_dir / OUTPUT_CLAIMS, index=False)
    summary.to_csv(out_dir / OUTPUT_SUMMARY, index=False)
    validation.to_csv(out_dir / OUTPUT_VALIDATION, index=False)
    if verbose:
        line = "=" * 92
        print(line)
        print("VITTANTRA — DAY 78 RESEARCH REPORTS (evidence-linked)")
        print(line)
        print(summary[["ticker", "rating", "valuation_signal", "upside", "bull_points", "bear_points", "claims"]]
              .to_string(index=False, float_format=lambda x: f"{x:+.0%}"))
        example = summary.iloc[0]["ticker"]
        print(f"\nExample note: {example}\n")
        print(report_markdown(example, claims, summary.set_index("ticker").loc[example]))
        print("\nValidation")
        print(validation[["check", "passed", "details"]].to_string(index=False))
        print(f"\nPassed: {int(validation['passed'].sum())}/{len(validation)}")
        print("\nDay 78 research reports complete. Research notes, not recommendations.")
        print(line)
    return claims, summary, validation


if __name__ == "__main__":
    run_reports()
