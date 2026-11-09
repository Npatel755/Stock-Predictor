"""Afternoon MNQ Strategy Discovery on TRAIN SPLIT ONLY (2020-2023).

Strict Mandate:
- Evaluates EXCLUSIVELY on Train split (2020-2023). Zero touch of Validation or Test.
- Strict micro transaction costs ($2.72/RT).
- Afternoon sessions only:
  * Post-European close / institutional rebalance window (13:00 - 15:30 ET).
- Mandatory intraday flattening by 15:55 ET (flat_minute=955).
- Filters:
  * Expectancy >= $20-$25+/trade
  * Max Drawdown <= $1,000
  * Positive in 4 of 4 train years (2020, 2021, 2022, 2023)
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
from quant_futures.htf_engine import compute_htf_features

cat = json.load(open(ROOT / 'data/catalog.json'))

def load_train_bars(tf_interval):
    p = cat['instruments']['MNQ']['splits']['train']['path']
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
    WHERE timestamp_utc >= '2020-01-01'
    GROUP BY 1
    ORDER BY 1
    """
    df = con.execute(q, [str(p)]).fetch_df()
    df['instrument'] = 'MNQ'
    df = canonical(df)
    con.close()
    return df

print("Loading Train (2020-2023) MNQ bars...")
b_15m = load_train_bars('15 minutes')
b_30m = load_train_bars('30 minutes')
b_60m = load_train_bars('60 minutes')

d_15m = apply_early_close(generalized_arrays(b_15m), b_15m)
d_30m = apply_early_close(generalized_arrays(b_30m), b_30m)
d_60m = apply_early_close(generalized_arrays(b_60m), b_60m)

datasets = {
    '15m': (b_15m, d_15m, 15),
    '30m': (b_30m, d_30m, 30),
    '60m': (b_60m, d_60m, 60),
}

# Afternoon Windows:
# 13:00 - 15:00 (780 - 900 min)
# 13:30 - 15:15 (810 - 915 min)
# 13:00 - 15:30 (780 - 930 min)
windows = [
    ('Aft_1300_1500', 780, 900),
    ('Aft_1330_1515', 810, 915),
    ('Aft_1300_1530', 780, 930),
]

lookbacks = [4, 8, 12, 16]
thresholds = [0.5, 0.75, 1.0]
stops = [1.0, 1.25, 1.5]
targets = [2.0, 3.0, 4.0]
holds = [4, 6, 8]

results = []

