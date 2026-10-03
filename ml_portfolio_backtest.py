"""
Vittantra
Day 56 — Portfolio Construction & Economic Validation

Purpose
-------
Convert Day 55 out-of-sample cross-sectional rankings into
portfolio-level research results.

Input
-----
day55_cross_sectional_rankings.csv

Strategies
----------
1. Equal-Weight Universe
2. Top Quintile Long
3. Bottom Quintile Long
4. Dollar-Neutral Long/Short
   +50% Top Quintile
   -50% Bottom Quintile

Important methodology
---------------------
- Day 55 predictions are already out-of-sample.
- Day 56 does NOT retrain the ML model.
- Forward returns are 20-trading-day returns.
- Ranking dates are approximately 20 trading days apart.
- Annualization uses 252 / 20 periods per year.
- Transaction costs are deducted from portfolio turnover.
- Historical research only.
- No live trading or investment recommendations.
"""

from pathlib import Path
import math
import sys

import numpy as np
import pandas as pd

from vittantra_live_inputs import risk_free_rates


# ============================================================
# CONFIGURATION
# ============================================================

BASE_DIR = Path(__file__).resolve().parent

INPUT_FILE = BASE_DIR / "day55_cross_sectional_rankings.csv"

OUTPUT_PERIODS = BASE_DIR / "day56_portfolio_periods.csv"
OUTPUT_SUMMARY = BASE_DIR / "day56_portfolio_summary.csv"
OUTPUT_YEARLY = BASE_DIR / "day56_yearly_summary.csv"
OUTPUT_TURNOVER = BASE_DIR / "day56_turnover_summary.csv"

FORWARD_DAYS = 20
PERIODS_PER_YEAR = 252 / FORWARD_DAYS

TRANSACTION_COST_BPS = 10.0
TRANSACTION_COST_RATE = TRANSACTION_COST_BPS / 10_000

TOP_QUINTILE = 5
BOTTOM_QUINTILE = 1


# ============================================================
# DISPLAY HELPERS
# ============================================================

def header(title):
    print()
    print(title)
    print("=" * 100)


def subheader(title):
    print()
    print(title)
    print("-" * 100)


def fmt_pct(value):
    if pd.isna(value):
        return "N/A"

    return f"{value:.2%}"


def fmt_num(value, digits=4):
    if pd.isna(value):
        return "N/A"

    return f"{value:.{digits}f}"


# ============================================================
# LOAD DAY 55
# ============================================================

def load_rankings():

    if not INPUT_FILE.exists():
        raise FileNotFoundError(
            f"{INPUT_FILE.name} not found. "
            "Run Day 55 first."
        )

    df = pd.read_csv(INPUT_FILE)

    if df.empty:
        raise ValueError(
            "Day 55 ranking file is empty."
        )

    required = [
        "date",
        "ticker",
        "up_probability",
        "forward_return_20d",
    ]

    missing = [
        column
        for column in required
        if column not in df.columns
    ]

    if missing:
        raise ValueError(
            f"Missing Day 55 columns: {missing}\n"
            f"Available columns: {list(df.columns)}"
        )

    df["date"] = pd.to_datetime(
        df["date"],
        errors="coerce",
    )

    df["ticker"] = (
        df["ticker"]
        .astype(str)
        .str.upper()
        .str.strip()
    )

    df["up_probability"] = pd.to_numeric(
        df["up_probability"],
        errors="coerce",
    )

    df["forward_return_20d"] = pd.to_numeric(
        df["forward_return_20d"],
        errors="coerce",
    )

    df = df.dropna(
        subset=[
            "date",
            "ticker",
            "up_probability",
        ]
    )

    df = df.sort_values(
        ["date", "ticker"]
    ).reset_index(drop=True)

    duplicates = df.duplicated(
        subset=[
            "date",
            "ticker",
        ]
    ).sum()

    if duplicates:
        raise ValueError(
            f"Found {duplicates} duplicate "
            "date/ticker observations."
        )

    return df


# ============================================================
# QUINTILES
# ============================================================

