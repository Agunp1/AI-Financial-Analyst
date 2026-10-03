"""
VITTANTRA
Day 58 — Factor & Exposure Attribution

Purpose
-------
Diagnose whether the Day 56 long-short portfolio return may be explained by
systematic market/factor exposures rather than a genuinely differentiated
cross-sectional signal.

This module DOES NOT:
- retrain the ML model
- change Day 55 rankings
- change Day 56 portfolio construction
- change Day 57 robustness tests

This module ONLY performs independent attribution / diagnostics.

Inputs
------
day56_portfolio_periods.csv

Outputs
-------
day58_factor_returns.csv
day58_factor_exposures.csv
day58_factor_regression_summary.csv
day58_factor_attribution.csv
day58_rolling_exposures.csv
day58_factor_correlation_matrix.csv
day58_diagnostics.csv

Important
---------
ETF returns are used as practical factor proxies.

They are not identical to institutional academic factors such as
Fama-French SMB/HML or proprietary risk-model factors.

Day 58 is therefore an exposure-diagnostic layer, not a claim of
formal factor-model alpha.
"""

from __future__ import annotations

import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import t as student_t

warnings.filterwarnings("ignore")


# ==============================================================
# CONFIGURATION
# ==============================================================

INPUT_FILE = Path("day56_portfolio_periods.csv")

OUTPUT_FACTOR_RETURNS = Path("day58_factor_returns.csv")
OUTPUT_EXPOSURES = Path("day58_factor_exposures.csv")
OUTPUT_REGRESSION = Path("day58_factor_regression_summary.csv")
OUTPUT_ATTRIBUTION = Path("day58_factor_attribution.csv")
OUTPUT_ROLLING = Path("day58_rolling_exposures.csv")
OUTPUT_CORRELATIONS = Path("day58_factor_correlation_matrix.csv")
OUTPUT_DIAGNOSTICS = Path("day58_diagnostics.csv")


# ETF / market proxies.
#
# These are deliberately diversified because Vittantra is moving toward
# a multi-asset risk architecture.
PROXY_TICKERS = {
    "market": "SPY",
    "small_cap": "IWM",
    "value": "IWD",
    "growth": "IWF",
    "momentum": "MTUM",
    "quality": "QUAL",
    "low_volatility": "USMV",
    "treasury": "IEF",
    "high_yield": "HYG",
    "gold": "GLD",
    "dollar": "UUP",
}


# Factors that will enter the main multivariate regression.
MAIN_FACTORS = [
    "market_factor",
    "size_factor",
    "value_factor",
    "momentum_factor",
    "quality_factor",
    "low_vol_factor",
    "rates_factor",
    "credit_factor",
    "gold_factor",
    "dollar_factor",
]


MIN_REGRESSION_OBSERVATIONS = 15

ROLLING_WINDOW = 12

EPSILON = 1e-12


# ==============================================================
# HELPERS
# ==============================================================

def section(title: str) -> None:
    print()
    print("=" * 78)
    print(title)
    print("=" * 78)


def safe_float(value) -> float:
    try:
        value = float(value)
        if np.isfinite(value):
            return value
    except Exception:
        pass
    return np.nan


def detect_date_column(df: pd.DataFrame) -> str:
    """
    Detect the most likely date column without depending on one fixed
    historical schema.
    """

    preferred_names = [
        "date",
        "rebalance_date",
        "portfolio_date",
        "signal_date",
        "period_date",
        "start_date",
    ]

    lower_map = {str(c).lower(): c for c in df.columns}

    for name in preferred_names:
        if name in lower_map:
            candidate = lower_map[name]

            parsed = pd.to_datetime(
                df[candidate],
                errors="coerce",
            )

            if parsed.notna().mean() >= 0.80:
                return candidate

    # Fallback:
    # attempt parsing each column as dates.
    best_column = None
    best_rate = 0.0

    for column in df.columns:
        parsed = pd.to_datetime(
            df[column],
            errors="coerce",
        )

        rate = parsed.notna().mean()

        if rate > best_rate:
            best_rate = rate
            best_column = column

    if best_column is None or best_rate < 0.80:
        raise KeyError(
            "Could not reliably detect the portfolio date column.\n"
            f"Available columns: {df.columns.tolist()}"
        )

    return best_column


def require_column(
    df: pd.DataFrame,
    possible_names: list[str],
    description: str,
) -> str:
    """
    Locate a required column using several permitted names.
    """

    lower_map = {str(c).lower(): c for c in df.columns}

    for name in possible_names:
        if name.lower() in lower_map:
            return lower_map[name.lower()]

    raise KeyError(
        f"Could not locate {description}.\n"
        f"Tried: {possible_names}\n"
        f"Available columns: {df.columns.tolist()}"
    )


