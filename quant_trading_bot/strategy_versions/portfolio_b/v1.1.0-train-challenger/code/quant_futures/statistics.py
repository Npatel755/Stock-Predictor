import numpy as np
from scipy.stats import norm
from .metrics import probabilistic_sharpe


def deflated_sharpe_diagnostic(returns, trial_sharpes, effective_independent_trials=None):
    """IID diagnostic, not a substitute for block inference on autocorrelated returns."""
    trials = np.asarray(trial_sharpes, dtype=float)
    n = len(trials) if effective_independent_trials is None else effective_independent_trials
    if len(trials) < 2 or n < 2:
        return dict(probability=None, limitation="At least two trial Sharpes and effective trials required")
    euler = .5772156649
    reference = np.std(trials, ddof=1)*((1-euler)*norm.ppf(1-1/n)+euler*norm.ppf(1-1/(n*np.e)))
    return dict(probability=probabilistic_sharpe(returns, reference), reference_sharpe=float(reference),
        assumed_independent_trials=n, limitation="IID skew/kurtosis adjustment; correlated searches make effective trial count uncertain")


def reality_check(returns_matrix, draws=499, block=5, seed=20261106):
    """Centered circular block maximum-mean test across all supplied strategies.

    Related to White's Reality Check. Fixed aligned session returns, flat-cash
    benchmark, weak stationarity; not a complete correction for undisclosed searches.
    """
    x = np.asarray(returns_matrix, dtype=float)
    if x.ndim != 2 or not len(x) or not np.isfinite(x).all():
        raise ValueError("Aligned finite session-by-strategy returns required")
    means = x.mean(axis=0)
    observed = means.max()
    centered = x-means
    rng = np.random.default_rng(seed)
    maxima = []
    for _ in range(draws):
        starts = rng.integers(0, len(x), int(np.ceil(len(x)/block)))
        ids = ((starts[:, None]+np.arange(block)) % len(x)).ravel()[:len(x)]
        maxima.append(centered[ids].mean(axis=0).max())
    return dict(pvalue=float((1+np.count_nonzero(np.asarray(maxima) >= observed))/(draws+1)),
        strategies=x.shape[1], sessions=x.shape[0], draws=draws, block_sessions=block,
        insufficient_evidence=len(x) < 60, method="Centered block maximum-mean test vs cash; all supplied trials")
