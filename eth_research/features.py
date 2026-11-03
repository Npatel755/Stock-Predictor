"""Causal scale-free features from completed five-minute ETHUSD bars."""
import numpy as np
import pandas as pd

from .data import BAR_MINUTES, TICKER, validate_bars

BAR = pd.Timedelta(minutes=BAR_MINUTES)


def _segment_features(bars):
    c, o, h, l, v = [bars[k] for k in ["close", "open", "high", "low", "volume"]]
    f = pd.DataFrame(index=bars.index)
    r = c.pct_change(fill_method=None)
    for n in (1, 3, 6, 12, 24, 48, 96):
        f[f"return_{n}"] = c.pct_change(n, fill_method=None)
    for n in (6, 12, 24, 48, 96):
        f[f"ema_distance_{n}"] = c / c.ewm(span=n, adjust=False, min_periods=n).mean() - 1
    for n in (6, 12, 24, 48, 96):
        f[f"volatility_{n}"] = r.rolling(n).std()
    for n in (24, 96):
        f[f"price_z_{n}"] = ((c - c.rolling(n).mean()) / c.rolling(n).std().replace(0, np.nan)).fillna(0)
        f[f"volume_ratio_{n}"] = v / v.rolling(n).mean().replace(0, np.nan)
        f[f"high_distance_{n}"] = c / h.rolling(n).max() - 1
        f[f"low_distance_{n}"] = c / l.rolling(n).min() - 1
    f["range"] = (h - l) / c
    f["body"] = (c - o) / o
    f["upper_wick"] = (h - pd.concat([c, o], axis=1).max(axis=1)) / c
    f["lower_wick"] = (pd.concat([c, o], axis=1).min(axis=1) - l) / c
    f["gap"] = o / c.shift(1) - 1
    gain = c.diff().clip(lower=0).rolling(14).mean()
    loss = -c.diff().clip(upper=0).rolling(14).mean()
    f["rsi_14"] = (gain / (gain + loss).replace(0, np.nan)).fillna(0.5)
    tr = pd.concat([h - l, (h - c.shift()).abs(), (l - c.shift()).abs()], axis=1).max(axis=1)
    f["atr_14"] = tr.ewm(alpha=1 / 14, adjust=False, min_periods=14).mean() / c
    f["volume_change"] = np.log1p(v).diff()
    f["volume_z_24"] = ((np.log1p(v) - np.log1p(v).rolling(24).mean()) /
                         np.log1p(v).rolling(24).std().replace(0, np.nan)).fillna(0)
    f["macd"] = (c.ewm(span=12, adjust=False).mean() - c.ewm(span=26, adjust=False).mean()) / c
    return f


def build_features(bars, expected_ticker=TICKER):
    bars = validate_bars(bars, expected_ticker=expected_ticker)
    # Reset every rolling calculation at a missing bar; never bridge data gaps.
    groups = bars.timestamp.diff().ne(BAR).cumsum()
    parts = [_segment_features(part) for _, part in bars.groupby(groups, sort=False)]
    features = pd.concat(parts).sort_index()
    minute = bars.timestamp.dt.hour * 60 + bars.timestamp.dt.minute
    features["time_sin"] = np.sin(2 * np.pi * minute / 1440)
    features["time_cos"] = np.cos(2 * np.pi * minute / 1440)
    features["week_sin"] = np.sin(2 * np.pi * bars.timestamp.dt.dayofweek / 7)
    features["week_cos"] = np.cos(2 * np.pi * bars.timestamp.dt.dayofweek / 7)
    columns = features.columns.tolist()
    features = features.replace([np.inf, -np.inf], np.nan)
    result = pd.concat([bars, features], axis=1)
    result["information_time"] = result.timestamp + BAR
    # Signal at t close, execute at next bar open, exit at next bar close.
    adjacent = result.timestamp.shift(-1).sub(result.timestamp).eq(BAR)
    result["entry"] = result.open.shift(-1).where(adjacent)
    result["exit"] = result.close.shift(-1).where(adjacent)
    result["exit_high"] = result.high.shift(-1).where(adjacent)
    result["exit_low"] = result.low.shift(-1).where(adjacent)
    result["entry_time"] = result.timestamp.shift(-1).where(adjacent)
    result["label_end"] = (result.timestamp.shift(-1) + BAR).where(adjacent)
    result["forward_return"] = result.exit / result.entry - 1
    result["target"] = (result.forward_return > 0).astype(float).where(result.forward_return.notna())
    # Missing future bars remain unlabeled, never silently become DOWN labels.
    result = result.dropna(subset=columns).reset_index(drop=True)
    return result, columns


def eligible_indices(frame, sequence_length=24, labeled=True):
    continuous = frame.timestamp.sub(frame.timestamp.shift(sequence_length - 1)).eq(BAR * (sequence_length - 1))
    if labeled:
        continuous &= frame.target.notna()
    return np.flatnonzero(continuous.to_numpy())