def calculate_ols(
    y: pd.Series,
    x: pd.DataFrame,
) -> dict:
    """
    Lightweight ordinary least-squares implementation.

    This avoids requiring statsmodels and keeps Day 58 reproducible with
    numpy + pandas.
    """

    working = pd.concat(
        [
            y.rename("target"),
            x,
        ],
        axis=1,
    ).dropna()

    if len(working) < MIN_REGRESSION_OBSERVATIONS:
        raise ValueError(
            "Not enough overlapping observations for regression. "
            f"Need at least {MIN_REGRESSION_OBSERVATIONS}, "
            f"found {len(working)}."
        )

    y_values = working["target"].to_numpy(dtype=float)

    x_values = working[x.columns].to_numpy(dtype=float)

    # Intercept.
    design = np.column_stack(
        [
            np.ones(len(working)),
            x_values,
        ]
    )

    coefficients, _, _, _ = np.linalg.lstsq(
        design,
        y_values,
        rcond=None,
    )

    fitted = design @ coefficients

    residuals = y_values - fitted

    ss_residual = float(
        np.sum(
            residuals ** 2
        )
    )

    ss_total = float(
        np.sum(
            (
                y_values
                - np.mean(y_values)
            )
            ** 2
        )
    )

    if ss_total <= EPSILON:
        r_squared = np.nan
    else:
        r_squared = 1.0 - ss_residual / ss_total

    n = len(y_values)

    k = design.shape[1]

    if n > k and np.isfinite(r_squared):
        adjusted_r_squared = (
            1.0
            - (
                1.0 - r_squared
            )
            * (
                n - 1
            )
            / (
                n - k
            )
        )
    else:
        adjusted_r_squared = np.nan

    # Classical OLS standard errors: Var(b) = s^2 (X'X)^-1 with
    # s^2 = SSR / (n - k); t = b / SE; two-sided p-value from Student t.
    standard_errors = np.full(k, np.nan)
    t_statistics = np.full(k, np.nan)
    p_values = np.full(k, np.nan)
    if n > k:
        residual_variance = ss_residual / (n - k)
        covariance = residual_variance * np.linalg.pinv(design.T @ design)
        standard_errors = np.sqrt(np.clip(np.diag(covariance), 0.0, None))
        with np.errstate(divide="ignore", invalid="ignore"):
            t_statistics = coefficients / standard_errors
        p_values = 2.0 * student_t.sf(np.abs(t_statistics), df=n - k)

    output = {
        "observations": n,
        "intercept": coefficients[0],
        "intercept_standard_error": standard_errors[0],
        "intercept_t_statistic": t_statistics[0],
        "intercept_p_value": p_values[0],
        "r_squared": r_squared,
        "adjusted_r_squared": adjusted_r_squared,
        "mean_actual_return": np.mean(y_values),
        "mean_fitted_return": np.mean(fitted),
        "mean_residual_return": np.mean(residuals),
        "residual_std": np.std(
            residuals,
            ddof=1,
        ),
        "fitted_values": fitted,
        "residuals": residuals,
        "index": working.index,
    }

    for position, (factor, coefficient) in enumerate(
        zip(
            x.columns,
            coefficients[1:],
        ),
        start=1,
    ):
        output[factor] = coefficient
        output[f"{factor}_t_statistic"] = t_statistics[position]
        output[f"{factor}_p_value"] = p_values[position]

    return output


def calculate_univariate_beta(
    strategy: pd.Series,
    factor: pd.Series,
) -> dict:
    """
    Calculate correlation and simple beta of strategy vs one factor.
    """

    working = pd.concat(
        [
            strategy.rename("strategy"),
            factor.rename("factor"),
        ],
        axis=1,
    ).dropna()

    if len(working) < 5:
        return {
            "observations": len(working),
            "correlation": np.nan,
            "beta": np.nan,
            "alpha": np.nan,
            "r_squared": np.nan,
        }

    x = working["factor"].to_numpy(dtype=float)

    y = working["strategy"].to_numpy(dtype=float)

    variance = np.var(
        x,
        ddof=1,
    )

    if variance <= EPSILON:
        beta = np.nan
    else:
        beta = np.cov(
            y,
            x,
            ddof=1,
        )[0, 1] / variance

    if np.isfinite(beta):
        alpha = np.mean(y) - beta * np.mean(x)
    else:
        alpha = np.nan

    correlation = working["strategy"].corr(
        working["factor"]
    )

    if np.isfinite(correlation):
        r_squared = correlation ** 2
    else:
        r_squared = np.nan

    return {
        "observations": len(working),
        "correlation": correlation,
        "beta": beta,
        "alpha": alpha,
        "r_squared": r_squared,
    }


