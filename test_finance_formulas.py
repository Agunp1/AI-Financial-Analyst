"""
Reference tests for Vittantra's core finance formulas.

Each test checks a formula against a textbook identity or an independent
calculation, so a silent formula change is caught immediately.
"""

import math
import unittest

import numpy as np
import pandas as pd

import ml_portfolio_backtest as backtest
from cross_asset_stress import StressScenario, full_revaluation_effects
from ml_factor_attribution import calculate_ols
from multi_asset_risk import AssetClass, Instrument
from vittantra_pricing import (
    black_scholes_delta,
    black_scholes_price,
    bond_analytics,
    bond_price,
)
from vittantra_risk_model import euler_risk_contributions


def scenario(**overrides):
    base = dict(
        name="test", description="", equity_shock=0.0, etf_fund_shock=0.0,
        fixed_income_shock=0.0, option_shock=0.0, future_shock=0.0, fx_shock=0.0,
        commodity_shock=0.0, cash_shock=0.0, crypto_shock=0.0, real_estate_shock=0.0,
        other_shock=0.0, volatility_multiplier=1.0, interest_rate_shock_bps=0.0,
        credit_spread_shock_bps=0.0,
    )
    base.update(overrides)
    fields = StressScenario.__dataclass_fields__
    return StressScenario(**{k: v for k, v in base.items() if k in fields})


class OptionPricingTests(unittest.TestCase):

    def test_black_scholes_textbook_value(self):
        # Hull: S=K=100, T=1, r=5%, σ=20% → call 10.4506, put 5.5735
        self.assertAlmostEqual(black_scholes_price(100, 100, 1, 0.05, 0.2, "call"), 10.4506, places=4)
        self.assertAlmostEqual(black_scholes_price(100, 100, 1, 0.05, 0.2, "put"), 5.5735, places=4)

    def test_put_call_parity(self):
        s, k, t, r, v = 105.0, 100.0, 0.75, 0.04, 0.3
        call = black_scholes_price(s, k, t, r, v, "call")
        put = black_scholes_price(s, k, t, r, v, "put")
        self.assertAlmostEqual(call - put, s - k * math.exp(-r * t), places=10)

    def test_delta_matches_finite_difference(self):
        s, k, t, r, v, h = 100.0, 105.0, 0.5, 0.03, 0.25, 1e-4
        numeric = (black_scholes_price(s + h, k, t, r, v) - black_scholes_price(s - h, k, t, r, v)) / (2 * h)
        self.assertAlmostEqual(black_scholes_delta(s, k, t, r, v), numeric, places=6)


class BondTests(unittest.TestCase):

    def test_par_bond(self):
        self.assertAlmostEqual(bond_price(0.06, 0.06, 10), 100.0, places=8)

    def test_zero_coupon_duration_equals_maturity(self):
        a = bond_analytics(0.0, 0.05, 5)
        self.assertAlmostEqual(a["macaulay_duration"], 5.0, places=10)
        self.assertAlmostEqual(a["modified_duration"], 5.0 / 1.025, places=10)

    def test_duration_convexity_approximates_price_change(self):
        a = bond_analytics(0.045, 0.052, 4.7)
        dy = 0.01
        exact = bond_price(0.045, 0.052 + dy, 4.7) / a["price"] - 1
        approx = -a["modified_duration"] * dy + 0.5 * a["convexity"] * dy ** 2
        self.assertAlmostEqual(exact, approx, places=4)


class StressTests(unittest.TestCase):

    def setUp(self):
        self.bond = Instrument(
            instrument_id="B", symbol="B", name="Bond", asset_class=AssetClass.FIXED_INCOME,
            quantity=100, price=98.5, maturity_date="2031-06-15", coupon_rate=0.045,
            yield_to_maturity=0.052,
        )
        self.call = Instrument(
            instrument_id="C", symbol="C", name="Call", asset_class=AssetClass.OPTION,
            quantity=5, price=8.5, underlying="AAPL", option_type="Call", strike=210.0,
            expiration_date="2027-01-15", contract_multiplier=100,
            metadata={"underlying_price": 205.0, "implied_volatility": 0.28, "risk_free_rate": 0.04},
        )

    def test_bond_loses_value_when_rates_rise(self):
        effects = full_revaluation_effects(self.bond, scenario(interest_rate_shock_bps=200))
        self.assertLess(effects["rate_effect"], -0.07)
        self.assertGreater(effects["rate_effect"], -0.10)

    def test_option_crash_is_leveraged(self):
        effects = full_revaluation_effects(self.call, scenario(equity_shock=-0.30))
        self.assertLess(effects["direct_shock"], -0.90)

    def test_no_shock_no_change(self):
        for instrument in (self.bond, self.call):
            effects = full_revaluation_effects(instrument, scenario())
            total = sum(effects[k] for k in ("direct_shock", "rate_effect", "credit_effect", "volatility_effect"))
            self.assertAlmostEqual(total, 0.0, places=12)


