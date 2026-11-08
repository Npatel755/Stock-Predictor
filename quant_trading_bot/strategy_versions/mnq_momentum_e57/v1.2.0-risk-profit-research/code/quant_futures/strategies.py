"""All strategies produce desired exposure at the same completed-bar timestamp."""
from enum import StrEnum
import numpy as np
import pandas as pd


BASELINES = ["sma", "ema", "adx", "donchian", "multi_timeframe", "rsi", "bollinger", "vwap",
             "vol_reversion", "opening_range", "previous_session", "compression", "momentum",
             "intraday_momentum", "volume_momentum", "vol_momentum"]


def baseline(name, bars, f, parameter=1.0, session="all"):
    c = bars.close
    trend = np.sign(f.ema_fast-f.ema_slow)
    z = f.zscore
    momentum = np.sign(f.momentum_10)
    def compare(upper, lower):
        return pd.Series(np.select([c > upper, c < lower], [1, -1], default=0), index=bars.index)
    choices = {
        "sma": np.sign(f.sma_fast-f.sma_slow),
        "ema": trend,
        "adx": trend.where(f.adx > 25*parameter, 0),
        "donchian": compare(f.prior_high, f.prior_low),
        "multi_timeframe": trend.where(trend == np.sign(f.htf_trend), 0),
        "rsi": pd.Series(np.select([f.rsi < 30/parameter, f.rsi > 100-30/parameter], [1, -1], default=0), index=bars.index),
        "bollinger": -np.sign(z).where(z.abs() >= 2*parameter, 0),
        "vwap": -np.sign(f.vwap_deviation).where(f.vwap_deviation.abs() > f.atr_relative*parameter, 0),
        "vol_reversion": -np.sign(f.momentum_3).where(f.momentum_3.abs() > f.volatility*2*parameter, 0),
        "opening_range": compare(f.opening_high, f.opening_low),
        "previous_session": compare(f.previous_session_high, f.previous_session_low),
        "compression": compare(f.prior_high, f.prior_low).where(f.vol_ratio.shift(1) < .75*parameter, 0),
        "momentum": momentum,
        "intraday_momentum": momentum.where(f.rth == 1, 0),
        "volume_momentum": momentum.where(f.relative_volume >= 1.2*parameter, 0),
        "vol_momentum": momentum.where(f.momentum_10.abs()/f.volatility.replace(0, np.nan) > parameter, 0),
    }
    if name not in choices:
        raise ValueError(name)
    result = choices[name].replace([np.inf, -np.inf], np.nan).fillna(0).astype(int)
    masks = {"all": pd.Series(True, index=f.index), "rth": f.rth.eq(1), "overnight": f.rth.eq(0),
             "open": f.session_bucket.eq(1), "midday": f.session_bucket.eq(2), "close": f.session_bucket.eq(3)}
    if session not in masks:
        raise ValueError(session)
    return result.where(masks[session], 0)


def causal_regime(f):
    # Fixed thresholds, no full-sample quantiles. Uncertain conditions abstain.
    return pd.Series(np.select([f.vol_percentile > .95, (f.adx > 25) & (f.vol_percentile <= .95),
                              (f.adx < 20) & (f.vol_percentile <= .8)],
                             ["uncertain", "trend", "range"], default="uncertain"), index=f.index)


def regime_strategy(bars, f):
    regime = causal_regime(f)
    return baseline("ema", bars, f).where(regime.eq("trend"),
        baseline("bollinger", bars, f).where(regime.eq("range"), 0))


def ensemble(signals, weights=None, abstention=.34):
    signals = pd.DataFrame(signals)
    if weights is None:
        weights = np.ones(signals.shape[1])/signals.shape[1]
    weights = np.asarray(weights, dtype=float)
    if len(weights) != signals.shape[1] or not np.isfinite(weights).all() or (weights < 0).any() or weights.sum() <= 0:
        raise ValueError("Invalid ensemble weights")
    vote = signals.dot(weights/weights.sum())
    return np.sign(vote).where(vote.abs() >= abstention, 0).astype(int)


def fitted_ensemble_weights(training_strategy_returns):
    # Caller supplies eligible training/OOS-inner returns only, never outer validation.
    scores = pd.DataFrame(training_strategy_returns).mean().clip(lower=0).to_numpy()
    return scores/scores.sum() if scores.sum() else np.ones(len(scores))/len(scores)
