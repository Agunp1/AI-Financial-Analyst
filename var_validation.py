
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
