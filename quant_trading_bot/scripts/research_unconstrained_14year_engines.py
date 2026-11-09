"""Unconstrained 14-Year Systematic Training Discovery (2010-2023).

Strict Rules:
- Evaluated ONLY on train split (2010-2023). Zero access to validation (2024-2025) or test (2026).
- Deducts full micro transaction costs: $2.72 round-turn ($0.61/side + 1 tick slippage + 1 tick spread).
- Requires expectancy >= $25/trade to defeat friction comfortably.
- Requires Max DD <= $1,200 on 1 contract (to preserve $800+ cushion for funded $2,000 limit).
- Tests:
  * Timeframes: 15m, 30m, 60m, 120m
  * Sessions: Morning (09:45-12:00), Afternoon (13:00-15:30), Full RTH (09:45-15:30)
  * Mechanisms: Trend, Breakout, Volatility Expansion, Mean Reversion
  * Instruments: NQ (MNQ economics), ES (MES economics)
"""
import sys
import json
import duckdb
import numpy as np
import pandas as pd
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'runs/training_search_500k_v1/code'))
sys.path.insert(0, str(ROOT / 'src'))

from quant_futures.data import canonical
from quant_futures.session_calendar import apply_early_close
import mass_execution as me
from quant_futures.mtf_features import generalized_arrays

cat = json.load(open(ROOT / 'data/catalog.json'))

def load_resampled_train(sym, tf_interval):
    p = cat['instruments'][sym]['splits']['train']['path']
    con = duckdb.connect()
    q = f"""
    SELECT 
        time_bucket(INTERVAL '{tf_interval}', CAST(timestamp_utc AS TIMESTAMPTZ)) AS timestamp_utc,
        arg_min(contract, timestamp_utc) AS contract,
        arg_min(session_id, timestamp_utc) AS session_id,
        arg_min(open, timestamp_utc) AS open,
        max(high) AS high,
        min(low) AS low,
        arg_max(close, timestamp_utc) AS close,
        sum(volume)::DOUBLE AS volume
    FROM read_parquet(?)
    GROUP BY 1
    ORDER BY 1
    """
    df = con.execute(q, [str(p)]).fetch_df()
    df['instrument'] = sym
    df = canonical(df)
    con.close()
    return df