def assign_quintiles(df):
    """
    Assign cross-sectional quintiles while explicitly
    preserving the date column.

    We intentionally avoid groupby.apply here because newer
    pandas versions may exclude grouping columns from apply().
    """

    df = df.copy()

    df["score_quintile"] = np.nan

    for date in df["date"].drop_duplicates():

        mask = (
            df["date"] == date
        )

        scores = (
            df.loc[
                mask,
                "up_probability",
            ]
        )

        if len(scores) < 10:
            continue

        # Unique ranks avoid qcut failures caused by tied scores.
        ranks = scores.rank(
            method="first",
            ascending=True,
        )

        quintiles = pd.qcut(
            ranks,
            q=5,
            labels=[
                1,
                2,
                3,
                4,
                5,
            ],
        )

        df.loc[
            mask,
            "score_quintile",
        ] = (
            quintiles
            .astype(int)
            .to_numpy()
        )

    df = df.dropna(
        subset=[
            "score_quintile",
        ]
    ).copy()

    df["score_quintile"] = (
        df["score_quintile"]
        .astype(int)
    )

    return df


# ============================================================
# WEIGHTS
# ============================================================

def equal_weights(tickers):

    tickers = list(tickers)

    if not tickers:
        return {}

    weight = 1.0 / len(tickers)

    return {
        ticker: weight
        for ticker in tickers
    }


def long_short_weights(
    long_tickers,
    short_tickers,
):

    weights = {}

    long_tickers = list(
        long_tickers
    )

    short_tickers = list(
        short_tickers
    )

    if long_tickers:

        long_weight = (
            0.50
            / len(long_tickers)
        )

        for ticker in long_tickers:
            weights[ticker] = (
                long_weight
            )

    if short_tickers:

        short_weight = (
            -0.50
            / len(short_tickers)
        )

        for ticker in short_tickers:
            weights[ticker] = (
                short_weight
            )

    return weights


# ============================================================
# RETURN / TURNOVER
# ============================================================

def portfolio_return(
    weights,
    realized_returns,
):

    value = 0.0

    for ticker, weight in weights.items():

        realized = realized_returns.get(
            ticker
        )

        if (
            realized is None
            or pd.isna(realized)
        ):
            continue

        value += (
            weight
            * float(realized)
        )

    return float(value)


def calculate_turnover(
    previous_weights,
    current_weights,
):
    """
    One-way portfolio turnover.

    0.5 * sum absolute weight changes.
    """

    securities = (
        set(previous_weights)
        | set(current_weights)
    )

    total_change = sum(
        abs(
            current_weights.get(
                ticker,
                0.0,
            )
            -
            previous_weights.get(
                ticker,
                0.0,
            )
        )
        for ticker in securities
    )

    return (
        0.5
        * total_change
    )


# ============================================================
# BUILD PORTFOLIOS
# ============================================================

def build_portfolios(rankings):

    strategies = [
        "universe",
        "top_quintile",
        "bottom_quintile",
        "long_short",
    ]

    previous_weights = {
        strategy: {}
        for strategy in strategies
    }

    records = []

    ranking_dates = (
        rankings[
            "date"
        ]
        .drop_duplicates()
        .sort_values()
    )

    for date in ranking_dates:

        group = rankings[
            rankings["date"] == date
        ].copy()

        # The last Day 55 ranking dates may not yet have
        # realized 20-day returns.
        group = group.dropna(
            subset=[
                "forward_return_20d",
            ]
        )

        if len(group) < 10:
            continue

        top = group[
            group["score_quintile"]
            == TOP_QUINTILE
        ]

        bottom = group[
            group["score_quintile"]
            == BOTTOM_QUINTILE
        ]

        if (
            top.empty
            or bottom.empty
        ):
            continue

        universe_names = (
            group["ticker"]
            .tolist()
        )

        top_names = (
            top["ticker"]
            .tolist()
        )

        bottom_names = (
            bottom["ticker"]
            .tolist()
        )

        realized_returns = dict(
            zip(
                group["ticker"],
                group[
                    "forward_return_20d"
                ],
            )
        )

        current_weights = {
            "universe":
                equal_weights(
                    universe_names
                ),

            "top_quintile":
                equal_weights(
                    top_names
                ),

            "bottom_quintile":
                equal_weights(
                    bottom_names
                ),

            "long_short":
                long_short_weights(
                    top_names,
                    bottom_names,
                ),
        }

        record = {
            "date":
                date,

            "securities":
                len(group),

            "top_count":
                len(top),

            "bottom_count":
                len(bottom),

            "top_probability":
                top[
                    "up_probability"
                ].mean(),

            "bottom_probability":
                bottom[
                    "up_probability"
                ].mean(),

            "probability_spread":
                (
                    top[
                        "up_probability"
                    ].mean()
                    -
                    bottom[
                        "up_probability"
                    ].mean()
                ),
        }

        for (
            strategy,
            weights,
        ) in current_weights.items():

            gross_return = (
                portfolio_return(
                    weights,
                    realized_returns,
                )
            )

            turnover = (
                calculate_turnover(
                    previous_weights[
                        strategy
                    ],
                    weights,
                )
            )

            # Costs apply to every dollar traded (buys and sells).

            # Traded weight = sum of |weight changes| = 2 x one-way turnover.

            cost = (

                2.0

                * turnover

                * TRANSACTION_COST_RATE

            )

            net_return = (
                gross_return
                - cost
            )

            record[
                f"{strategy}_gross_return"
            ] = gross_return

            record[
                f"{strategy}_turnover"
            ] = turnover

            record[
                f"{strategy}_cost"
            ] = cost

            record[
                f"{strategy}_net_return"
            ] = net_return

            previous_weights[
                strategy
            ] = (
                weights.copy()
            )

        records.append(
            record
        )

    portfolio = pd.DataFrame(
        records
    )

    if portfolio.empty:
        raise ValueError(
            "No valid portfolio periods were created."
        )

    portfolio = (
        portfolio.sort_values(
            "date"
        )
        .reset_index(
            drop=True
        )
    )

    return portfolio