# ==============================================================
# LOAD DAY 56 PORTFOLIO RESULTS
# ==============================================================

def load_portfolio_periods() -> tuple[
    pd.DataFrame,
    str,
    str,
]:
    section(
        "DAY 58 — LOADING DAY 56 PORTFOLIO RESULTS"
    )

    if not INPUT_FILE.exists():
        raise FileNotFoundError(
            f"Required input file not found: {INPUT_FILE}"
        )

    df = pd.read_csv(
        INPUT_FILE
    )

    if df.empty:
        raise ValueError(
            f"{INPUT_FILE} is empty."
        )

    date_column = detect_date_column(
        df
    )

    strategy_column = require_column(
        df,
        [
            "long_short_net_return",
            "long_short_return",
            "long_short_gross_return",
        ],
        "long-short strategy return column",
    )

    df[date_column] = pd.to_datetime(
        df[date_column],
        errors="coerce",
    )

    df[strategy_column] = pd.to_numeric(
        df[strategy_column],
        errors="coerce",
    )

    df = (
        df
        .dropna(
            subset=[
                date_column,
                strategy_column,
            ]
        )
        .sort_values(
            date_column
        )
        .drop_duplicates(
            subset=[
                date_column
            ],
            keep="last",
        )
        .reset_index(
            drop=True
        )
    )

    if len(df) < MIN_REGRESSION_OBSERVATIONS:
        raise ValueError(
            "Too few valid Day 56 portfolio periods for Day 58."
        )

    print(
        f"Input file: {INPUT_FILE}"
    )

    print(
        f"Detected date column: {date_column}"
    )

    print(
        f"Strategy return column: {strategy_column}"
    )

    print(
        f"Portfolio periods: {len(df)}"
    )

    print(
        f"First date: {df[date_column].min().date()}"
    )

    print(
        f"Last date: {df[date_column].max().date()}"
    )

    print(
        f"Mean long-short return: "
        f"{df[strategy_column].mean():.6f}"
    )

    return (
        df,
        date_column,
        strategy_column,
    )


# ==============================================================
# YFINANCE
# ==============================================================

def import_yfinance():
    try:
        import yfinance as yf

        return yf

    except ImportError as exc:
        raise ImportError(
            "\nDay 58 needs the yfinance package to retrieve "
            "factor-proxy market data.\n\n"
            "Install it with:\n"
            "    pip install yfinance\n\n"
            "Then rerun:\n"
            "    python ml_factor_attribution.py\n"
        ) from exc


def download_proxy_prices(
    start_date: pd.Timestamp,
    end_date: pd.Timestamp,
) -> pd.DataFrame:
    section(
        "DOWNLOADING FACTOR PROXY DATA"
    )

    yf = import_yfinance()

    tickers = list(
        PROXY_TICKERS.values()
    )

    # Extra buffer before and after the strategy period.
    download_start = (
        start_date
        - pd.Timedelta(
            days=15
        )
    )

    download_end = (
        end_date
        + pd.Timedelta(
            days=45
        )
    )

    print(
        "Factor proxies:"
    )

    for factor_name, ticker in PROXY_TICKERS.items():
        print(
            f"  {factor_name:<16} -> {ticker}"
        )

    print()
    print(
        f"Download window: "
        f"{download_start.date()} "
        f"to {download_end.date()}"
    )

    raw = yf.download(
        tickers=tickers,
        start=download_start.strftime(
            "%Y-%m-%d"
        ),
        end=download_end.strftime(
            "%Y-%m-%d"
        ),
        auto_adjust=True,
        progress=False,
        group_by="column",
        threads=True,
    )

    if raw is None or len(raw) == 0:
        raise RuntimeError(
            "No market data was returned by yfinance."
        )

    # yfinance may return a MultiIndex even when using several symbols.
    if isinstance(
        raw.columns,
        pd.MultiIndex,
    ):
        if "Close" in raw.columns.get_level_values(0):
            prices = raw["Close"].copy()

        elif "Adj Close" in raw.columns.get_level_values(0):
            prices = raw["Adj Close"].copy()

        else:
            raise KeyError(
                "Downloaded Yahoo data does not contain Close prices."
            )

    else:
        # Defensive fallback.
        prices = raw.copy()

    if isinstance(
        prices,
        pd.Series,
    ):
        prices = prices.to_frame()

    prices.index = pd.to_datetime(
        prices.index
    )

    prices = (
        prices
        .sort_index()
        .replace(
            [
                np.inf,
                -np.inf,
            ],
            np.nan,
        )
        .ffill()
    )

    missing_tickers = [
        ticker
        for ticker in tickers
        if ticker not in prices.columns
    ]

    if missing_tickers:
        raise RuntimeError(
            "Missing factor proxy price series: "
            + ", ".join(
                missing_tickers
            )
        )

    prices = prices[
        tickers
    ].copy()

    print(
        f"Downloaded trading days: {len(prices)}"
    )

    return prices


