"""Rigorous 14-Year Component Research (2010-2023 Train Split Only).

Strict protocol:
- Uses ONLY train split (2010-2023 for NQ/ES). Zero access to validation or test.
- Deducts full micro friction ($2.72/RT).
- Closes all positions intraday (no overnight roll risk).
- Analyzes:
  1. Morning impulse (09:45 - 12:00 ET) vs Afternoon expansion (13:00 - 15:30 ET).
  2. NQ vs ES diversification.
  3. Timeframes: 15m, 30m, 60m.
  4. Robustness: Pre-2020 (2010-2019) PnL AND Post-2020 (2020-2023) PnL.
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
        'atr': atr.to_numpy(dtype=np.float64),
        'trend': trend.to_numpy(dtype=np.float64),
        'breakout_high': breakout_high.to_numpy(dtype=np.float64),
        'breakout_low': breakout_low.to_numpy(dtype=np.float64),
    }

def evaluate_grid():
    candidates = []
    
    # MNQ ($2 mult, $0.25 tick) and MES ($5 mult, $0.25 tick)
    specs = [
        ('NQ', 0.25, 2.0),
        ('ES', 0.25, 5.0),
    ]
    
    timeframes = [
        ('15m', '15 minutes', 15, 930),   # flat at 15:30 (min 930)
        ('30m', '30 minutes', 30, 930),   # flat at 15:30 (min 930)
        ('60m', '60 minutes', 60, 900),   # flat at 15:00 (min 900)
    ]
    
    sessions = [
        ('Morning', 585, 720),     # 09:45 - 12:00 ET
        ('Afternoon', 780, 900),   # 13:00 - 15:00 ET
    ]
    
    lookbacks = [8, 12, 16]
    thresholds = [0.5, 0.75]
    stops = [1.25, 1.5, 2.0]
    targets = [2.5, 3.5, 4.0]
    holds = [6, 8]

    for sym, tick_size, mult in specs:
        print(f"\n==================================================")
        print(f"Scanning 14-year training data for {sym}...")
        print(f"==================================================")
        
        for tf_label, tf_interval, tf_min, flat_min in timeframes:
            print(f"  Loading {tf_interval}...")
            b = load_resampled_train(sym, tf_interval)
            d = apply_early_close(generalized_arrays(b), b)
            loc = b.timestamp_utc.dt.tz_convert('America/New_York')
            dec = (loc.dt.hour * 60 + loc.dt.minute + tf_min).to_numpy()
            is_weekday = loc.dt.weekday.to_numpy() < 5
            years = d['year']
            
            for lb in lookbacks:
                f = compute_features(b, lb, tf_min)
                atr = f['atr']
                trend = f['trend']
                b_high = f['breakout_high']
                b_low = f['breakout_low']
                close = f['close']
                
                for s_name, s_start, s_end in sessions:
                    sess_mask = (dec >= s_start) & (dec < s_end) & is_weekday
                    
                    # 1. Trend Follower
                    for th in thresholds:
                        sig_trend = np.where(sess_mask & (np.abs(trend) >= th), np.sign(trend), 0).astype(np.int8)
                        if np.count_nonzero(sig_trend) < 40:
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
                                        funded_drawdown=2000.0, flat_minute=flat_min, max_gap_minutes=tf_min*2
                                    )
                                    res = me.execute(d, sig_trend, atr, cfg)
                                    tn = res['trade_net']
                                    if len(tn) < 50:
                                        continue
                                        
                                    pnl = res['cash'] - res['cash'][0]
                                    dd = np.maximum.accumulate(pnl) - (res['worst'] - res['cash'][0])
                                    mdd = float(dd.max())
                                    net = float(tn.sum())
                                    exp = float(tn.mean())
                                    
                                    # Strict institutional training criteria:
                                    # Expectancy >= $20, Max DD <= $1,200, Total Net >= $2,500
                                    if exp >= 20.0 and mdd <= 1200.0 and net >= 2500.0:
                                        t_yr = years[res['trade_entry']]
                                        pre_2020 = float(tn[t_yr < 2020].sum()) if np.any(t_yr < 2020) else 0.0
                                        post_2020 = float(tn[t_yr >= 2020].sum()) if np.any(t_yr >= 2020) else 0.0
                                        
                                        # Must be profitable BOTH pre-2020 AND post-2020!
                                        if pre_2020 > 0.0 and post_2020 > 0.0:
                                            candidates.append({
                                                'sym': sym, 'tf': tf_label, 'session': s_name, 'mech': 'Trend',
                                                'lb': lb, 'th': th, 'stop': st, 'tgt': tgt, 'hold': h,
                                                'trades': len(tn), 'net_14y': net, 'exp_14y': exp, 'mdd_14y': mdd,
                                                'pre_2020': pre_2020, 'post_2020': post_2020,
                                                'pre_exp': float(tn[t_yr < 2020].mean()),
                                                'post_exp': float(tn[t_yr >= 2020].mean()),
                                                'calmar_14y': net / mdd if mdd > 0 else 999.0
                                            })
                    
                    # 2. Breakout with Trend Filter
                    for th in [0.0, 0.5]:
                        cond_long = sess_mask & (close > b_high) & (trend >= th)
                        cond_short = sess_mask & (close < b_low) & (trend <= -th)
                        sig_bo = np.zeros(len(close), dtype=np.int8)
                        sig_bo[cond_long] = 1
                        sig_bo[cond_short] = -1
                        
                        if np.count_nonzero(sig_bo) < 40:
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
                                        funded_drawdown=2000.0, flat_minute=flat_min, max_gap_minutes=tf_min*2
                                    )
                                    res = me.execute(d, sig_bo, atr, cfg)
                                    tn = res['trade_net']
                                    if len(tn) < 50:
                                        continue
                                        
                                    pnl = res['cash'] - res['cash'][0]
                                    dd = np.maximum.accumulate(pnl) - (res['worst'] - res['cash'][0])
                                    mdd = float(dd.max())
                                    net = float(tn.sum())
                                    exp = float(tn.mean())
                                    
                                    if exp >= 20.0 and mdd <= 1200.0 and net >= 2500.0:
                                        t_yr = years[res['trade_entry']]
                                        pre_2020 = float(tn[t_yr < 2020].sum()) if np.any(t_yr < 2020) else 0.0
                                        post_2020 = float(tn[t_yr >= 2020].sum()) if np.any(t_yr >= 2020) else 0.0
                                        
                                        if pre_2020 > 0.0 and post_2020 > 0.0:
                                            candidates.append({
                                                'sym': sym, 'tf': tf_label, 'session': s_name, 'mech': f'Breakout_th{th}',
                                                'lb': lb, 'th': th, 'stop': st, 'tgt': tgt, 'hold': h,
                                                'trades': len(tn), 'net_14y': net, 'exp_14y': exp, 'mdd_14y': mdd,
                                                'pre_2020': pre_2020, 'post_2020': post_2020,
                                                'pre_exp': float(tn[t_yr < 2020].mean()),
                                                'post_exp': float(tn[t_yr >= 2020].mean()),
                                                'calmar_14y': net / mdd if mdd > 0 else 999.0
                                            })

    df_cand = pd.DataFrame(candidates)
    out_file = ROOT / 'runs/research_14year_components.parquet'
    df_cand.to_parquet(out_file)
    print(f"\n==================================================")
    print(f"DISCOVERY COMPLETE: {len(df_cand)} ROBUST 14-YEAR CANDIDATES")
    print(f"==================================================")
    
    if not df_cand.empty:
        # Group by Sym, Session, Mech and show best of each
        print("\nTop Candidates by Calmar Ratio (Pre-2020 > 0 AND Post-2020 > 0):")
        cols = ['sym', 'tf', 'session', 'mech', 'lb', 'th', 'stop', 'tgt', 'hold', 'trades', 'net_14y', 'exp_14y', 'mdd_14y', 'pre_2020', 'post_2020', 'calmar_14y']
        top = df_cand.sort_values('calmar_14y', ascending=False)
        print(top[cols].head(25).to_string(index=False))

if __name__ == '__main__':
    evaluate_grid()