# ============================================================
# PERFORMANCE FUNCTIONS
# ============================================================

def cumulative_return(returns):

    returns = returns.dropna()

    if returns.empty:
        return np.nan

    return float(
        (1 + returns).prod()
        - 1
    )


def annualized_return(returns):

    returns = returns.dropna()

    if returns.empty:
        return np.nan

    wealth = (
        1 + returns
    ).prod()

    if wealth <= 0:
        return np.nan

    years = (
        len(returns)
        / PERIODS_PER_YEAR
    )

    if years <= 0:
        return np.nan

    return float(
        wealth ** (
            1 / years
        )
        - 1
    )


def annualized_volatility(returns):

    returns = returns.dropna()

    if len(returns) < 2:
        return np.nan

    return float(
        returns.std(
            ddof=1
        )
        * math.sqrt(
            PERIODS_PER_YEAR
        )
    )


def excess_returns(returns, risk_free=None):
    returns = returns.dropna()
    if risk_free is None:
        return returns
    return returns - risk_free.reindex(returns.index).fillna(0.0)


def sharpe_ratio(returns, risk_free=None):
    """
    Sharpe = mean(R - Rf) / std(R - Rf) x sqrt(periods per year).

    risk_free: per-period risk-free return aligned to returns, or None
    for self-financing (long-short) portfolios, whose returns are
    already excess returns.
    """
    excess = excess_returns(returns, risk_free)
    if len(excess) < 2:
        return np.nan
    volatility = excess.std(ddof=1)
    if volatility == 0:
        return np.nan
    return float(
        excess.mean()
        / volatility
        * math.sqrt(PERIODS_PER_YEAR)
    )


def sortino_ratio(returns, risk_free=None):
    """
    Sortino = mean(R - Rf) / downside deviation x sqrt(periods per year),
    where downside deviation = sqrt(mean(min(R - Rf, 0)^2)) over ALL
    periods (not the standard deviation of the losing periods only).
    """
    excess = excess_returns(returns, risk_free)
    if len(excess) < 2:
        return np.nan
    downside_deviation = math.sqrt(
        float((excess.clip(upper=0.0) ** 2).mean())
    )
    if downside_deviation == 0:
        return np.nan
    return float(
        excess.mean()
        / downside_deviation
        * math.sqrt(PERIODS_PER_YEAR)
    )


def period_risk_free(dates):
    """Per-period risk-free return from the point-in-time T-bill yield."""
    annual, source = risk_free_rates(dates)
    period = (1.0 + annual.to_numpy()) ** (1.0 / PERIODS_PER_YEAR) - 1.0
    return pd.Series(period, index=dates.index), source