# ==============================================================
# PERIOD RETURNS
# ==============================================================

def nearest_price_on_or_after(
    prices: pd.Series,
    date: pd.Timestamp,
) -> tuple[pd.Timestamp, float]:
    valid = prices.loc[
        prices.index >= date
    ].dropna()

    if valid.empty:
        return (
            pd.NaT,
            np.nan,
        )

    return (
        valid.index[0],
        float(
            valid.iloc[0]
        ),
    )


def calculate_proxy_period_returns(
    portfolio: pd.DataFrame,
    date_column: str,
    prices: pd.DataFrame,
) -> pd.DataFrame:
    section(
        "CALCULATING PERIOD-MATCHED FACTOR RETURNS"
    )

    portfolio_dates = (
        portfolio[date_column]
        .sort_values()
        .reset_index(
            drop=True
        )
    )

    median_gap = portfolio_dates.diff().dt.days.median()

    if not np.isfinite(
        median_gap
    ):
        median_gap = 28.0

    median_gap = max(
        float(
            median_gap
        ),
        1.0,
    )

    rows = []

    for i, start_date in enumerate(
        portfolio_dates
    ):
        if i < len(
            portfolio_dates
        ) - 1:
            end_date = portfolio_dates.iloc[
                i + 1
            ]

        else:
            end_date = (
                start_date
                + pd.Timedelta(
                    days=median_gap
                )
            )

        row = {
            "date": start_date,
            "period_target_end": end_date,
        }

        for ticker in prices.columns:
            start_actual, start_price = nearest_price_on_or_after(
                prices[ticker],
                start_date,
            )

            end_actual, end_price = nearest_price_on_or_after(
                prices[ticker],
                end_date,
            )

            row[
                f"{ticker}_start_date"
            ] = start_actual

            row[
                f"{ticker}_end_date"
            ] = end_actual

            if (
                np.isfinite(
                    start_price
                )
                and np.isfinite(
                    end_price
                )
                and abs(
                    start_price
                ) > EPSILON
            ):
                period_return = (
                    end_price
                    / start_price
                    - 1.0
                )

            else:
                period_return = np.nan

            row[
                f"{ticker}_return"
            ] = period_return

        rows.append(
            row
        )

    period_returns = pd.DataFrame(
        rows
    )

    print(
        f"Constructed factor return periods: {len(period_returns)}"
    )

    return period_returns


# ==============================================================
# FACTOR DEFINITIONS
# ==============================================================

