import duckdb
import numpy as np
import pandas as pd
from pathlib import Path
import json

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
        from quant_futures.data import canonical
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

def compute_5m_indicators(bars_5m, bars_60m):
    """
    Computes causal 5m indicators and joins causal 60m trend.
    Vectorized and C-accelerated for maximum speed.
    """
    b = bars_5m.reset_index(drop=True).copy()
    times = pd.to_datetime(b.timestamp_utc, utc=True)
    
    close = b.close.astype(float)
    high = b.high.astype(float)
    low = b.low.astype(float)
    volume = b.volume.astype(float)
    
    # 5m ATR
    previous = close.shift(1)
    tr = np.maximum(high - low, np.maximum((high - previous).abs(), (low - previous).abs()))
    atr = tr.rolling(14, min_periods=14).mean()
    
    # 5m Volume MA
    vol_ma = volume.rolling(20, min_periods=20).mean()
    vol_ratio = _ratio(volume, vol_ma)
    
    # 60m trend for MTF alignment
    b60 = bars_60m.reset_index(drop=True).copy()
    times60 = pd.to_datetime(b60.timestamp_utc, utc=True)
    c60 = b60.close.astype(float)
    h60 = b60.high.astype(float)
    l60 = b60.low.astype(float)
    p60 = c60.shift(1)
    tr60 = np.maximum(h60 - l60, np.maximum((h60 - p60).abs(), (l60 - p60).abs()))
    atr60 = tr60.rolling(14, min_periods=14).mean()
    fast60 = c60.ewm(span=6, adjust=False, min_periods=6).mean()
    slow60 = c60.ewm(span=12, adjust=False, min_periods=12).mean()
    trend60 = _ratio(fast60 - slow60, atr60)
    
    # Causal alignment via merge_asof on close_time
    b['close_time'] = times + pd.Timedelta(minutes=5)
    b60['close_time'] = times60 + pd.Timedelta(minutes=60)
    b60['trend60'] = trend60
    
    merged = pd.merge_asof(b[['close_time']], b60[['close_time', 'trend60']], on='close_time', direction='backward')
    aligned_trend60 = merged['trend60'].fillna(0.0).to_numpy(dtype=np.float64)
    
    # Session timing masks in Eastern Time
    local = b.timestamp_utc.dt.tz_convert('America/New_York')
    close_min = local.dt.hour * 60 + local.dt.minute + 5
    weekdays = local.dt.weekday < 5
    
    # Opening Range Breakout (ORB) features: 09:30 to 10:00 ET
    # Minute 570 is 09:30, minute 600 is 10:00
    is_orb_bar = (close_min > 570) & (close_min <= 600) & weekdays
    orb_df = pd.DataFrame({'session': b.session_id, 'high': high.where(is_orb_bar), 'low': low.where(is_orb_bar)}).groupby('session').agg({'high': 'max', 'low': 'min'})
    orb_high = b.session_id.map(orb_df['high']).fillna(np.inf)
    orb_low = b.session_id.map(orb_df['low']).fillna(-np.inf)
    
    features_by_lb = {}
    returns = close.pct_change(fill_method=None)
    for lb in [12, 18, 24, 36, 48]:
        fast_span = max(2, lb // 2)
        fast = close.ewm(span=fast_span, adjust=False, min_periods=fast_span).mean()
        slow = close.ewm(span=lb, adjust=False, min_periods=lb).mean()
        
        bh = high.shift(1).rolling(lb, min_periods=lb).max()
        bl = low.shift(1).rolling(lb, min_periods=lb).min()
        
        mom = _ratio(close - close.shift(lb), atr * np.sqrt(lb))
        trend = _ratio(fast - slow, atr)
        
        short_span = max(2, lb // 4)
        vol_comp = _ratio(returns.rolling(short_span, min_periods=short_span).std(ddof=0),
                          returns.rolling(lb, min_periods=lb).std(ddof=0))
        
        features_by_lb[lb] = {
            'breakout_high': bh.to_numpy(dtype=np.float64),
            'breakout_low': bl.to_numpy(dtype=np.float64),
            'trend': trend.to_numpy(dtype=np.float64),
            'momentum': mom.to_numpy(dtype=np.float64),
            'vol_comp': vol_comp.to_numpy(dtype=np.float64),
        }
        
    return {
        'close': close.to_numpy(dtype=np.float64),
        'high': high.to_numpy(dtype=np.float64),
        'low': low.to_numpy(dtype=np.float64),
        'atr': atr.to_numpy(dtype=np.float64),
        'vol_ratio': vol_ratio.to_numpy(dtype=np.float64),
        'trend60': aligned_trend60,
        'orb_high': orb_high.to_numpy(dtype=np.float64),
        'orb_low': orb_low.to_numpy(dtype=np.float64),
        'close_min': close_min.to_numpy(dtype=np.int64),
        'weekdays': weekdays.to_numpy(dtype=bool),
        'features_by_lb': features_by_lb
    }