def maximum_drawdown(returns):

    returns = returns.fillna(
        0.0
    )

    wealth = (
        1 + returns
    ).cumprod()

    running_peak = (
        wealth.cummax()
    )

    drawdown = (
        wealth
        / running_peak
        - 1
    )

    return float(
        drawdown.min()
    )


def hit_rate(returns):

    returns = returns.dropna()

    if returns.empty:
        return np.nan

    return float(
        (
            returns > 0
        ).mean()
    )


# ============================================================
# SUMMARY
# ============================================================

def build_summary(portfolio):

    strategies = {
        "Equal Weight Universe":
            "universe",

        "Top Quintile Long":
            "top_quintile",

        "Bottom Quintile Long":
            "bottom_quintile",

        "Long Short":
            "long_short",
    }

    rows = []


    period_rf, _ = period_risk_free(portfolio["date"])

    for (
        strategy_name,
        key,
    ) in strategies.items():

        # Long-short is self-financing, so its return is already an
        # excess return; long-only portfolios subtract the T-bill rate.
        strategy_rf = None if key == "long_short" else period_rf

        gross = portfolio[
            f"{key}_gross_return"
        ]

        net = portfolio[
            f"{key}_net_return"
        ]

        turnover = portfolio[
            f"{key}_turnover"
        ]

        costs = portfolio[
            f"{key}_cost"
        ]

        rows.append(
            {
                "strategy":
                    strategy_name,

                "periods":
                    len(net),

                "gross_cumulative_return":
                    cumulative_return(
                        gross
                    ),

                "net_cumulative_return":
                    cumulative_return(
                        net
                    ),

                "annualized_return":
                    annualized_return(
                        net
                    ),

                "annualized_volatility":
                    annualized_volatility(
                        net
                    ),

                "sharpe_ratio":
                    sharpe_ratio(
                        net, strategy_rf
                    ),

                "sortino_ratio":
                    sortino_ratio(
                        net, strategy_rf
                    ),

                "maximum_drawdown":
                    maximum_drawdown(
                        net
                    ),

                "hit_rate":
                    hit_rate(
                        net
                    ),

                "average_turnover":
                    turnover.mean(),

                "total_turnover":
                    turnover.sum(),

                "total_transaction_cost":
                    costs.sum(),
            }
        )

    return pd.DataFrame(rows)


# ============================================================
# TURNOVER SUMMARY
# ============================================================

def build_turnover_summary(
    portfolio,
):

    strategies = {
        "Equal Weight Universe":
            "universe",

        "Top Quintile Long":
            "top_quintile",

        "Bottom Quintile Long":
            "bottom_quintile",

        "Long Short":
            "long_short",
    }

    rows = []

    for (
        strategy_name,
        key,
    ) in strategies.items():

        turnover = portfolio[
            f"{key}_turnover"
        ]

        costs = portfolio[
            f"{key}_cost"
        ]

        rows.append(
            {
                "strategy":
                    strategy_name,

                "average_turnover":
                    turnover.mean(),

                "median_turnover":
                    turnover.median(),

                "maximum_turnover":
                    turnover.max(),

                "total_turnover":
                    turnover.sum(),

                "total_transaction_cost":
                    costs.sum(),
            }
        )

    return pd.DataFrame(rows)


# ============================================================
# YEARLY SUMMARY
# ============================================================

def build_yearly_summary(
    portfolio,
):

    temp = portfolio.copy()

    temp["year"] = (
        temp["date"]
        .dt.year
    )

    strategies = {
        "Equal Weight Universe":
            "universe_net_return",

        "Top Quintile Long":
            "top_quintile_net_return",

        "Bottom Quintile Long":
            "bottom_quintile_net_return",

        "Long Short":
            "long_short_net_return",
    }

    period_rf, _ = period_risk_free(temp["date"])

    rows = []

    for year, group in (
        temp.groupby("year")
    ):

        for (
            strategy_name,
            column,
        ) in strategies.items():

            returns = (
                group[column]
                .dropna()
            )

            if returns.empty:
                continue

            rows.append(
                {
                    "year":
                        int(year),

                    "strategy":
                        strategy_name,

                    "periods":
                        len(returns),

                    "cumulative_return":
                        cumulative_return(
                            returns
                        ),

                    "sharpe_ratio":
                        sharpe_ratio(
                            returns,
                            None if column.startswith("long_short") else period_rf
                        ),

                    "maximum_drawdown":
                        maximum_drawdown(
                            returns
                        ),

                    "hit_rate":
                        hit_rate(
                            returns
                        ),
                }
            )

    return pd.DataFrame(rows)