def construct_factor_returns(
    period_returns: pd.DataFrame,
) -> pd.DataFrame:
    section(
        "CONSTRUCTING FACTOR PROXIES"
    )

    result = period_returns[
        [
            "date",
            "period_target_end",
        ]
    ].copy()

    spy = period_returns[
        "SPY_return"
    ]

    iwm = period_returns[
        "IWM_return"
    ]

    iwd = period_returns[
        "IWD_return"
    ]

    iwf = period_returns[
        "IWF_return"
    ]

    mtum = period_returns[
        "MTUM_return"
    ]

    qual = period_returns[
        "QUAL_return"
    ]

    usmv = period_returns[
        "USMV_return"
    ]

    ief = period_returns[
        "IEF_return"
    ]

    hyg = period_returns[
        "HYG_return"
    ]

    gld = period_returns[
        "GLD_return"
    ]

    uup = period_returns[
        "UUP_return"
    ]

    # ----------------------------------------------------------
    # Practical tradable factor proxies
    # ----------------------------------------------------------

    # Broad equity market.
    result[
        "market_factor"
    ] = spy

    # Smaller companies relative to broad market.
    result[
        "size_factor"
    ] = (
        iwm
        - spy
    )

    # Value relative to growth.
    result[
        "value_factor"
    ] = (
        iwd
        - iwf
    )

    # Momentum relative to broad market.
    result[
        "momentum_factor"
    ] = (
        mtum
        - spy
    )

    # Quality relative to broad market.
    result[
        "quality_factor"
    ] = (
        qual
        - spy
    )

    # Low volatility relative to broad market.
    result[
        "low_vol_factor"
    ] = (
        usmv
        - spy
    )

    # Intermediate Treasuries.
    result[
        "rates_factor"
    ] = ief

    # High-yield credit relative to Treasury duration proxy.
    result[
        "credit_factor"
    ] = (
        hyg
        - ief
    )

    # Defensive / real-asset proxy.
    result[
        "gold_factor"
    ] = gld

    # U.S. dollar exposure.
    result[
        "dollar_factor"
    ] = uup

    print(
        "Factor definitions:"
    )

    print(
        "  market_factor       = SPY"
    )

    print(
        "  size_factor         = IWM - SPY"
    )

    print(
        "  value_factor        = IWD - IWF"
    )

    print(
        "  momentum_factor     = MTUM - SPY"
    )

    print(
        "  quality_factor      = QUAL - SPY"
    )

    print(
        "  low_vol_factor      = USMV - SPY"
    )

    print(
        "  rates_factor        = IEF"
    )

    print(
        "  credit_factor       = HYG - IEF"
    )

    print(
        "  gold_factor         = GLD"
    )

    print(
        "  dollar_factor       = UUP"
    )

    return result


# ==============================================================
# MERGE
# ==============================================================

def merge_strategy_and_factors(
    portfolio: pd.DataFrame,
    date_column: str,
    strategy_column: str,
    factors: pd.DataFrame,
) -> pd.DataFrame:
    section(
        "ALIGNING STRATEGY AND FACTORS"
    )

    strategy = portfolio[
        [
            date_column,
            strategy_column,
        ]
    ].copy()

    strategy = strategy.rename(
        columns={
            date_column: "date",
            strategy_column: "strategy_return",
        }
    )

    merged = strategy.merge(
        factors,
        on="date",
        how="left",
        validate="one_to_one",
    )

    for column in [
        "strategy_return",
        *MAIN_FACTORS,
    ]:
        merged[column] = pd.to_numeric(
            merged[column],
            errors="coerce",
        )

    overlap = merged[
        [
            "strategy_return",
            *MAIN_FACTORS,
        ]
    ].dropna()

    print(
        f"Strategy periods: {len(strategy)}"
    )

    print(
        f"Complete factor-overlap periods: {len(overlap)}"
    )

    if len(
        overlap
    ) < MIN_REGRESSION_OBSERVATIONS:
        raise ValueError(
            "Too few complete strategy/factor observations "
            "for Day 58 regression."
        )

    return merged


# ==============================================================
# FACTOR EXPOSURES
# ==============================================================

def build_univariate_exposures(
    merged: pd.DataFrame,
) -> pd.DataFrame:
    section(
        "ESTIMATING INDIVIDUAL FACTOR EXPOSURES"
    )

    rows = []

    for factor in MAIN_FACTORS:
        stats = calculate_univariate_beta(
            merged[
                "strategy_return"
            ],
            merged[
                factor
            ],
        )

        row = {
            "factor": factor,
            **stats,
        }

        rows.append(
            row
        )

    exposures = pd.DataFrame(
        rows
    )

    exposures[
        "absolute_correlation"
    ] = exposures[
        "correlation"
    ].abs()

    exposures[
        "absolute_beta"
    ] = exposures[
        "beta"
    ].abs()

    exposures = exposures.sort_values(
        "absolute_correlation",
        ascending=False,
    ).reset_index(
        drop=True
    )

    print()
    print(
        exposures[
            [
                "factor",
                "correlation",
                "beta",
                "r_squared",
            ]
        ].to_string(
            index=False
        )
    )

    return exposures


# ==============================================================
# MULTIVARIATE REGRESSION
# ==============================================================

