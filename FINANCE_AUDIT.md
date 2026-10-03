# Vittantra Finance Framework Audit

This document records the review of every core finance calculation in
Vittantra: what each method is, where it lives in the code, whether it
follows the standard framework, what was corrected, and which
simplifications remain. Use it as a study guide. Each row is something to
learn and be able to explain in an interview.

Reference tests: `test_finance_formulas.py` checks the formulas against
textbook values and independent calculations.

---

## 1. Correct as built

| Area | Method | Code | Standard |
|------|--------|------|----------|
| Returns | Simple returns `P_t / P_{t-1} − 1` | `unified_risk_engine.price_to_returns` | ✅ |
| Volatility | Sample std (ddof=1) × √252 | `unified_risk_engine.annualized_volatility` | ✅ |
| Drawdown | `P / running max − 1`, minimum | `unified_risk_engine.maximum_drawdown` | ✅ |
| Beta | `Cov(r_a, r_m) / Var(r_m)` | `unified_risk_engine.calculate_beta` | ✅ |
| Historical VaR | Revalue today's holdings under each past daily return; VaR = loss quantile | `var_engine.calculate_historical_var` | ✅ |
| Expected Shortfall | Mean loss beyond VaR | `var_engine.calculate_historical_var` | ✅ |
| VaR backtest | Rolling window, each estimate uses only prior data | `var_backtesting.backtest_historical_var` | ✅ |
| Kupiec POF test | LR = 2[ln L(p̂) − ln L(p)], χ²(1) | `var_validation.kupiec_pof_test` | ✅ |
| Christoffersen test | Markov transition LR for exception clustering, χ²(1) | `var_validation.christoffersen_independence_test` | ✅ |
| Conditional coverage | LR_uc + LR_ind, χ²(2) | `var_validation.conditional_coverage_test` | ✅ |
| Bond analytics | Macaulay & modified duration, convexity, DV01 = MV × D_mod × 0.0001 | `unified_risk_engine.calculate_bond_analytics`, `vittantra_pricing.bond_analytics` | ✅ |
| Option Greeks | Black-Scholes Δ, Γ, vega (per 1 vol pt), θ (per day), ρ (per 1%) | `unified_risk_engine.black_scholes_greeks` | ✅ |
| Futures | Exposure = quantity × price × multiplier; capital separated from notional | `exposure_risk_engine` | ✅ |
| ML validation | Walk-forward training with a 20-day purge, so 20-day labels never overlap the ranking date (no look-ahead) | `ml_cross_sectional_ranking.build_training_set` | ✅ |
| Backtest annualization | 20-day non-overlapping periods → 252/20 = 12.6 periods a year; geometric annual return | `ml_portfolio_backtest` | ✅ |
| Factor regression | OLS with intercept (alpha), R², adjusted R² | `ml_factor_attribution.calculate_ols` | ✅ |
| Pre-trade limits | Max order value, max order weight, max position weight, min cash | `risk_engine.evaluate_order` | ✅ |

| Fundamentals (Day 76) | Point-in-time (filed ≤ as-of), restatement-aware, TTM = FY + YTD − prior YTD; valuation as yields; ROE/ROA on average capital; percentile scoring; financials excluded from industrial ratios | `fundamental_engine.py` | ✅ |

| Multi-asset analytics (Day 76c) | Total-return prices (adjusted close); volatility annualized with each instrument's observed trading days per year; 12-1 momentum; beta/correlation on overlapping dates; curve slopes 2s10s and 3m10y; spreads in bp with historical percentile; FX carry = base short rate − quote short rate (covered interest parity) | `multi_asset_universe.py` | ✅ |

| Multi-factor rating (Day 77) | Cross-sectional percentile pillars; IC = Spearman rank correlation with next-period return, t-stat across dates; IC-weighted composite using only completed outcomes; cost-adjusted quintile portfolios | `multi_factor_rating.py` | ✅ |

---

## 2. Corrected in this audit

