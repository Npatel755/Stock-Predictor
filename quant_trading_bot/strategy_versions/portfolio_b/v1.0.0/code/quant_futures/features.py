"""Features are available at completed-bar close; no future-confirmed backdating.

Wilder smoothing and pivot confirmation conventions reuse the audited design in
backtesting/indicators.py. Its fixed five-minute alignment is deliberately replaced.
"""
import numpy as np
import pandas as pd


def rma(values, length):
    out = np.full(len(values), np.nan)
    seed, last = [], np.nan
    for i, value in enumerate(values):
        if not np.isfinite(value):
            continue
        if np.isnan(last):
            seed.append(value)
            if len(seed) == length:
                last = float(np.mean(seed))
        else:
            last = (last * (length - 1) + value) / length
        out[i] = last
    return pd.Series(out, index=values.index)


def _one(bars, minutes=1):
    b = bars.reset_index(drop=True)
    # Constant additive roll offsets may alter return denominators; features reset
    # at raw contract changes rather than treating adjusted returns as tradable P&L.
    c, h, l, o, v = b.close, b.high, b.low, b.open, b.volume
    f = pd.DataFrame(index=b.index)
    f["return_1"] = c.pct_change(fill_method=None)
    f["log_return"] = np.log(c).diff()
    for n in (3, 5, 10, 20, 60):
        f[f"momentum_{n}"] = c.pct_change(n, fill_method=None)
    span = (h-l).replace(0, np.nan)
    f["range"] = (h-l)/c
    f["body"] = (c-o)/span
    f["close_open"] = c/o-1
    f["upper_wick"] = (h-pd.concat([o, c], axis=1).max(axis=1))/span
    f["lower_wick"] = (pd.concat([o, c], axis=1).min(axis=1)-l)/span
    prev = c.shift(1)
    tr = pd.concat([h-l, (h-prev).abs(), (l-prev).abs()], axis=1).max(axis=1)
    f["atr"] = rma(tr, 14)
    f["atr_relative"] = f.atr/c
    f["volatility"] = f.log_return.rolling(20).std()
    f["parkinson"] = (np.log(h/l).pow(2).rolling(20).mean()/(4*np.log(2))).pow(0.5)
    gk = 0.5*np.log(h/l)**2 - (2*np.log(2)-1)*np.log(c/o)**2
    f["garman_klass"] = gk.rolling(20).mean().clip(lower=0).pow(0.5)
    f["vol_of_vol"] = f.volatility.rolling(20).std()
    # Stable tie handling across batch/online rolling-variance implementations.
    f["vol_percentile"] = f.volatility.round(14).rolling(60).rank(pct=True)
    f["vol_ratio"] = f.log_return.rolling(5).std()/f.log_return.rolling(60).std().replace(0, np.nan)
    f["zscore"] = (c-c.rolling(20).mean())/c.rolling(20).std().replace(0, np.nan)
    f["sma_fast"] = c.rolling(10).mean()
    f["sma_slow"] = c.rolling(40).mean()
    f["ema_fast"] = c.ewm(span=10, adjust=False, min_periods=10).mean()
    f["ema_slow"] = c.ewm(span=40, adjust=False, min_periods=40).mean()
    f["trend_slope"] = c.rolling(20).apply(lambda x: np.polyfit(np.arange(20), x, 1)[0], raw=True)/c
    changes = c.diff()
    gain, loss = rma(changes.clip(lower=0), 14), rma(-changes.clip(upper=0), 14)
    f["rsi"] = 100-100/(1+gain/loss.replace(0, np.nan))
    f.loc[(loss == 0) & (gain > 0), "rsi"] = 100
    f.loc[(loss == 0) & (gain == 0), "rsi"] = 50
    up, down = h.diff(), -l.diff()
    plus = rma(up.where((up > down) & (up > 0), 0), 14)/f.atr
    minus = rma(down.where((down > up) & (down > 0), 0), 14)/f.atr
    f["adx"] = 100*rma((plus-minus).abs()/(plus+minus).replace(0, np.nan), 14)
    f["prior_high"] = h.shift(1).rolling(20).max()
    f["prior_low"] = l.shift(1).rolling(20).min()
    f["high_distance"] = c/f.prior_high-1
    f["low_distance"] = c/f.prior_low-1
    f["breakout"] = (c > f.prior_high).astype(int)-(c < f.prior_low).astype(int)
    f["failed_breakout"] = ((h > f.prior_high) & (c < f.prior_high)).astype(int)-((l < f.prior_low) & (c > f.prior_low)).astype(int)
    f["relative_volume"] = v/v.shift(1).rolling(20).mean().replace(0, np.nan)
    f["volume_average"] = v.rolling(20).mean()
    f["volume_zscore"] = (v-v.rolling(20).mean())/v.rolling(20).std().replace(0, np.nan)
    f["price_volume_corr"] = f.return_1.rolling(20).corr(v.pct_change(fill_method=None))
    f["volume_imbalance_proxy"] = np.sign(c-o)*v/v.rolling(20).mean().replace(0, np.nan)
    sid = b.session_id
    f["session_volume"] = v.groupby(sid).cumsum()
    f["vwap"] = (((h+l+c)/3*v).groupby(sid).cumsum()/f.session_volume.replace(0, np.nan))
    f["vwap_deviation"] = c/f.vwap-1
    sh, sl = h.groupby(sid).cummax(), l.groupby(sid).cummin()
    f["session_high_distance"] = c/sh-1
    f["session_low_distance"] = c/sl-1
    f["range_expansion"] = (sh-sl)/f.atr.replace(0, np.nan)
    previous = b.groupby("session_id", sort=True).agg(high=("high", "max"), low=("low", "min")).shift(1)
    f["previous_session_high"] = sid.map(previous.high)
    f["previous_session_low"] = sid.map(previous.low)
    # Pivots are emitted at confirmation time (two bars later), never at the extremum.
    confirmed_high = h.shift(2).where((h.shift(2) >= h.shift(4)) & (h.shift(2) >= h.shift(3)) & (h.shift(2) > h.shift(1)) & (h.shift(2) > h))
    confirmed_low = l.shift(2).where((l.shift(2) <= l.shift(4)) & (l.shift(2) <= l.shift(3)) & (l.shift(2) < l.shift(1)) & (l.shift(2) < l))
    f["swing_high"] = confirmed_high.ffill()
    f["swing_low"] = confirmed_low.ffill()
    f["higher_high"] = f.swing_high.diff().clip(lower=0)/c
    f["lower_low"] = (-f.swing_low.diff()).clip(lower=0)/c
    f["support_distance"] = c/f.swing_low-1
    f["resistance_distance"] = c/f.swing_high-1
    local = b.timestamp_utc.dt.tz_convert("America/New_York")
    minute = local.dt.hour*60+local.dt.minute
    f["minute_et"] = minute
    f["rth"] = ((minute >= 570) & (minute < 960)).astype(int)
    f["session_bucket"] = np.select([minute < 570, minute < 630, minute < 840, minute < 960], [0, 1, 2, 3], default=4)
    opening = (minute >= 570) & (minute < 600)
    # Cummax sees only opening-range observations already completed, then carries them.
    f["opening_high"] = h.where(opening).groupby(sid).cummax().groupby(sid).ffill().where(minute >= 600)
    f["opening_low"] = l.where(opening).groupby(sid).cummin().groupby(sid).ffill().where(minute >= 600)
    f["opening_location"] = (c-f.opening_low)/(f.opening_high-f.opening_low).replace(0, np.nan)
    f["persistence"] = f.return_1.rolling(20).corr(f.return_1.shift(1))
    # Minute-clock higher-timeframe proxy samples only completed 15-minute closes.
    completed = ((minute+minutes) % 15 == 0)
    f["htf_trend"] = c.where(completed).ffill().pct_change(30, fill_method=None)
    return f.replace([np.inf, -np.inf], np.nan)