def run_multifactor_regression(
    merged: pd.DataFrame,
) -> tuple[
    pd.DataFrame,
    pd.DataFrame,
]:
    section(
        "RUNNING MULTI-FACTOR ATTRIBUTION"
    )

    usable_factors = []

    for factor in MAIN_FACTORS:
        series = pd.to_numeric(
            merged[factor],
            errors="coerce",
        )

        if (
            series.notna().sum()
            >= MIN_REGRESSION_OBSERVATIONS
            and series.std(
                ddof=1
            )
            > EPSILON
        ):
            usable_factors.append(
                factor
            )

    if not usable_factors:
        raise ValueError(
            "No usable factor columns were available."
        )

    regression = calculate_ols(
        y=merged[
            "strategy_return"
        ],
        x=merged[
            usable_factors
        ],
    )

    period_days = (
        merged[
            "period_target_end"
        ]
        - merged[
            "date"
        ]
    ).dt.days

    typical_period_days = period_days.median()

    if (
        not np.isfinite(
            typical_period_days
        )
        or typical_period_days <= 0
    ):
        typical_period_days = 28.0

    periods_per_year = (
        365.25
        / typical_period_days
    )

    period_alpha = safe_float(
        regression[
            "intercept"
        ]
    )

    if np.isfinite(
        period_alpha
    ):
        annualized_alpha_simple = (
            period_alpha
            * periods_per_year
        )

        if period_alpha > -1:
            annualized_alpha_compounded = (
                (
                    1.0
                    + period_alpha
                )
                ** periods_per_year
                - 1.0
            )

        else:
            annualized_alpha_compounded = np.nan

    else:
        annualized_alpha_simple = np.nan
        annualized_alpha_compounded = np.nan

    summary_rows = [
        {
            "metric": "observations",
            "value": regression[
                "observations"
            ],
        },
        {
            "metric": "period_alpha_intercept",
            "value": period_alpha,
        },
        {
            "metric": "annualized_alpha_simple",
            "value": annualized_alpha_simple,
        },
        {
            "metric": "annualized_alpha_compounded",
            "value": annualized_alpha_compounded,
        },
        {
            "metric": "r_squared",
            "value": regression[
                "r_squared"
            ],
        },
        {
            "metric": "adjusted_r_squared",
            "value": regression[
                "adjusted_r_squared"
            ],
        },
        {
            "metric": "mean_strategy_return",
            "value": regression[
                "mean_actual_return"
            ],
        },
        {
            "metric": "mean_factor_explained_return",
            "value": regression[
                "mean_fitted_return"
            ],
        },
        {
            "metric": "mean_residual_return",
            "value": regression[
                "mean_residual_return"
            ],
        },
        {
            "metric": "residual_std",
            "value": regression[
                "residual_std"
            ],
        },
        {
            "metric": "typical_period_days",
            "value": typical_period_days,
        },
        {
            "metric": "estimated_periods_per_year",
            "value": periods_per_year,
        },
    ]

    for factor in usable_factors:
        summary_rows.append(
            {
                "metric": f"beta_{factor}",
                "value": regression[
                    factor
                ],
            }
        )

    summary_rows.extend(
        [
            {
                "metric": "alpha_standard_error",
                "value": regression["intercept_standard_error"],
            },
            {
                "metric": "alpha_t_statistic",
                "value": regression["intercept_t_statistic"],
            },
            {
                "metric": "alpha_p_value",
                "value": regression["intercept_p_value"],
            },
            {
                "metric": "alpha_significant_at_5pct",
                "value": bool(regression["intercept_p_value"] < 0.05),
            },
        ]
    )

    for factor in usable_factors:
        summary_rows.append(
            {
                "metric": f"t_stat_{factor}",
                "value": regression[f"{factor}_t_statistic"],
            }
        )

    summary = pd.DataFrame(
        summary_rows
    )

    attribution = merged.loc[
        regression[
            "index"
        ],
        [
            "date",
            "strategy_return",
            *usable_factors,
        ],
    ].copy()

    attribution[
        "factor_model_fitted_return"
    ] = regression[
        "fitted_values"
    ]

    attribution[
        "factor_model_residual_return"
    ] = regression[
        "residuals"
    ]

    attribution[
        "cumulative_strategy_return"
    ] = (
        1.0
        + attribution[
            "strategy_return"
        ]
    ).cumprod() - 1.0

    attribution[
        "cumulative_factor_fitted_return"
    ] = (
        1.0
        + attribution[
            "factor_model_fitted_return"
        ]
    ).cumprod() - 1.0

    attribution[
        "cumulative_residual_return"
    ] = (
        1.0
        + attribution[
            "factor_model_residual_return"
        ]
    ).cumprod() - 1.0

    print()
    print(
        f"Observations: "
        f"{regression['observations']}"
    )

    print(
        f"Period alpha/intercept: "
        f"{period_alpha:.6f}"
    )

    print(
        f"R-squared: "
        f"{regression['r_squared']:.4f}"
    )

    print(
        f"Adjusted R-squared: "
        f"{regression['adjusted_r_squared']:.4f}"
    )

    print()
    print(
        "Multivariate factor coefficients:"
    )

    for factor in usable_factors:
        print(
            f"  {factor:<22} "
            f"{regression[factor]: .6f}"
        )

    return (
        summary,
        attribution,
    )