| # | Issue | Why it was wrong | Fix | Effect |
|---|-------|------------------|-----|--------|
| 1 | **Bond stress ignored rates and credit spreads** | Duration was never passed to the stress engine, so the rate and spread sensitivity silently became zero. "Rates +200bp" showed a 0% bond loss | Bonds are fully repriced at the shocked yield: `P(y+Δr+Δs)/P(y) − 1` | Rates +200bp: 0% → **−9.5%** |
| 2 | **Option stress used a flat guess** | An option is leveraged and non-linear; a −30% stock move is not a −35% option move | Full Black-Scholes revaluation at shocked spot, volatility and rate | Equity crash: −35% → **−83%** |
| 3 | **Risk = notional × fixed multiplier** | Ignored actual volatility and correlations; risk contributions don't scale linearly with position size | **Euler risk contributions** `RC_i = x_i(Σx)_i / σ_p` from the return covariance matrix | ES risk share 89%; options and BTC now correctly flagged |
| 4 | **Option exposure = premium paid** | A $4,250 call controls about $51,000 of AAPL | Delta-adjusted exposure `Δ × S × qty × multiplier` | AAPL call becomes 20% of portfolio risk |
| 5 | **Day 65 scaled risk linearly** | Shrinking one position changes every position's risk share | Iterative risk-contribution cap, recomputed each pass | ES capped at 34.9% (limit 35%) |
| 6 | **Transaction costs charged on half the trades** | Cost was applied to one-way turnover `½Σ|Δw|`; every dollar bought *and* sold pays | Cost on traded weight `Σ|Δw|` (Day 56) and both books (Day 57) | L/S return 10.3% → **9.3%**; break-even cost ~70 bps |
| 7 | **Sharpe ignored the risk-free rate** | Sharpe = (R − Rf)/σ. With T-bills at ~4–5%, long-only Sharpe was overstated | Excess returns over the point-in-time 3-month T-bill (FRED DGS3MO) | Top quintile Sharpe 1.69 → **1.31** |
| 8 | **Sortino used the wrong downside measure** | Used std of losing periods only. The standard downside deviation is `√mean(min(R−MAR,0)²)` over all periods | Standard downside deviation | Sortino values corrected |
| 9 | **Alpha reported without significance** | A coefficient means little without its standard error | OLS standard errors, t-statistics and p-values for alpha and every factor | Alpha 2.4%/yr, t = 0.40, p = 0.70 → **not significant** |
| 10 | **Day 63 crashed on the sample portfolio** | Refused to run when a position already exceeded its cap | Moves toward targets within the turnover limit and flags the remaining breach | Pipeline runs end to end |
| 11 | **Risk chain ran only on made-up data** | Day 60 used synthetic price history and fixed example prices | Day 75 data hub feeds real prices, rates, spreads and history | LIVE mode available |

---

## 3. Known simplifications (stated, not hidden)

These are acceptable for a research system but should be understood:

| Area | Simplification | Better practice / next step |
|------|----------------|------------------------------|
| Futures capital | Margin assumed at 10% of notional | Use exchange initial-margin data |
| Option volatility | Implied volatility assumed at 28% (no free IV source) | Implied vol from option chains |
| Bond schedule | Regular coupon schedule; no accrued interest (clean price) | Actual day-count and accrued interest |
| Risk model | Sample covariance of ~320 daily returns, equal weighting | EWMA or shrinkage covariance; factor risk model |
| Risk budgets | Strategic asset-class budgets are policy choices | Set from an investment policy statement (Day 82) |
| Day 63 targets | Stress-based heuristic targets | Optimizer with explicit objective |
| Day 56 vs Day 57 | Day 56 long/short is 50%/50% (100% gross); Day 57 is 100%/100% (200% gross), so return levels differ | Report both at the same gross exposure |
| Equal-weight benchmark | Rebalancing back to equal weight after drift is not charged | Track drift and charge rebalancing costs |
| VaR backtest | Fixed illustrative portfolio value | Use the actual portfolio value path |
| Factor regression | 39 observations for 10 factors; classical (not HAC) standard errors | Longer sample; Newey-West standard errors; fewer factors |
| Notebooks (Days 1–30) | Some use Sharpe with Rf = 0 and arithmetic annualization (labeled) | Kept as the original learning record |
| Sample mode | Illustrative prices and synthetic history | Run `python run_vittantra.py` for live data |
| Fundamentals: valuation | Market cap uses the listed class price × all share classes (e.g. GOOGL) | Per-class prices |
| Fundamentals: debt | Debt = long-term + short-term borrowings; operating leases excluded | Include lease liabilities |
| Fundamentals: REITs | P/E used; REITs are normally valued on FFO/AFFO | Add FFO from filings |
| Fundamentals: EPS TTM | Diluted EPS TTM built with FY + YTD − prior YTD (approximation; EPS is not strictly additive) | Net income ÷ diluted shares per quarter |
| Fundamentals: scoring | 33-stock universe uses universe percentiles (3 per sector is too few) | Done for the US market engine: sector-relative percentiles |
| US market engine | SEC frames carry the latest value per period (restatements included) and no filing date | Use the point-in-time Day 76 engine for backtests |
| US market engine | SIC codes mapped to GICS-style sectors approximately | Licensed GICS classification |
| US market engine | Shares from diluted weighted-average count when cover-page shares are unavailable | Period-end shares outstanding |
| Multi-asset: credit | No free prices for individual corporate bonds; spread indices and bond ETFs used. FRED's ICE BofA history is limited (about 3 years), so spread percentiles cover a short window | Licensed bond pricing (TRACE/ICE) |
| Multi-asset: FX carry | OECD 3-month interbank rates are monthly and some countries lag or are discontinued | Daily deposit/forward rates |
| Multi-asset: commodities | Front-month futures only; no roll yield / term structure | Second-month contracts |
| Multi-factor: sample | 33 stocks and ~3 years of monthly rebalances: IC t-statistics are noisy; economic pillar is a simple beta tilt | Larger universe (US engine), longer history, sector-macro sensitivities |
| Multi-asset: alternatives | Listed proxies stand in for private equity, private credit and hedge funds | Fund-level data |
