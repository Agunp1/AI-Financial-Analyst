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

| Macro drivers (Day 76d) | Multiple OLS of daily returns on factor moves (t-stats, R², standardized betas); attribution = Σ β × factor move + α + residual; rate beta ≈ −duration check | `macro_drivers.py` | ✅ |
| Equity valuation (Day 78) | CAPM with Blume-adjusted beta; WACC on market-value weights; cost of debt = r_f + rating spread from interest coverage; FCFF = CFO + interest(1−t) − capex; three-stage DCF (5y growth, 5y fade, Gordon terminal with g ≤ r_f); residual income with clean surplus and ROE fading to r_e; two-stage DDM from sustainable growth b×ROE; model chosen by business type; reverse DCF by bisection; WACC × g sensitivity | `vittantra_pricing.py`, `valuation_engine.py` | ✅ |
| Portfolio construction (Day 79) | Grinold–Kahn alpha = IC × σ × z; Ledoit–Wolf (2004) constant-correlation shrinkage covariance; mean–active-variance optimizer with tracking-error budget, position, sector, beta and Euler risk-share limits | `portfolio_construction.py`, `vittantra_risk_model.constant_correlation_shrinkage` | ✅ |
| Performance attribution (Day 80) | Brinson–Fachler allocation/selection/interaction per period, Carino logarithmic linking; cross-sectional factor attribution (exposure × factor return + specific) | `performance_attribution.py` | ✅ |
| What-if risk (Day 81) | Parametric VaR = 2.326σ, ES = 2.665σ (normal, 99%); historical VaR; Euler risk shares; OLS factor betas → scenario P&L = Σβ×shock | `whatif_engine.py` | ✅ |
| Advisory (Days 82–84) | Building-block capital market assumptions (yield − expected loss; 10Y + ERP); shrinkage correlations with volatility blended 50/50 with long-run levels; max-return-at-target-volatility allocation with policy ranges; profile = min(willingness, capacity); 1-in-20 loss = 1.645σ − μ; lognormal Monte Carlo matched to arithmetic mean and variance, flows inflation-indexed, results in real terms | `advisory_engine.py` | ✅ |
| Private markets (Day 91) | VC method (exit × retention ÷ target multiple) and its reverse; priced round with option-pool shuffle; cap table dilution; 1× non-participating/participating waterfall solved by iteration; LTV, CAC payback, burn multiple, Rule of 40; power-law fund simulation (TVPI); LBO with FCF debt paydown, MOIC, IRR and value-creation bridge | `private_markets.py` | ✅ |
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
| 12 | **Macro drivers: prices one day behind rates** | Price dates carrying a time of day sorted after FRED's plain dates, so each price was carried to the next day; bond returns no longer lined up with yield changes | Both date indexes reduced to plain calendar dates; a lead-lag check (TLT vs 10Y change must peak at lag 0) is now part of validation | TLT rate beta ≈ 0 → ≈ −duration |
| 13 | **Macro drivers: rate-beta check in the wrong units** | Returns are decimals, so a duration of 17 shows as a beta of −0.17 per +1pp; the check expected −17, and the real −0.134 (t = −25) was reported as a failure | Check range −0.12 to −0.22, reported as % per +1pp with implied duration | TLT −13.4% per +1pp (implied duration 13.4) passes |
| 14 | **Day 77 ran on coarse 20-day prices and no regime** | Needed hedge_fund.db or a stock price database that a fresh machine does not have; regime needed spread history | Free Yahoo daily prices and FRED spread/yield history downloaded and cached (`day77_price_history.csv`, `day77_macro_history.csv`); SEC facts downloaded once if missing (filing dates keep it point in time) | Technical, risk and economic pillars on daily data |
| 15 | **US market engine scored funds as companies** | Commodity ETF trusts (gold, silver, oil, crypto) and asset-backed trusts file with the SEC like companies (SIC 6221/6189); they topped the fundamental ranking | Excluded by SIC code and fund names, keeping operating companies under those codes (e.g. a uranium royalty company); saved results re-scored without re-downloading | 121 funds removed; 4,215 operating companies scored |
| 16 | **Model portfolio failed on staggered free price data** | Yahoo daily rows can be missing for alternate tickers on alternate dates; the 80%-coverage filter then dropped every stock and the benchmark divided by zero | Calendars aligned first: dates nobody traded are dropped and a close is carried forward over gaps of at most 5 days (past prices only, so no look-ahead); a clear error if fewer than 2 stocks remain | Same tracking error on staggered and clean test data |
| 17 | **Notes overstated upside wording; missing debt valued as zero silently** | "Trades 216% below its value" mixed up price-to-value and value-to-price; a company whose debt is absent from the SEC frames (e.g. a carmaker with a finance arm) was valued as debt-free without a warning | Wording is now "value is X% above/below the price"; missing debt is stated in the note, wide model disagreement is flagged, and when both happen no under/overvalued call is made ("Low confidence") | On-demand notes for any US company use the same rules |
| 18 | **Risk budgets could never be met** | Day 66 rescaled asset-class risk budgets to sum to exactly 100% of risk, including 3% for cash (which has no risk) and large budgets for bonds, FX and REITs that use under 1% of risk. Shares of risk also sum to 100%, so some position was always over budget: the demo book showed CRITICAL whatever it held, and no remediation could clear it | Budgets are now limits: the maximum share of portfolio risk per asset class (cash none); limits of risky classes sum above 100%. Day 69b sizes the fix by re-running the real risk chain and shrinking only positions at or above 80% of their limit; a human approves it in the app (approved_positions.json), then the chain re-runs | Before: AAPL call 350% and ES 140% of limit (CRITICAL). After the sized fix: every position below 80% of its limit (NORMAL); all Day 66–70 checks pass |
| 19 | **Stress tests double-counted the market proxy** | SPY is the equity-market factor, but it was also regressed on rates, credit and the dollar, and those betas (which absorb equity moves when the equity factor is left out) were added on top of the equity shock: a 60/40 lost 36% in the 2022-like rate shock | A factor's own instrument moves one-for-one with its factor and has zero exposure to the others | 60/40: rate shock −16.8% (2022 actual ≈ −17%), 2008-like crisis −19.1% (2008 actual ≈ −20%) |