# ==============================================================
# ROLLING EXPOSURES
# ==============================================================

def build_rolling_exposures(
    merged: pd.DataFrame,
) -> pd.DataFrame:
    section(
        "CALCULATING ROLLING FACTOR EXPOSURES"
    )

    working = merged[
        [
            "date",
            "strategy_return",
            *MAIN_FACTORS,
        ]
    ].copy()

    rows = []

    if len(
        working
    ) < ROLLING_WINDOW:
        print(
            "Not enough observations for rolling attribution."
        )

        return pd.DataFrame()

    for end_index in range(
        ROLLING_WINDOW - 1,
        len(
            working
        ),
    ):
        window = working.iloc[
            end_index
            - ROLLING_WINDOW
            + 1:
            end_index
            + 1
        ]

        row = {
            "date": working.iloc[
                end_index
            ][
                "date"
            ],
            "rolling_window": ROLLING_WINDOW,
        }

        for factor in MAIN_FACTORS:
            stats = calculate_univariate_beta(
                window[
                    "strategy_return"
                ],
                window[
                    factor
                ],
            )

            row[
                f"beta_{factor}"
            ] = stats[
                "beta"
            ]

            row[
                f"corr_{factor}"
            ] = stats[
                "correlation"
            ]

        rows.append(
            row
        )

    rolling = pd.DataFrame(
        rows
    )

    print(
        f"Rolling exposure observations: {len(rolling)}"
    )

    return rolling


# ==============================================================
# CORRELATION MATRIX
# ==============================================================

def build_correlation_matrix(
    merged: pd.DataFrame,
) -> pd.DataFrame:
    section(
        "BUILDING FACTOR CORRELATION MATRIX"
    )

    columns = [
        "strategy_return",
        *MAIN_FACTORS,
    ]

    matrix = merged[
        columns
    ].corr()

    print(
        matrix.round(
            3
        ).to_string()
    )

    return matrix


# ==============================================================
# DIAGNOSTICS
# ==============================================================

def build_diagnostics(
    merged: pd.DataFrame,
    exposures: pd.DataFrame,
    regression_summary: pd.DataFrame,
) -> pd.DataFrame:
    section(
        "BUILDING DAY 58 DIAGNOSTIC SCORECARD"
    )

    metric_lookup = dict(
        zip(
            regression_summary[
                "metric"
            ],
            regression_summary[
                "value"
            ],
        )
    )

    r_squared = safe_float(
        metric_lookup.get(
            "r_squared"
        )
    )

    adjusted_r_squared = safe_float(
        metric_lookup.get(
            "adjusted_r_squared"
        )
    )

    alpha = safe_float(
        metric_lookup.get(
            "period_alpha_intercept"
        )
    )

    mean_residual = safe_float(
        metric_lookup.get(
            "mean_residual_return"
        )
    )

    max_abs_correlation = exposures[
        "absolute_correlation"
    ].max()

    most_correlated_factor = (
        exposures.sort_values(
            "absolute_correlation",
            ascending=False,
        )
        .iloc[0][
            "factor"
        ]
    )

    rows = [
        {
            "diagnostic": "factor_model_r_squared",
            "value": r_squared,
            "interpretation": (
                "Fraction of strategy-period variation "
                "associated with the factor proxy model."
            ),
        },
        {
            "diagnostic": "factor_model_adjusted_r_squared",
            "value": adjusted_r_squared,
            "interpretation": (
                "R-squared adjusted for number of factor proxies."
            ),
        },
        {
            "diagnostic": "period_alpha_intercept",
            "value": alpha,
            "interpretation": (
                "Regression intercept per portfolio period. "
                "Historical diagnostic only."
            ),
        },
        {
            "diagnostic": "mean_residual_return",
            "value": mean_residual,
            "interpretation": (
                "Average return not fitted by the selected "
                "factor proxies."
            ),
        },
        {
            "diagnostic": "largest_absolute_factor_correlation",
            "value": max_abs_correlation,
            "interpretation": (
                f"Most correlated factor: "
                f"{most_correlated_factor}."
            ),
        },
        {
            "diagnostic": "strategy_periods",
            "value": len(
                merged
            ),
            "interpretation": (
                "Total Day 56 portfolio periods included before "
                "complete-case regression filtering."
            ),
        },
    ]

    diagnostics = pd.DataFrame(
        rows
    )

    print()
    print(
        diagnostics.to_string(
            index=False
        )
    )

    return diagnostics