class RiskContributionTests(unittest.TestCase):

    def setUp(self):
        self.cov = pd.DataFrame(
            [[0.04, 0.006, 0.0], [0.006, 0.09, -0.01], [0.0, -0.01, 0.01]],
            index=list("ABC"), columns=list("ABC"),
        )
        self.x = pd.Series({"A": 100.0, "B": 50.0, "C": 80.0})

    def test_contributions_sum_to_portfolio_volatility(self):
        shares, vol = euler_risk_contributions(self.x, self.cov)
        x = self.x.to_numpy()
        self.assertAlmostEqual(vol, math.sqrt(x @ self.cov.to_numpy() @ x), places=10)
        self.assertAlmostEqual(shares.sum(), 1.0, places=12)

    def test_contribution_equals_exposure_times_marginal_risk(self):
        shares, vol = euler_risk_contributions(self.x, self.cov)
        h = 1e-6
        for name in self.x.index:
            bumped = self.x.copy()
            bumped[name] += h
            _, vol_up = euler_risk_contributions(bumped, self.cov)
            marginal = (vol_up - vol) / h
            self.assertAlmostEqual(shares[name] * vol, self.x[name] * marginal, places=4)


class PerformanceMetricTests(unittest.TestCase):

    def setUp(self):
        self.returns = pd.Series([0.02, -0.01, 0.03, -0.02, 0.01, 0.015])
        self.rf = pd.Series(0.003, index=self.returns.index)

    def test_sharpe_uses_excess_returns(self):
        excess = self.returns - self.rf
        expected = excess.mean() / excess.std(ddof=1) * math.sqrt(backtest.PERIODS_PER_YEAR)
        self.assertAlmostEqual(backtest.sharpe_ratio(self.returns, self.rf), expected, places=12)

    def test_sortino_downside_deviation_over_all_periods(self):
        excess = self.returns - self.rf
        downside = math.sqrt((np.minimum(excess, 0) ** 2).mean())
        expected = excess.mean() / downside * math.sqrt(backtest.PERIODS_PER_YEAR)
        self.assertAlmostEqual(backtest.sortino_ratio(self.returns, self.rf), expected, places=12)

    def test_annualized_return_is_geometric(self):
        r = pd.Series([0.01] * int(round(backtest.PERIODS_PER_YEAR * 2)))
        years = len(r) / backtest.PERIODS_PER_YEAR
        self.assertAlmostEqual(backtest.annualized_return(r), 1.01 ** (len(r) / years) - 1, places=12)

    def test_turnover_is_one_way(self):
        # Full switch from A to B: one-way turnover 100%, traded 200%.
        self.assertAlmostEqual(backtest.calculate_turnover({"A": 1.0}, {"B": 1.0}), 1.0)


class RegressionTests(unittest.TestCase):

    def test_ols_t_statistics_match_closed_form(self):
        rng = np.random.default_rng(3)
        x = pd.DataFrame({"f1": rng.normal(size=60), "f2": rng.normal(size=60)})
        y = pd.Series(0.01 + 0.5 * x["f1"] - 0.2 * x["f2"] + rng.normal(scale=0.3, size=60))
        result = calculate_ols(y, x)
        design = np.column_stack([np.ones(60), x.to_numpy()])
        beta = np.linalg.solve(design.T @ design, design.T @ y.to_numpy())
        resid = y.to_numpy() - design @ beta
        s2 = resid @ resid / (60 - 3)
        se = np.sqrt(np.diag(s2 * np.linalg.inv(design.T @ design)))
        self.assertAlmostEqual(result["intercept_t_statistic"], beta[0] / se[0], places=8)
        self.assertAlmostEqual(result["f1_t_statistic"], beta[1] / se[1], places=8)


if __name__ == "__main__":
    unittest.main()