def build_features(bars, minutes=1):
    if bars.instrument.nunique() != 1 or bars.timestamp_utc.duplicated().any():
        raise ValueError("Features require one selected contract per timestamp")
    b = bars.reset_index(drop=True)
    # Scheduled session boundaries preserve prior-session structure and EMA/RMA
    # history. Unexpected gaps within a session reset the feature segment.
    boundaries = b.contract.ne(b.contract.shift()) | ((b.timestamp_utc.diff() > pd.Timedelta(minutes=max(5, 2*minutes))) & b.session_id.eq(b.session_id.shift()))
    pieces = []
    for _, g in b.groupby(boundaries.cumsum(), sort=False):
        f = _one(g, minutes)
        f.index = g.index
        pieces.append(f)
    return pd.concat(pieces).sort_index() if pieces else pd.DataFrame()


def cross_market_features(left, right, minutes=1):
    # Exact completed timestamp joins only; unavailable other-market bars stay null.
    a = left[["timestamp_utc", "close"]].copy()
    b = right[["timestamp_utc", "close"]].rename(columns={"close": "other_close"})
    a["available_at"] = left.available_at if "available_at" in left else left.timestamp_utc+pd.Timedelta(minutes=minutes)
    b["available_at"] = right.available_at if "available_at" in right else right.timestamp_utc+pd.Timedelta(minutes=minutes)
    if b.available_at.duplicated().any():
        raise ValueError("Other market requires a selected contract")
    joined = a.merge(b[["available_at", "other_close"]], on="available_at", how="left", validate="one_to_one")
    r1, r2 = joined.close.pct_change(fill_method=None), joined.other_close.pct_change(fill_method=None)
    left_reset = left.timestamp_utc.diff() > pd.Timedelta(minutes=max(5, 2*minutes))
    if "contract" in left:
        left_reset |= left.contract.ne(left.contract.shift())
    right_reset = right.timestamp_utc.diff() > pd.Timedelta(minutes=max(5, 2*minutes))
    if "contract" in right:
        right_reset |= right.contract.ne(right.contract.shift())
    unavailable = pd.DataFrame(dict(available_at=b.available_at, reset=right_reset)).set_index("available_at")["reset"]
    r1 = r1.mask(left_reset.reset_index(drop=True))
    r2 = r2.mask(joined.available_at.map(unavailable).fillna(True).astype(bool))
    return pd.DataFrame(dict(relative_momentum=r1.rolling(5).sum()-r2.rolling(5).sum(),
        cross_correlation=r1.rolling(30).corr(r2), relative_volatility=r1.rolling(30).std()/r2.rolling(30).std(),
        lead_lag=r1.rolling(30).corr(r2.shift(1)), return_divergence=r1-r2,
        trend_agreement=np.sign(r1.rolling(10).sum())*np.sign(r2.rolling(10).sum())))
