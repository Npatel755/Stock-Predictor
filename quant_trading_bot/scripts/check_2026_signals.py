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
path = cat['instruments']['MNQ']['splits']['test']['path']

con = duckdb.connect()
q = f"""
SELECT 
    time_bucket(INTERVAL '30 minutes', CAST(timestamp_utc AS TIMESTAMPTZ)) AS timestamp_utc,
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
df = con.execute(q, [path]).fetch_df()
df['instrument'] = 'MNQ'
b = canonical(df)
con.close()

f = compute_htf_features(b, 16, 30)
loc = b.timestamp_utc.dt.tz_convert('America/New_York')
dec = (loc.dt.hour * 60 + loc.dt.minute + 30).to_numpy()
weekdays = loc.dt.weekday.to_numpy() < 5
sig = np.where((dec >= 585) & (dec < 720) & weekdays & (np.abs(f['trend']) >= 0.75), np.sign(f['trend']), 0).astype(np.int8)

print(f"Total non-zero signals in 2026 Test: {np.count_nonzero(sig)}")
b['sig'] = sig
b['loc_time'] = loc
b['trend'] = f['trend']
sig_bars = b[b['sig'] != 0][['loc_time', 'close', 'trend', 'sig']]
print("\nFirst 10 signal bars:")
print(sig_bars.head(10).to_string(index=False))
print("\nLast 10 signal bars:")
print(sig_bars.tail(10).to_string(index=False))

# Now run execution on test bars alone to see what happens
d = apply_early_close(generalized_arrays(b), b)
cfg = dict(tick=0.25, multiplier=2.0, commission_per_side=0.61, slippage_ticks=1.0, spread_ticks=1.0,
           stop_atr=1.5, target_ratio=3.5, hold_bars=8, trailing_atr=0.0, maxqty=1, initial_balance=50000.0,
           risk_per_trade=150.0, max_open_risk=150.0, daily_loss=300.0, hard_drawdown=1800.0, funded_drawdown=2000.0,
           flat_minute=955, max_gap_minutes=60)
res = me.execute(d, sig, f['atr'], cfg)
print(f"\nExecution on test split alone: {len(res['trade_net'])} trades, Net: ${res['trade_net'].sum():.2f}")
print("Funded failed:", res['funded_failed'])
