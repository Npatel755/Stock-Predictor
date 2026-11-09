import sys, json, duckdb, numpy as np, pandas as pd
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
con = duckdb.connect()
paths = [
    cat['instruments']['MNQ']['splits']['train']['path'],
    cat['instruments']['MNQ']['splits']['validation']['path'],
    cat['instruments']['MNQ']['splits']['test']['path']
]
q = """
SELECT time_bucket(INTERVAL '30 minutes', CAST(timestamp_utc AS TIMESTAMPTZ)) AS timestamp_utc,
       'MNQ' as instrument, arg_min(contract, timestamp_utc) as contract,
       arg_min(session_id, timestamp_utc) as session_id, arg_min(open, timestamp_utc) as open,
       max(high) as high, min(low) as low, arg_max(close, timestamp_utc) as close, sum(volume)::DOUBLE as volume
FROM read_parquet(?) GROUP BY 1 ORDER BY 1
"""
df = canonical(con.execute(q, [paths]).fetch_df())
con.close()

d = apply_early_close(generalized_arrays(df), df)
f = compute_htf_features(df, 16, 30)
loc = df.timestamp_utc.dt.tz_convert('America/New_York')
dec = (loc.dt.hour * 60 + loc.dt.minute + 30).to_numpy()
sig = np.where((dec >= 585) & (dec < 720) & (loc.dt.weekday.to_numpy() < 5) & (np.abs(f['trend']) >= 0.75), np.sign(f['trend']), 0).astype(np.int8)

print("=" * 100)
print("MNQ 30m Breakout: Sizing and Risk per Trade Impact (2020-2026)")
print("=" * 100)

for rpt in [150.0, 200.0, 250.0, 300.0]:
    cfg = dict(tick=0.25, multiplier=2.0, commission_per_side=0.61, slippage_ticks=1.0, spread_ticks=1.0,
               stop_atr=1.5, target_ratio=3.5, hold_bars=8, trailing_atr=0.0, maxqty=1, initial_balance=50000.0,
               risk_per_trade=rpt, max_open_risk=rpt, daily_loss=rpt*2, hard_drawdown=1800.0, funded_drawdown=2000.0,
               flat_minute=955, max_gap_minutes=60)
    res = me.execute(d, sig, f['atr'], cfg)
    tn = res['trade_net']
    yr = d['year'][res['trade_entry']]
    m26 = yr == 2026
    net26 = float(tn[m26].sum()) if np.any(m26) else 0.0
    cnt26 = int(np.count_nonzero(m26))
    exp26 = net26 / cnt26 if cnt26 else 0.0
    total_net = float(tn.sum())
    worst_dd = float((np.maximum.accumulate(res['cash']) - res['worst']).max())
    failed = res['funded_failed']
    print(f"rpt=${rpt:3.0f} -> Total Net: +${total_net:9.2f} | 7Y MaxDD: ${worst_dd:7.2f} | 2026 Net: +${net26:8.2f} ({cnt26:2d} trades, exp +${exp26:6.2f}) | Breach: {failed}")
