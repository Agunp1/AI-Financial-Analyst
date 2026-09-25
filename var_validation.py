
import math

from scipy.stats import chi2


def kupiec_pof_test(exceptions, observations, confidence=0.95):
    """
    Kupiec proportion-of-failures test for VaR exceptions.

    H0: The true exception rate equals 1 - confidence.
    Returns the likelihood-ratio statistic and chi-square p-value.
    """
    if not isinstance(observations, int) or observations <= 0:
        raise ValueError("Observations must be a positive integer.")

    if not isinstance(exceptions, int):
        raise ValueError("Exceptions must be an integer.")

    if not 0 <= exceptions <= observations:
        raise ValueError(
            "Exceptions must be between zero and observations."
        )

    if not 0 < confidence < 1:
        raise ValueError("Confidence must be between zero and one.")

    expected_rate = 1 - confidence
    observed_rate = exceptions / observations

    def log_likelihood(rate):
        if rate == 0:
            return 0.0 if exceptions == 0 else -math.inf

        if rate == 1:
            return (
                0.0
                if exceptions == observations
                else -math.inf
            )

        return (
            exceptions * math.log(rate)
            + (observations - exceptions) * math.log1p(-rate)
        )

    lr_statistic = 2 * (
        log_likelihood(observed_rate)
        - log_likelihood(expected_rate)
    )

    lr_statistic = max(0.0, lr_statistic)
    p_value = float(chi2.sf(lr_statistic, df=1))

    return {
        "Observations": observations,
        "Exceptions": exceptions,
        "Expected Exception Rate": expected_rate,
        "Observed Exception Rate": observed_rate,
        "Kupiec LR Statistic": lr_statistic,
        "P-Value": p_value,
        "Reject at 5%": p_value < 0.05,
    }

import numpy as np
from scipy.stats import chi2


def christoffersen_independence_test(exception_series):
    """
    Test whether consecutive VaR exceptions are independent.

    exception_series: chronological sequence of booleans
                      (True = VaR breach).
    """
    exceptions = np.asarray(exception_series, dtype=int)

    if exceptions.ndim != 1 or len(exceptions) < 3:
        raise ValueError("At least three chronological observations are required.")

    if not np.isin(exceptions, [0, 1]).all():
        raise ValueError("Exceptions must contain only True/False or 0/1.")

    previous = exceptions[:-1]
    current = exceptions[1:]

    n00 = int(((previous == 0) & (current == 0)).sum())
    n01 = int(((previous == 0) & (current == 1)).sum())
    n10 = int(((previous == 1) & (current == 0)).sum())
    n11 = int(((previous == 1) & (current == 1)).sum())

    if n00 + n01 == 0 or n10 + n11 == 0:
        raise ValueError(
            "Both breach and non-breach states need outgoing transitions."
        )

    p01 = n01 / (n00 + n01)
    p11 = n11 / (n10 + n11)
    p = (n01 + n11) / (n00 + n01 + n10 + n11)

    def log_likelihood(successes, failures, probability):
        terms = 0.0
        if successes:
            if probability == 0:
                return float("-inf")
            terms += successes * np.log(probability)
        if failures:
            if probability == 1:
                return float("-inf")
            terms += failures * np.log1p(-probability)
        return terms

    log_null = log_likelihood(n01 + n11, n00 + n10, p)
    log_alt = (
        log_likelihood(n01, n00, p01)
        + log_likelihood(n11, n10, p11)
    )

    lr_statistic = max(0.0, 2 * (log_alt - log_null))
    p_value = float(chi2.sf(lr_statistic, df=1))

    return {
        "N00": n00,
        "N01": n01,
        "N10": n10,
        "N11": n11,
        "P01": p01,
        "P11": p11,
        "LR Independence": lr_statistic,
        "P-Value": p_value,
        "Reject at 5%": p_value < 0.05,
    }
from scipy.stats import chi2


def conditional_coverage_test(exceptions, confidence=0.95):
    """
    Combine Kupiec unconditional coverage and
    Christoffersen independence tests.
    """
    exceptions = list(exceptions)

    if len(exceptions) < 3:
        raise ValueError("At least 3 observations are required.")

    kupiec = kupiec_pof_test(
        sum(exceptions),
        len(exceptions),
        confidence
    )

    independence = christoffersen_independence_test(exceptions)

    lr_cc = (
        kupiec["Kupiec LR Statistic"]
       + independence["LR Independence"]
    )

    p_value = float(chi2.sf(lr_cc, df=2))

    return {
        "Conditional Coverage LR": lr_cc,
        "P-Value": p_value,
        "Reject at 5%": p_value < 0.05,
    }