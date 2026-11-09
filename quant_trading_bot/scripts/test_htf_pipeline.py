import json
from pathlib import Path
import sys
import duckdb
import numpy as np
import pandas as pd
import ast

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'runs/training_search_500k_v1/code'))
sys.path.insert(0, str(ROOT / 'src'))

from quant_futures.data import canonical
from quant_futures.session_calendar import apply_early_close
import mass_execution as me
import mass_metrics as mm

CATALOG = json.load(open(ROOT / 'data/catalog.json'))

def load_resampled_bars(sym, split, tf_interval):
    p = CATALOG['instruments'][sym]['splits'][split]['path']
    con = duckdb.connect()
    query = f"""
    SELECT time_bucket(INTERVAL '{tf_interval}', CAST(timestamp_utc AS TIMESTAMPTZ)) AS timestamp_utc,
           instrument, contract, session_id,
           arg_min(open, timestamp_utc) AS open,
           max(high) AS high,
           min(low) AS low,
           arg_max(close, timestamp_utc) AS close,
           sum(volume)::DOUBLE AS volume
    FROM read_parquet(?)
    WHERE timestamp_utc >= '2020-01-01'
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

print("Running test execution on 30m MNQ bars...")
bars_30m = load_resampled_bars('MNQ', 'train', '30 minutes')
f_30m = compute_htf_features(bars_30m, 6, 30)
data = apply_early_close(generalized_arrays(bars_30m), bars_30m)

# Signal rule: Trend on 30m
raw_sig = np.where(np.abs(f_30m['trend']) >= 1.0, np.sign(f_30m['trend']), 0).astype(np.int8)

local = bars_30m.timestamp_utc.dt.tz_convert('America/New_York')
decision = (local.dt.hour * 60 + local.dt.minute + 30).to_numpy()
weekdays = local.dt.weekday.to_numpy() < 5
mask = (decision >= 585) & (decision < 945) & weekdays
sig = np.where(mask, raw_sig, 0).astype(np.int8)

ecfg = dict(
    initial_balance=50000.0,
    tick=0.25,
    multiplier=2.0,
    commission_per_side=0.61,
    exchange_per_side=0.0,
    regulatory_per_side=0.0,
    spread_ticks=1,
    slippage_ticks=1,
    impact_ticks=0.0,
    factor=1,
    maxqty=1,
    risk_per_trade=150.0,
    max_open_risk=150.0,
    daily_loss=300.0,
    hard_drawdown=1800.0,
    stop_atr=1.5,
    target_ratio=3.0,
    hold_bars=8,
    entry_start=585 - 15,
    entry_end=945 - 30,
    flat_minute=955,
    max_gap_minutes=60,
    participation=0.01,
    trailing_atr=0.0,
    max_consecutive_losses=5,
    funded_drawdown=2000.0,
    funded_cap=50100.0,
)

res = me.execute(data, sig, f_30m['atr'], ecfg)
sm = mm.summarize_execution(res, data)
print(f"Sample 30m MNQ Trend: Net = ${sm['net_pnl']:,.2f} | Trades = {sm['trades']} | Expectancy = ${sm['net_pnl']/sm['trades']:.2f}/trade | DD = ${sm['intrabar_drawdown']:.2f} | PF = {sm['profit_factor']:.2f}")
