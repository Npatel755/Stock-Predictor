import json
from pathlib import Path
import duckdb
import numpy as np
import pandas as pd
from quant_futures.data import canonical

CATALOG_PATH = Path(__file__).resolve().parents[2] / 'data/catalog.json'

def load_resampled_bars(sym, split, tf_interval, start_date='2020-01-01'):
    catalog = json.load(open(CATALOG_PATH))
    p = catalog['instruments'][sym]['splits'][split]['path']
    con = duckdb.connect()
    where_clause = f"WHERE timestamp_utc >= '{start_date}'" if start_date else ""
    query = f"""
    SELECT time_bucket(INTERVAL '{tf_interval}', CAST(timestamp_utc AS TIMESTAMPTZ)) AS timestamp_utc,
           instrument, contract, session_id,
           arg_min(open, timestamp_utc) AS open,
           max(high) AS high,
           min(low) AS low,
           arg_max(close, timestamp_utc) AS close,
           sum(volume)::DOUBLE AS volume
    FROM read_parquet(?)
    {where_clause}
    GROUP BY 1, instrument, contract, session_id
    ORDER BY 1
    """
    try:
        df = canonical(con.execute(query, [str(p)]).fetch_df())
    finally:
        con.close()
    return df

def generalized_arrays(bars):
    local = bars.timestamp_utc.dt.tz_convert('America/New_York')
    dates = pd.to_datetime(bars.session_id)
    return dict(
        timestamp=pd.DatetimeIndex(bars.timestamp_utc).as_unit('ns').asi8,
        session=pd.factorize(bars.session_id, sort=False)[0].astype(np.int64),
        minute=(local.dt.hour * 60 + local.dt.minute).to_numpy(dtype=np.int64),
        month=(dates.dt.year * 100 + dates.dt.month).to_numpy(dtype=np.int64),
        year=dates.dt.year.to_numpy(dtype=np.int64),
        contract=pd.factorize(bars.contract, sort=False)[0].astype(np.int64),
        **{name: bars[name].to_numpy(dtype=np.float64) for name in ('open', 'high', 'low', 'close', 'volume')}
    )

def _ratio(numerator, denominator):
    return numerator / denominator.replace(0, np.nan)

def compute_htf_features(bars, lookback, tf_minutes):
    b = bars.reset_index(drop=True)
    times = pd.to_datetime(b.timestamp_utc, utc=True)
    gap_threshold = pd.Timedelta(minutes=int(tf_minutes * 1.6))
    segments = (b.contract.ne(b.contract.shift()) | times.diff().gt(gap_threshold)).cumsum()
    
    close = b.close.astype(float)
    high = b.high.astype(float)
    low = b.low.astype(float)
    volume = b.volume.astype(float)
    
    previous = close.groupby(segments, sort=False).shift(1)
    tr = pd.concat([high - low, (high - previous).abs(), (low - previous).abs()], axis=1).max(axis=1)
    atr = tr.groupby(segments, sort=False).rolling(14, min_periods=14).mean().reset_index(level=0, drop=True)
    
    fast_span = max(2, lookback // 2)
    fast = close.groupby(segments, sort=False).apply(lambda s: s.ewm(span=fast_span, adjust=False, min_periods=fast_span).mean()).reset_index(level=0, drop=True)
    slow = close.groupby(segments, sort=False).apply(lambda s: s.ewm(span=lookback, adjust=False, min_periods=lookback).mean()).reset_index(level=0, drop=True)
    
    returns = close.groupby(segments, sort=False).pct_change(fill_method=None)
    short_span = max(2, lookback // 4)
    
    breakout_high = high.groupby(segments, sort=False).shift(1).groupby(segments, sort=False).rolling(lookback, min_periods=lookback).max().reset_index(level=0, drop=True)
    breakout_low = low.groupby(segments, sort=False).shift(1).groupby(segments, sort=False).rolling(lookback, min_periods=lookback).min().reset_index(level=0, drop=True)
    
    momentum = _ratio(close - close.groupby(segments, sort=False).shift(lookback), atr * np.sqrt(lookback))
    trend = _ratio(fast - slow, atr)
    zscore = _ratio(close - close.groupby(segments, sort=False).rolling(lookback, min_periods=lookback).mean().reset_index(level=0, drop=True),
                    close.groupby(segments, sort=False).rolling(lookback, min_periods=lookback).std(ddof=0).reset_index(level=0, drop=True))
    
    efficiency = _ratio((close - close.groupby(segments, sort=False).shift(lookback)).abs(),
                        close.groupby(segments, sort=False).diff().abs().groupby(segments, sort=False).rolling(lookback, min_periods=lookback).sum().reset_index(level=0, drop=True))
    
    vol_ratio = _ratio(returns.groupby(segments, sort=False).rolling(short_span, min_periods=short_span).std(ddof=0).reset_index(level=0, drop=True),
                       returns.groupby(segments, sort=False).rolling(lookback, min_periods=lookback).std(ddof=0).reset_index(level=0, drop=True))
    
    return {
        'close': close.to_numpy(dtype=np.float64),
        'atr': atr.to_numpy(dtype=np.float64),
        'trend': trend.to_numpy(dtype=np.float64),
        'momentum': momentum.to_numpy(dtype=np.float64),
        'zscore': zscore.to_numpy(dtype=np.float64),
        'breakout_high': breakout_high.to_numpy(dtype=np.float64),
        'breakout_low': breakout_low.to_numpy(dtype=np.float64),
        'efficiency': efficiency.to_numpy(dtype=np.float64),
        'vol_ratio': vol_ratio.to_numpy(dtype=np.float64),
    }