---

## 3. Known simplifications (stated, not hidden)

These are acceptable for a research system but should be understood:

| Area | Simplification | Better practice / next step |
|------|----------------|------------------------------|
| Futures capital | Margin assumed at 10% of notional | Use exchange initial-margin data |
| Option volatility | Implied volatility assumed at 28% (no free IV source) | Implied vol from option chains |
| Bond schedule | Regular coupon schedule; no accrued interest (clean price) | Actual day-count and accrued interest |
| Risk model (Days 59–66) | Sample covariance of ~320 daily returns, equal weighting (Days 79–81 use Ledoit–Wolf shrinkage) | Shrinkage in the risk chain too; EWMA; factor risk model |
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
| Macro drivers | Linear, constant betas over one year; factors correlated (betas shift when factors move together — e.g. TLT's implied duration 13.4 vs ~16 actual, because inflation expectations and the equity factor share part of the rate move; HYG's credit beta is small because the equity factor absorbs most credit risk); summed simple returns approximate compounding | Rolling/regime-dependent betas, orthogonalized factors |
| CRE | Listed REITs/brand owners proxy private CRE; no free occupancy/RevPAR or property NOI data | Licensed STR/CoStar data |
| Multi-factor: sample | 33 stocks and ~3 years of monthly rebalances: IC t-statistics are noisy; economic pillar is a simple beta tilt | Larger universe (US engine), longer history, sector-macro sensitivities |
| Valuation inputs | Equity risk premium 4.5% and terminal growth cap 3% are policy assumptions; growth starts from trailing revenue growth (capped 20%; 5% for energy/materials) rather than analyst forecasts; trailing FCFF is not normalized for the cycle; book debt proxies market debt; leases excluded | Consensus or own forecasts, normalized (mid-cycle) cash flows, market value of debt |
| Valuation: REITs | Valued with DCF/DDM on reported cash flow; FFO/AFFO not computed | FFO = net income + real-estate depreciation − gains on sales |
| Portfolio construction | Alpha scaled from one IC for all stocks; benchmark is the equal-weighted 33-stock universe; book costs 10 bp | Stock-specific IC/volatility forecasts, a cap-weighted benchmark, market-impact costs |
| Attribution | Backtested top-quintile portfolio, not the optimizer's portfolio; arithmetic Brinson with Carino linking | Attribute live portfolios once a track record exists |
| What-if scenarios | Linear factor betas; normal parametric VaR; built-in scenarios are hypothetical sizes of past episodes | Full revaluation (bonds/options), stressed correlations, historical scenario replay |
| Advisory assumptions | Premiums (ERP 4.5%, international +0.5%, EM +1.5%, REIT +3%) and default losses are policy assumptions; correlations from one year; annual returns independent (no mean reversion or fat tails); taxes and fees not modelled beyond the IPS cost rate | Committee-approved CMAs, longer histories, fat-tailed or regime simulations, tax-aware planning |
| Private markets | Deals are fictional practice cases; screening thresholds and the power-law outcome mix are illustrative; LBO uses a single debt tranche, FCF as a fixed share of EBITDA and no working-capital detail | Real deal data (paid), multi-tranche debt schedules, fund-specific return data |
| Multi-asset: alternatives | Listed proxies stand in for private equity, private credit and hedge funds | Fund-level data |
