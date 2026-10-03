# Emergent Ventures application — working draft (Day 89)

*A starting point only. Emergent Ventures values a genuine personal voice:
rewrite every paragraph in your own words, keep it short, and do not
overstate. Items in [brackets] are for you to fill in. Check the current
questions on the Mercatus Center website before submitting.*

---

## What do you want to do?

I want to make professional-grade investment research transparent and free to
learn from. Most people — including finance graduates in [your country/city]
— never see how an analyst, portfolio manager, risk manager or advisor
actually works, because the data and tools cost thousands of dollars a year.

Over [90] days I built **Vittantra**, an open research platform that runs
entirely on free public data (SEC EDGAR filings, the Federal Reserve's FRED,
market prices and official news feeds). It:

- rates US stocks on five factors and tests which ones actually predict
  returns;
- values companies with discounted cash flow, residual income and dividend
  models;
- builds a risk-budgeted portfolio and explains its performance;
- checks recommendations for suitability.

Every number is traceable to its source, an AI copilot answers only from that
evidence, and nothing trades without human approval. A built-in "Academy"
lets a learner do each role's daily work on live data, mapped to the CFA
Level II curriculum.

**Next:** [e.g. open it to students at N universities / cover markets in your
country with local free data / turn the Academy into a free course / test
whether learners who use it do better in finance interviews].

## Why you?

[Your story in 3–4 sentences: your finance background, why you started
learning Python, SQL and machine learning, what you cannot afford and how
that shaped the free-data constraint, and what you want to become.]

I built Vittantra while learning to code, using an AI coding assistant as a
pair programmer; the design, the finance decisions and the checking of every
result were mine. [Optional: one concrete thing you are proud of, e.g.
discovering that combining signals equally made predictions worse, and fixing
it without look-ahead bias.]

## What would you do with the grant?

[Be specific and modest, e.g. CFA Level II exam fee $[ ]; a laptop able to run
local AI models $[ ]; a year of hosting for a public version $[ ]; time to
build a version for [local market] users.]

## What has been done so far (verifiable)

- Code and documentation: [GitHub link]; live demo: [Streamlit link].
- 250+ automated tests pin finance formulas to textbook values and enforce the
  rules: no automatic trading, no invented data, suitability checks.
- `FINANCE_AUDIT.md` lists every method, the errors found and corrected, and
  the known simplifications.

*Important: describe backtests as historical research results, not returns
anyone earned, and say clearly that the sample clients are fictional.*