# ============================================================
# SCORE-BUCKET DIAGNOSTIC
# ============================================================

def build_bucket_summary(
    rankings,
):

    summary = (
        rankings.groupby(
            "score_quintile"
        )
        .agg(
            observations=(
                "ticker",
                "size",
            ),

            mean_probability=(
                "up_probability",
                "mean",
            ),

            mean_forward_return=(
                "forward_return_20d",
                "mean",
            ),

            median_forward_return=(
                "forward_return_20d",
                "median",
            ),

            positive_rate=(
                "forward_return_20d",
                lambda x:
                (
                    x > 0
                ).mean(),
            ),
        )
        .reset_index()
    )

    return summary


# ============================================================
# OUTPUT FORMATTING
# ============================================================

def show_bucket_summary(summary):

    subheader(
        "DAY 55 SCORE QUINTILE CHECK"
    )

    display = summary.copy()

    display[
        "mean_probability"
    ] = (
        display[
            "mean_probability"
        ]
        .map(
            lambda x:
            f"{x:.4f}"
        )
    )

    display[
        "mean_forward_return"
    ] = (
        display[
            "mean_forward_return"
        ]
        .map(fmt_pct)
    )

    display[
        "median_forward_return"
    ] = (
        display[
            "median_forward_return"
        ]
        .map(fmt_pct)
    )

    display[
        "positive_rate"
    ] = (
        display[
            "positive_rate"
        ]
        .map(fmt_pct)
    )

    print(
        display.to_string(
            index=False
        )
    )


def show_performance_summary(summary):

    subheader(
        "PORTFOLIO PERFORMANCE SUMMARY"
    )

    display = summary.copy()

    percentage_columns = [
        "gross_cumulative_return",
        "net_cumulative_return",
        "annualized_return",
        "annualized_volatility",
        "maximum_drawdown",
        "hit_rate",
        "average_turnover",
        "total_transaction_cost",
    ]

    for column in percentage_columns:

        display[column] = (
            display[column]
            .map(fmt_pct)
        )

    display[
        "sharpe_ratio"
    ] = (
        display[
            "sharpe_ratio"
        ]
        .map(fmt_num)
    )

    display[
        "sortino_ratio"
    ] = (
        display[
            "sortino_ratio"
        ]
        .map(fmt_num)
    )

    display[
        "total_turnover"
    ] = (
        display[
            "total_turnover"
        ]
        .map(
            lambda x:
            f"{x:.2f}"
        )
    )

    print(
        display.to_string(
            index=False
        )
    )


# ============================================================
# MAIN
# ============================================================

