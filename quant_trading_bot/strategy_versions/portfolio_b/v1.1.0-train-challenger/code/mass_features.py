"""Causal, unfitted indicators for complete 15-minute raw-contract bars."""
import numpy as np
import pandas as pd


BAR_MINUTES = 15


def _ratio(numerator, denominator):
    return numerator/denominator.replace(0, np.nan)


def features_reference(bars, lookback):
    """Return aligned NumPy arrays without inspecting any future statistic.

    Rolling indicators reset at raw-contract changes or gaps >20 minutes.
    Session VWAP additionally resets at the exchange session boundary.  Opening
    ranges require exact complete 15-minute buckets beginning at 09:30 ET;
    their highs/lows are published only at the completed opening window's end.
    Unsupported sub-bar opening windows remain unavailable rather than guessed.
    """
    if isinstance(lookback, bool) or int(lookback) != lookback or lookback < 2:
        raise ValueError("Lookback must be an integer of at least two")
    lookback = int(lookback)
    b = bars.reset_index(drop=True)
    times = pd.to_datetime(b.timestamp_utc, utc=True)
    if not times.is_monotonic_increasing or times.duplicated().any():
        raise ValueError("Chronological unique bar timestamps required")
    if b.instrument.nunique() != 1:
        raise ValueError("One instrument per feature frame required")
    n = len(b)
    names = ("atr", "trend", "momentum", "zscore", "breakout_high", "breakout_low",
             "vwap_deviation", "efficiency", "vol_ratio", "volume_ratio", "htf",
             "opening_high", "opening_low")
    out = {name: np.full(n, np.nan, dtype=np.float64) for name in names}
    out["close"] = b.close.to_numpy(dtype=np.float64, copy=True)
    out["opening_ready"] = np.zeros(n, dtype=bool)
    if not n:
        return out
    breaks = b.contract.ne(b.contract.shift()) | times.diff().gt(pd.Timedelta(minutes=20))
    segments = breaks.cumsum()
    local = times.dt.tz_convert("America/New_York")
    clock = (local.dt.hour*60+local.dt.minute).to_numpy()
    for _, ids_ in b.groupby(segments, sort=False).indices.items():
        ids = np.asarray(ids_)
        part = b.iloc[ids].reset_index(drop=True)
        close = part.close.astype(float)
        previous = close.shift()
        tr = pd.concat((part.high-part.low, (part.high-previous).abs(), (part.low-previous).abs()), axis=1).max(axis=1)
        atr = tr.rolling(14, min_periods=14).mean()
        fast = close.ewm(span=max(2, lookback//2), adjust=False, min_periods=max(2, lookback//2)).mean()
        slow = close.ewm(span=lookback, adjust=False, min_periods=lookback).mean()
        returns = close.pct_change(fill_method=None)
        short = max(2, lookback//4)
        values = dict(
            atr=atr,
            trend=_ratio(fast-slow, atr),
            momentum=_ratio(close-close.shift(lookback), atr*np.sqrt(lookback)),
            zscore=_ratio(close-close.rolling(lookback).mean(), close.rolling(lookback).std(ddof=0)),
            breakout_high=part.high.shift().rolling(lookback).max(),
            breakout_low=part.low.shift().rolling(lookback).min(),
            efficiency=_ratio((close-close.shift(lookback)).abs(), close.diff().abs().rolling(lookback).sum()),
            vol_ratio=_ratio(returns.rolling(short).std(ddof=0), returns.rolling(lookback).std(ddof=0)),
            volume_ratio=_ratio(part.volume.astype(float), part.volume.shift().rolling(lookback).mean()),
            htf=np.sign(close-close.shift(lookback*2)),
        )
        for name, value in values.items():
            out[name][ids] = np.asarray(value, dtype=np.float64)
        typical = (part.high+part.low+part.close)/3
        volume = part.volume.astype(float)
        session = part.session_id
        cumulative = (typical*volume).groupby(session, sort=False).cumsum()
        cumulative_volume = volume.groupby(session, sort=False).cumsum()
        vwap = _ratio(cumulative, cumulative_volume)
        out["vwap_deviation"][ids] = _ratio(close-vwap, atr).to_numpy(dtype=float)
    # The requested opening window must be resolvable from source bars.
    if lookback % BAR_MINUTES == 0:
        for _, ids_ in b.groupby("session_id", sort=False).indices.items():
            ids = np.asarray(ids_)
            opening = ids[(clock[ids] >= 570) & (clock[ids] < 570+lookback)]
            expected = np.arange(570, 570+lookback, BAR_MINUTES)
            if (len(opening) != len(expected) or not np.array_equal(clock[opening], expected)
                    or b.contract.iloc[opening].nunique() != 1 or segments.iloc[opening].nunique() != 1):
                continue
            if len(opening) > 1 and not times.iloc[opening].diff().iloc[1:].eq(pd.Timedelta(minutes=BAR_MINUTES)).all():
                continue
            # Timestamp is bar-open. End 09:45 becomes available at that
            # boundary and is actionable at the following tradable open.
            ready = ids[(clock[ids]+BAR_MINUTES >= 570+lookback)
                        & (times.iloc[ids].to_numpy() >= times.iloc[opening[-1]])
                        & (segments.iloc[ids].to_numpy() == segments.iloc[opening[-1]])]
            high = float(b.high.iloc[opening].max())
            low = float(b.low.iloc[opening].min())
            out["opening_high"][ready] = high
            out["opening_low"][ready] = low
            out["opening_ready"][ready] = True
    for name in names:
        out[name][~np.isfinite(out[name])] = np.nan
    return out


def features(bars, lookback):
    """Same causal formulas as the reference, using grouped rolling kernels."""
    if isinstance(lookback,bool) or int(lookback)!=lookback or lookback<2:
        raise ValueError('Lookback must be an integer of at least two')
    lookback=int(lookback)
    b=bars.reset_index(drop=True)
    times=pd.to_datetime(b.timestamp_utc,utc=True)
    if not times.is_monotonic_increasing or times.duplicated().any():
        raise ValueError('Chronological unique bar timestamps required')
    if b.instrument.nunique()!=1:
        raise ValueError('One instrument per feature frame required')
    if not len(b):
        return features_reference(b,lookback)
    segments=(b.contract.ne(b.contract.shift())|times.diff().gt(pd.Timedelta(minutes=20))).cumsum()
    close=b.close.astype(float)
    def shift(s,n=1): return s.groupby(segments,sort=False).shift(n)
    def rolling(s,n,kind):
        group=s.groupby(segments,sort=False).rolling(n,min_periods=n)
        result=getattr(group,kind)(ddof=0) if kind=='std' else getattr(group,kind)()
        return result.droplevel(0).sort_index()
    def ema(n):
        return close.groupby(segments,sort=False).ewm(span=n,adjust=False,min_periods=n).mean().droplevel(0).sort_index()
    previous=shift(close)
    tr=pd.concat((b.high-b.low,(b.high-previous).abs(),(b.low-previous).abs()),axis=1).max(axis=1)
    atr=rolling(tr,14,'mean')
    returns=close/previous-1
    cumulative=(b.high+b.low+b.close)/3*b.volume
    keys=[segments,b.session_id]
    vwap=_ratio(cumulative.groupby(keys,sort=False).cumsum(),b.volume.groupby(keys,sort=False).cumsum())
    values=dict(atr=atr,trend=_ratio(ema(max(2,lookback//2))-ema(lookback),atr),
        momentum=_ratio(close-shift(close,lookback),atr*np.sqrt(lookback)),
        zscore=_ratio(close-rolling(close,lookback,'mean'),rolling(close,lookback,'std')),
        breakout_high=rolling(shift(b.high),lookback,'max'),breakout_low=rolling(shift(b.low),lookback,'min'),
        efficiency=_ratio((close-shift(close,lookback)).abs(),rolling((close-previous).abs(),lookback,'sum')),
        vol_ratio=_ratio(rolling(returns,max(2,lookback//4),'std'),rolling(returns,lookback,'std')),
        volume_ratio=_ratio(b.volume.astype(float),rolling(shift(b.volume),lookback,'mean')),
        htf=np.sign(close-shift(close,lookback*2)),vwap_deviation=_ratio(close-vwap,atr),close=close)
    out={name:np.array(value,dtype=float,copy=True) for name,value in values.items()}
    n=len(b)
    out.update(opening_high=np.full(n,np.nan),opening_low=np.full(n,np.nan),opening_ready=np.zeros(n,dtype=bool))
    if lookback%BAR_MINUTES==0:
        local=times.dt.tz_convert('America/New_York')
        clock=(local.dt.hour*60+local.dt.minute).to_numpy()
        expected=np.arange(570,570+lookback,BAR_MINUTES)
        for ids_ in b.groupby('session_id',sort=False).indices.values():
            ids=np.asarray(ids_)
            opening=ids[(clock[ids]>=570)&(clock[ids]<570+lookback)]
            if len(opening)!=len(expected) or not np.array_equal(clock[opening],expected): continue
            if b.contract.iloc[opening].nunique()!=1 or segments.iloc[opening].nunique()!=1: continue
            if len(opening)>1 and not times.iloc[opening].diff().iloc[1:].eq(pd.Timedelta(minutes=BAR_MINUTES)).all(): continue
            ready=ids[(clock[ids]+BAR_MINUTES>=570+lookback)&(times.iloc[ids].to_numpy()>=times.iloc[opening[-1]])&(segments.iloc[ids].to_numpy()==segments.iloc[opening[-1]])]
            out['opening_high'][ready]=float(b.high.iloc[opening].max())
            out['opening_low'][ready]=float(b.low.iloc[opening].min())
            out['opening_ready'][ready]=True
    for name in out:
        if name!='opening_ready': out[name][~np.isfinite(out[name])]=np.nan
    return out


def signal_for(configuration, f):
    """Desired direction at completed close; execution/session gates are external."""
    family = configuration["family"]
    threshold = float(configuration["threshold"])
    close, atr = f["close"], f["atr"]
    if family == "trend":
        value, eligible = f["trend"], np.abs(f["trend"]) >= threshold
    elif family == "momentum":
        value, eligible = f["momentum"], np.abs(f["momentum"]) >= threshold
    elif family == "mean_reversion":
        value, eligible = -f["zscore"], np.abs(f["zscore"]) >= threshold
    elif family == "breakout":
        value = np.where(close > f["breakout_high"]+threshold*atr, 1.,
                         np.where(close < f["breakout_low"]-threshold*atr, -1., 0.))
        eligible = np.isfinite(atr) & np.isfinite(f["breakout_high"]) & np.isfinite(f["breakout_low"])
    elif family == "vwap":
        value = -f["vwap_deviation"]
        # The cumulative session benchmark has no rolling lookback itself.
        # A fixed momentum cap uses the configured horizon as an active
        # confirmation rule and avoids fading a strong directional impulse.
        eligible = (np.abs(f["vwap_deviation"]) >= threshold) & (np.abs(f["momentum"]) <= 1.)
    elif family == "opening_range":
        if configuration["lookback"] % BAR_MINUTES:
            raise ValueError("Opening lookback must be an exact 15-minute window")
        value = np.where(close > f["opening_high"]+threshold*atr, 1.,
                         np.where(close < f["opening_low"]-threshold*atr, -1., 0.))
        eligible = f["opening_ready"] & np.isfinite(atr)
    elif family == "regime":
        value = f["momentum"]
        eligible = (f["efficiency"] > threshold/3) & (f["vol_ratio"] < 1.5)
    elif family == "volatility":
        value, eligible = f["momentum"], f["vol_ratio"] >= threshold
    elif family == "volume":
        value, eligible = f["momentum"], f["volume_ratio"] >= threshold
    elif family == "hybrid":
        value = f["trend"]
        eligible = (np.sign(value) == f["htf"]) & (np.abs(f["momentum"]) >= threshold)
    else:
        raise ValueError("Unknown mass research family: "+family)
    return np.where(np.isfinite(value) & eligible, np.sign(value), 0).astype(np.int8)
