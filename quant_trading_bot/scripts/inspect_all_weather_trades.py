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

con = duckdb.connect()
cat = json.load(open(ROOT / 'data/catalog.json'))

paths = [
    cat['instruments']['MNQ']['splits']['train']['path'],
    cat['instruments']['MNQ']['splits']['validation']['path'],
    cat['instruments']['MNQ']['splits']['test']['path']
]

def load_continuous_bars(tf_interval):
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
    df = con.execute(q, [paths]).fetch_df()
    df['instrument'] = 'MNQ'
    return canonical(df)

b_30m = load_continuous_bars('30 minutes')
b_60m = load_continuous_bars('60 minutes')
con.close()

# 1. Sleeve 1: MNQ 30m Breakout
d_30m = apply_early_close(generalized_arrays(b_30m), b_30m)
f_30m = compute_htf_features(b_30m, 16, 30)
loc_30m = b_30m.timestamp_utc.dt.tz_convert('America/New_York')
dec_30m = (loc_30m.dt.hour * 60 + loc_30m.dt.minute + 30).to_numpy()
sig_30m = np.where((dec_30m >= 585) & (dec_30m < 720) & (loc_30m.dt.weekday.to_numpy() < 5) & (np.abs(f_30m['trend']) >= 0.75), np.sign(f_30m['trend']), 0).astype(np.int8)
cfg_30m = dict(tick=0.25, multiplier=2.0, commission_per_side=0.61, slippage_ticks=1.0, spread_ticks=1.0,
               stop_atr=1.5, target_ratio=3.5, hold_bars=8, trailing_atr=0.0, maxqty=1, initial_balance=50000.0,
               risk_per_trade=150.0, max_open_risk=150.0, daily_loss=300.0, hard_drawdown=1800.0, funded_drawdown=2000.0,
               flat_minute=955, max_gap_minutes=60)
res_30m = me.execute(d_30m, sig_30m, f_30m['atr'], cfg_30m)

# 2. Sleeve 2: MNQ 60m Macro Trend
d_60m = apply_early_close(generalized_arrays(b_60m), b_60m)
f_60m = compute_htf_features(b_60m, 12, 60)
loc_60m = b_60m.timestamp_utc.dt.tz_convert('America/New_York')
dec_60m = (loc_60m.dt.hour * 60 + loc_60m.dt.minute + 60).to_numpy()
sig_60m = np.where((dec_60m >= 600) & (dec_60m < 720) & (loc_60m.dt.weekday.to_numpy() < 5) & (np.abs(f_60m['trend']) >= 0.75), np.sign(f_60m['trend']), 0).astype(np.int8)
cfg_60m = dict(tick=0.25, multiplier=2.0, commission_per_side=0.61, slippage_ticks=1.0, spread_ticks=1.0,
               stop_atr=1.25, target_ratio=4.0, hold_bars=8, trailing_atr=0.0, maxqty=1, initial_balance=50000.0,
               risk_per_trade=150.0, max_open_risk=150.0, daily_loss=300.0, hard_drawdown=1800.0, funded_drawdown=2000.0,
               flat_minute=955, max_gap_minutes=120)
res_60m = me.execute(d_60m, sig_60m, f_60m['atr'], cfg_60m)

print("=" * 80)
print("SLEEVE 1: MNQ 30m BREAKOUT TRADES IN 2026 TEST")
print("=" * 80)
idx_30 = res_30m['trade_entry']
yr_30 = d_30m['year'][idx_30]
m26_30 = yr_30 == 2026
for i, (en, ex, net) in enumerate(zip(idx_30[m26_30], res_30m['trade_exit'][m26_30], res_30m['trade_net'][m26_30])):
    en_t = b_30m['timestamp_utc'].iloc[en].tz_convert('America/New_York')
    ex_t = b_30m['timestamp_utc'].iloc[ex].tz_convert('America/New_York')
    print(f"Trade {i+1}: Entry {en_t} -> Exit {ex_t} | Net: ${net:+.2f}")

print("\n" + "=" * 80)
print("SLEEVE 2: MNQ 60m TREND TRADES IN 2026 TEST")
print("=" * 80)
idx_60 = res_60m['trade_entry']
yr_60 = d_60m['year'][idx_60]
m26_60 = yr_60 == 2026
for i, (en, ex, net) in enumerate(zip(idx_60[m26_60], res_60m['trade_exit'][m26_60], res_60m['trade_net'][m26_60])):
    en_t = b_60m['timestamp_utc'].iloc[en].tz_convert('America/New_York')
    ex_t = b_60m['timestamp_utc'].iloc[ex].tz_convert('America/New_York')
    print(f"Trade {i+1}: Entry {en_t} -> Exit {ex_t} | Net: ${net:+.2f}")