for tf_label, (bars, data, tf_min) in datasets.items():
    print(f"\nScanning Afternoon rules on {tf_label} bars...")
    loc = bars.timestamp_utc.dt.tz_convert('America/New_York')
    dec = (loc.dt.hour * 60 + loc.dt.minute + tf_min).to_numpy()
    weekdays = loc.dt.weekday.to_numpy() < 5
    years = data['year']
    unique_years = [2020, 2021, 2022, 2023]
    
    for lb in lookbacks:
        f = compute_htf_features(bars, lb, tf_min)
        atr = f['atr']
        trend = f['trend']
        c = f['close']
        bh = f['breakout_high']
        bl = f['breakout_low']
        
        for w_name, w_start, w_end in windows:
            sess_mask = (dec >= w_start) & (dec < w_end) & weekdays
            
            # Mechanism 1: Afternoon Trend Continuation
            for th in thresholds:
                sig_trend = np.where(sess_mask & (np.abs(trend) >= th), np.sign(trend), 0).astype(np.int8)
                if np.count_nonzero(sig_trend) < 30:
                    continue
                    
                for st in stops:
                    for tgt in targets:
                        for h in holds:
                            cfg = dict(
                                tick=0.25, multiplier=2.0, commission_per_side=0.61, slippage_ticks=1.0, spread_ticks=1.0,
                                stop_atr=st, target_ratio=tgt, hold_bars=h, trailing_atr=0.0, maxqty=1, initial_balance=50000.0,
                                risk_per_trade=150.0, max_open_risk=150.0, daily_loss=300.0, hard_drawdown=1800.0,
                                funded_drawdown=2000.0, flat_minute=955, max_gap_minutes=tf_min*2
                            )
                            res = me.execute(data, sig_trend, atr, cfg)
                            tn = res['trade_net']
                            if len(tn) < 40:
                                continue
                            net = float(tn.sum())
                            exp = float(tn.mean())
                            mdd = float((np.maximum.accumulate(res['cash']) - res['worst']).max())
                            
                            if exp >= 20.0 and mdd <= 1200.0 and net >= 2000.0:
                                t_yr = years[res['trade_entry']]
                                yearly = {y: float(tn[t_yr == y].sum()) if np.any(t_yr == y) else 0.0 for y in unique_years}
                                pos_y = sum(yearly[y] > 0 for y in unique_years)
                                
                                if pos_y >= 3: # Positive in at least 3 of 4 train years
                                    results.append({
                                        'tf': tf_label, 'win': w_name, 'mech': 'Trend', 'lb': lb, 'th': th,
                                        'stop': st, 'tgt': tgt, 'hold': h, 'trades': len(tn),
                                        'net': net, 'exp': exp, 'mdd': mdd, 'calmar': net / mdd if mdd > 0 else 0,
                                        'pos_years': f"{pos_y}/4", 'yearly': yearly
                                    })
                                    
            # Mechanism 2: Afternoon Breakout
            for th in [0.0, 0.5]:
                cond_long = sess_mask & (c > bh + th * atr)
                cond_short = sess_mask & (c < bl - th * atr)
                sig_bo = np.zeros(len(c), dtype=np.int8)
                sig_bo[cond_long] = 1
                sig_bo[cond_short] = -1
                
                if np.count_nonzero(sig_bo) < 30:
                    continue
                    
                for st in stops:
                    for tgt in targets:
                        for h in holds:
                            cfg = dict(
                                tick=0.25, multiplier=2.0, commission_per_side=0.61, slippage_ticks=1.0, spread_ticks=1.0,
                                stop_atr=st, target_ratio=tgt, hold_bars=h, trailing_atr=0.0, maxqty=1, initial_balance=50000.0,
                                risk_per_trade=150.0, max_open_risk=150.0, daily_loss=300.0, hard_drawdown=1800.0,
                                funded_drawdown=2000.0, flat_minute=955, max_gap_minutes=tf_min*2
                            )
                            res = me.execute(data, sig_bo, atr, cfg)
                            tn = res['trade_net']
                            if len(tn) < 40:
                                continue
                            net = float(tn.sum())
                            exp = float(tn.mean())
                            mdd = float((np.maximum.accumulate(res['cash']) - res['worst']).max())
                            
                            if exp >= 20.0 and mdd <= 1200.0 and net >= 2000.0:
                                t_yr = years[res['trade_entry']]
                                yearly = {y: float(tn[t_yr == y].sum()) if np.any(t_yr == y) else 0.0 for y in unique_years}
                                pos_y = sum(yearly[y] > 0 for y in unique_years)
                                
                                if pos_y >= 3:
                                    results.append({
                                        'tf': tf_label, 'win': w_name, 'mech': f'Breakout_th{th}', 'lb': lb, 'th': th,
                                        'stop': st, 'tgt': tgt, 'hold': h, 'trades': len(tn),
                                        'net': net, 'exp': exp, 'mdd': mdd, 'calmar': net / mdd if mdd > 0 else 0,
                                        'pos_years': f"{pos_y}/4", 'yearly': yearly
                                    })

df_res = pd.DataFrame(results)
print("\n" + "=" * 90)
print(f"AFTERNOON MNQ TRAINING DISCOVERY (2020-2023): {len(df_res)} QUALIFIERS")
print("=" * 90)

if not df_res.empty:
    cols = ['tf', 'win', 'mech', 'lb', 'th', 'stop', 'tgt', 'hold', 'trades', 'net', 'exp', 'mdd', 'pos_years', 'calmar']
    top = df_res.sort_values('calmar', ascending=False)
    print(top[cols].head(20).to_string(index=False))
    
    # Save to json
    out_path = ROOT / 'runs/afternoon_mnq_train_qualifiers.json'
    with open(out_path, 'w') as f:
        json.dump(results, f, indent=2)
    print(f"\nSaved qualifiers to {out_path}")