def main():

    try:

        header(
            "VITTANTRA — DAY 56 "
            "PORTFOLIO ECONOMIC VALIDATION"
        )

        rankings = load_rankings()

        print(
            f"Raw Day 55 observations: "
            f"{len(rankings):,}"
        )

        print(
            f"Securities: "
            f"{rankings['ticker'].nunique()}"
        )

        print(
            f"Raw ranking dates: "
            f"{rankings['date'].nunique()}"
        )

        print(
            "Raw date range: "
            f"{rankings['date'].min().date()} "
            "to "
            f"{rankings['date'].max().date()}"
        )

        rankings = (
            assign_quintiles(
                rankings
            )
        )

        print()
        print(
            f"Validated ranking observations: "
            f"{len(rankings):,}"
        )

        print(
            f"Validated ranking dates: "
            f"{rankings['date'].nunique()}"
        )

        print(
            f"Forward-return horizon: "
            f"{FORWARD_DAYS} trading days"
        )

        print(
            f"Annualization periods/year: "
            f"{PERIODS_PER_YEAR:.2f}"
        )

        print(
            "Transaction-cost assumption: "
            f"{TRANSACTION_COST_BPS:.1f} bps "
            "per unit of turnover"
        )

        bucket_summary = (
            build_bucket_summary(
                rankings
            )
        )

        show_bucket_summary(
            bucket_summary
        )

        portfolio = (
            build_portfolios(
                rankings
            )
        )

        summary = (
            build_summary(
                portfolio
            )
        )

        turnover_summary = (
            build_turnover_summary(
                portfolio
            )
        )

        yearly_summary = (
            build_yearly_summary(
                portfolio
            )
        )

        show_performance_summary(
            summary
        )

        subheader(
            "TOP VS BOTTOM ECONOMIC SPREAD"
        )

        indexed = (
            summary.set_index(
                "strategy"
            )
        )

        top = indexed.loc[
            "Top Quintile Long"
        ]

        bottom = indexed.loc[
            "Bottom Quintile Long"
        ]

        long_short = indexed.loc[
            "Long Short"
        ]

        print(
            "Top quintile annualized return: "
            f"{fmt_pct(top['annualized_return'])}"
        )

        print(
            "Bottom quintile annualized return: "
            f"{fmt_pct(bottom['annualized_return'])}"
        )

        print(
            "Top-minus-bottom annualized difference: "
            f"{fmt_pct(top['annualized_return'] - bottom['annualized_return'])}"
        )

        print(
            "Long-short annualized return: "
            f"{fmt_pct(long_short['annualized_return'])}"
        )

        print(
            "Long-short Sharpe ratio: "
            f"{fmt_num(long_short['sharpe_ratio'])}"
        )

        print(
            "Long-short maximum drawdown: "
            f"{fmt_pct(long_short['maximum_drawdown'])}"
        )

        print(
            "Long-short hit rate: "
            f"{fmt_pct(long_short['hit_rate'])}"
        )

        subheader(
            "BACKTEST COVERAGE"
        )

        print(
            f"Portfolio periods: "
            f"{len(portfolio)}"
        )

        print(
            "First portfolio date: "
            f"{portfolio['date'].min().date()}"
        )

        print(
            "Last portfolio date: "
            f"{portfolio['date'].max().date()}"
        )

        print(
            "Average securities per period: "
            f"{portfolio['securities'].mean():.1f}"
        )

        print(
            "Average top-quintile holdings: "
            f"{portfolio['top_count'].mean():.1f}"
        )

        print(
            "Average bottom-quintile holdings: "
            f"{portfolio['bottom_count'].mean():.1f}"
        )

        subheader(
            "INTERPRETATION NOTES"
        )

        print(
            "- Day 56 consumes Day 55's "
            "out-of-sample ML rankings."
        )

        print(
            "- The machine-learning model is not "
            "retrained inside Day 56."
        )

        print(
            "- Cross-sectional quintiles are rebuilt "
            "independently on every ranking date."
        )

        print(
            "- The top quintile contains the securities "
            "with the highest model probabilities."
        )

        print(
            "- The bottom quintile contains the securities "
            "with the lowest model probabilities."
        )

        print(
            "- The long-short portfolio is approximately "
            "50% long and 50% short."
        )

        print(
            "- Returns represent approximately "
            "20-trading-day holding periods."
        )

        print(
            "- Annualization uses 252 / 20 periods "
            "per year rather than treating observations "
            "as daily returns."
        )

        print(
            "- Transaction costs are deducted from "
            "estimated portfolio turnover."
        )

        print(
            "- Borrow costs, financing costs, taxes, "
            "market impact and capacity are not fully modeled."
        )

        print(
            "- Historical backtest performance does not "
            "establish future investment performance."
        )

        portfolio.to_csv(
            OUTPUT_PERIODS,
            index=False,
        )

        summary.to_csv(
            OUTPUT_SUMMARY,
            index=False,
        )

        yearly_summary.to_csv(
            OUTPUT_YEARLY,
            index=False,
        )

        turnover_summary.to_csv(
            OUTPUT_TURNOVER,
            index=False,
        )

        subheader(
            "FILES CREATED"
        )

        print(
            OUTPUT_PERIODS.name
        )

        print(
            OUTPUT_SUMMARY.name
        )

        print(
            OUTPUT_YEARLY.name
        )

        print(
            OUTPUT_TURNOVER.name
        )

        print()
        print(
            "Day 56 portfolio backtest complete."
        )

    except Exception as exc:

        print()
        print(
            "DAY 56 FAILED"
        )

        print(
            "=" * 100
        )

        print(
            f"{type(exc).__name__}: {exc}"
        )

        print()
        print(
            "No conclusions should be drawn "
            "from an incomplete backtest."
        )

        sys.exit(1)


if __name__ == "__main__":
    main()