# ==============================================================
# SAVE OUTPUTS
# ==============================================================

def save_outputs(
    factor_returns: pd.DataFrame,
    exposures: pd.DataFrame,
    regression_summary: pd.DataFrame,
    attribution: pd.DataFrame,
    rolling: pd.DataFrame,
    correlations: pd.DataFrame,
    diagnostics: pd.DataFrame,
) -> None:
    section(
        "SAVING DAY 58 OUTPUTS"
    )

    factor_returns.to_csv(
        OUTPUT_FACTOR_RETURNS,
        index=False,
    )

    exposures.to_csv(
        OUTPUT_EXPOSURES,
        index=False,
    )

    regression_summary.to_csv(
        OUTPUT_REGRESSION,
        index=False,
    )

    attribution.to_csv(
        OUTPUT_ATTRIBUTION,
        index=False,
    )

    rolling.to_csv(
        OUTPUT_ROLLING,
        index=False,
    )

    correlations.to_csv(
        OUTPUT_CORRELATIONS,
        index=True,
    )

    diagnostics.to_csv(
        OUTPUT_DIAGNOSTICS,
        index=False,
    )

    outputs = [
        OUTPUT_FACTOR_RETURNS,
        OUTPUT_EXPOSURES,
        OUTPUT_REGRESSION,
        OUTPUT_ATTRIBUTION,
        OUTPUT_ROLLING,
        OUTPUT_CORRELATIONS,
        OUTPUT_DIAGNOSTICS,
    ]

    print(
        "Generated:"
    )

    for output in outputs:
        print(
            f"  {output}"
        )


# ==============================================================
# MAIN
# ==============================================================

def main() -> None:
    section(
        "VITTANTRA — DAY 58"
    )

    print(
        "Factor & Exposure Attribution"
    )

    print()
    print(
        "Day 58 is diagnostic only."
    )

    print(
        "The Day 55 ML model, Day 56 portfolio backtest, "
        "and Day 57 robustness suite remain unchanged."
    )

    try:
        (
            portfolio,
            date_column,
            strategy_column,
        ) = load_portfolio_periods()

        prices = download_proxy_prices(
            start_date=portfolio[
                date_column
            ].min(),
            end_date=portfolio[
                date_column
            ].max(),
        )

        proxy_period_returns = (
            calculate_proxy_period_returns(
                portfolio=portfolio,
                date_column=date_column,
                prices=prices,
            )
        )

        factor_returns = construct_factor_returns(
            proxy_period_returns
        )

        merged = merge_strategy_and_factors(
            portfolio=portfolio,
            date_column=date_column,
            strategy_column=strategy_column,
            factors=factor_returns,
        )

        exposures = build_univariate_exposures(
            merged
        )

        (
            regression_summary,
            attribution,
        ) = run_multifactor_regression(
            merged
        )

        rolling = build_rolling_exposures(
            merged
        )

        correlations = build_correlation_matrix(
            merged
        )

        diagnostics = build_diagnostics(
            merged=merged,
            exposures=exposures,
            regression_summary=regression_summary,
        )

        save_outputs(
            factor_returns=factor_returns,
            exposures=exposures,
            regression_summary=regression_summary,
            attribution=attribution,
            rolling=rolling,
            correlations=correlations,
            diagnostics=diagnostics,
        )

        section(
            "DAY 58 COMPLETE"
        )

        print(
            "Factor attribution completed successfully."
        )

        print()
        print(
            "Next research question:"
        )

        print(
            "How much of the historical long-short performance "
            "is associated with systematic exposures, and how "
            "much remains unexplained by these factor proxies?"
        )

        print()
        print(
            "Important:"
        )

        print(
            "A regression residual or positive intercept does NOT "
            "prove alpha. Day 58 is an attribution diagnostic, "
            "not evidence of guaranteed future performance."
        )

    except Exception as exc:
        section(
            "DAY 58 FAILED"
        )

        print(
            f"{type(exc).__name__}: {exc}"
        )

        print()
        print(
            "Days 1–57 have not been modified."
        )

        print(
            "Do not interpret Day 58 until the attribution "
            "pipeline completes successfully."
        )

        sys.exit(
            1
        )


if __name__ == "__main__":
    main()