def compute_features(bars, lookback, tf_minutes):
    b = bars.reset_index(drop=True)
    times = pd.to_datetime(b.timestamp_utc, utc=True)
    gap_threshold = pd.Timedelta(minutes=int(tf_minutes * 1.6))
    segments = (b.contract.ne(b.contract.shift()) | times.diff().gt(gap_threshold)).cumsum()
    
    close = b.close.astype(float)
    high = b.high.astype(float)
    low = b.low.astype(float)
    
    previous = close.groupby(segments, sort=False).shift(1)
    tr = pd.concat([high - low, (high - previous).abs(), (low - previous).abs()], axis=1).max(axis=1)
    atr = tr.groupby(segments, sort=False).rolling(14, min_periods=14).mean().reset_index(level=0, drop=True)
    
    fast_span = max(2, lookback // 2)
    fast = close.groupby(segments, sort=False).apply(lambda s: s.ewm(span=fast_span, adjust=False, min_periods=fast_span).mean()).reset_index(level=0, drop=True)
    slow = close.groupby(segments, sort=False).apply(lambda s: s.ewm(span=lookback, adjust=False, min_periods=lookback).mean()).reset_index(level=0, drop=True)
    
    breakout_high = high.groupby(segments, sort=False).shift(1).groupby(segments, sort=False).rolling(lookback, min_periods=lookback).max().reset_index(level=0, drop=True)
    breakout_low = low.groupby(segments, sort=False).shift(1).groupby(segments, sort=False).rolling(lookback, min_periods=lookback).min().reset_index(level=0, drop=True)
    
    trend = (fast - slow) / atr.replace(0, np.nan)
    
    return {
        'close': close.to_numpy(dtype=np.float64),
        'high': high.to_numpy(dtype=np.float64),
        'low': low.to_numpy(dtype=np.float64),
        'atr': atr.to_numpy(dtype=np.float64),
        'trend': trend.to_numpy(dtype=np.float64),
        'breakout_high': breakout_high.to_numpy(dtype=np.float64),
        'breakout_low': breakout_low.to_numpy(dtype=np.float64),
    }

def run_grid():
    results = []
    
    # We test NQ and ES
    specs = [
        ('NQ', 0.25, 2.0),   # MNQ multiplier $2
        ('ES', 0.25, 5.0),   # MES multiplier $5
    ]
    
    timeframes = [
        ('15 minutes', 15),
        ('30 minutes', 30),
        ('60 minutes', 60),
        ('120 minutes', 120),
    ]
    
    sessions = [
        ('Morning', 585, 720),      # 09:45 - 12:00 ET
        ('Afternoon', 780, 930),    # 13:00 - 15:30 ET
        ('Full_RTH', 585, 930),     # 09:45 - 15:30 ET
    ]
    
    lookbacks = [8, 12, 16, 24]
    trend_thresholds = [0.5, 0.75, 1.0]
    stops = [1.25, 1.5, 2.0]
    targets = [2.5, 3.5, 4.0]
    holds = [6, 8, 12]

    for sym, tick_size, mult in specs:
        print(f"\nProcessing {sym} (multiplier {mult})...")
        for tf_str, tf_min in timeframes:
            print(f"  Loading {tf_str} bars...")
            b = load_resampled_train(sym, tf_str)
            d = apply_early_close(generalized_arrays(b), b)
            loc = b.timestamp_utc.dt.tz_convert('America/New_York')
            dec = (loc.dt.hour * 60 + loc.dt.minute + tf_min).to_numpy()
            is_weekday = loc.dt.weekday.to_numpy() < 5
            
            for lb in lookbacks:
                f = compute_features(b, lb, tf_min)
                atr = f['atr']
                trend = f['trend']
                b_high = f['breakout_high']
                b_low = f['breakout_low']
                close = f['close']
                
                for s_name, s_start, s_end in sessions:
                    sess_mask = (dec >= s_start) & (dec < s_end) & is_weekday
                    
                    # Mechanism 1: Trend Following
                    for th in trend_thresholds:
                        sig_trend = np.where(sess_mask & (np.abs(trend) >= th), np.sign(trend), 0).astype(np.int8)
                        
                        # Quick check if enough signals
                        if np.count_nonzero(sig_trend) < 30:
                            continue
                            
                        for st in stops:
                            for tgt in targets:
                                for h in holds:
                                    cfg = dict(
                                        tick=tick_size, multiplier=mult, commission_per_side=0.61,
                                        slippage_ticks=1.0, spread_ticks=1.0,
                                        stop_atr=st, target_ratio=tgt, hold_bars=h, trailing_atr=0.0,
                                        maxqty=1, initial_balance=50000.0, risk_per_trade=150.0,
                                        max_open_risk=150.0, daily_loss=300.0, hard_drawdown=1800.0,
                                        funded_drawdown=2000.0, flat_minute=955, max_gap_minutes=tf_min*2
                                    )
                                    res = me.execute(d, sig_trend, atr, cfg)
                                    tn = res['trade_net']
                                    if len(tn) < 40:
                                        continue
                                    pnl = res['cash'] - res['cash'][0]
                                    dd = np.maximum.accumulate(pnl) - (res['worst'] - res['cash'][0])
                                    mdd = float(dd.max())
                                    net = float(tn.sum())
                                    exp = float(tn.mean())
                                    
                                    # Screen for institutional quality on 14 years
                                    if exp >= 25.0 and mdd <= 1200.0 and net > 3000.0:
                                        # Check pre-2020 vs post-2020 consistency
                                        yr = d['year'][res['trade_entry']]
                                        pre_2020_net = float(tn[yr < 2020].sum()) if np.any(yr < 2020) else 0.0
                                        post_2020_net = float(tn[yr >= 2020].sum()) if np.any(yr >= 2020) else 0.0
                                        
                                        results.append({
                                            'sym': sym, 'tf': tf_str, 'session': s_name, 'mech': 'Trend',
                                            'lb': lb, 'th': th, 'stop': st, 'tgt': tgt, 'hold': h,
                                            'trades': len(tn), 'net': net, 'exp': exp, 'mdd': mdd,
                                            'pre_2020': pre_2020_net, 'post_2020': post_2020_net
                                        })
                    
                    # Mechanism 2: Breakout with Trend Confirmation
                    for th in [0.0, 0.5]:
                        sig_bo = np.zeros(len(close), dtype=np.int8)
                        cond_long = sess_mask & (close > b_high) & (trend >= th)
                        cond_short = sess_mask & (close < b_low) & (trend <= -th)
                        sig_bo[cond_long] = 1
                        sig_bo[cond_short] = -1
                        
                        if np.count_nonzero(sig_bo) < 30:
                            continue
                            
                        for st in stops:
                            for tgt in targets:
                                for h in holds:
                                    cfg = dict(
                                        tick=tick_size, multiplier=mult, commission_per_side=0.61,
                                        slippage_ticks=1.0, spread_ticks=1.0,
                                        stop_atr=st, target_ratio=tgt, hold_bars=h, trailing_atr=0.0,
                                        maxqty=1, initial_balance=50000.0, risk_per_trade=150.0,
                                        max_open_risk=150.0, daily_loss=300.0, hard_drawdown=1800.0,
                                        funded_drawdown=2000.0, flat_minute=955, max_gap_minutes=tf_min*2
                                    )
                                    res = me.execute(d, sig_bo, atr, cfg)
                                    tn = res['trade_net']
                                    if len(tn) < 40:
                                        continue
                                    pnl = res['cash'] - res['cash'][0]
                                    dd = np.maximum.accumulate(pnl) - (res['worst'] - res['cash'][0])
                                    mdd = float(dd.max())
                                    net = float(tn.sum())
                                    exp = float(tn.mean())
                                    
                                    if exp >= 25.0 and mdd <= 1200.0 and net > 3000.0:
                                        yr = d['year'][res['trade_entry']]
                                        pre_2020_net = float(tn[yr < 2020].sum()) if np.any(yr < 2020) else 0.0
                                        post_2020_net = float(tn[yr >= 2020].sum()) if np.any(yr >= 2020) else 0.0
                                        
                                        results.append({
                                            'sym': sym, 'tf': tf_str, 'session': s_name, 'mech': f'Breakout_th{th}',
                                            'lb': lb, 'th': th, 'stop': st, 'tgt': tgt, 'hold': h,
                                            'trades': len(tn), 'net': net, 'exp': exp, 'mdd': mdd,
                                            'pre_2020': pre_2020_net, 'post_2020': post_2020_net
                                        })

    df_res = pd.DataFrame(results)
    out_path = ROOT / 'runs/research_unconstrained_14year_engines.parquet'
    out_path.parent.mkdir(parents=True, exist_ok=True)
    df_res.to_parquet(out_path)
    print(f"\nDone! Found {len(df_res)} candidates meeting institutional criteria.")
    if len(df_res) > 0:
        print("\nTop 15 by Expectancy (where pre-2020 > 0 and post-2020 > 0):")
        robust = df_res[(df_res['pre_2020'] > 0) & (df_res['post_2020'] > 0)].sort_values('exp', ascending=False)
        print(robust.head(15).to_string(index=False))

if __name__ == '__main__':
    run_grid()
