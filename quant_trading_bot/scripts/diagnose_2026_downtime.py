import sys
import json
import duckdb
import numpy as np
import pandas as pd
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))

from quant_futures.data import canonical
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

m_morn = (dec >= 585) & (dec < 720) & weekdays
tr = f['trend']

print("2026 Test Morning Window (09:45 - 12:00 ET):")
print(f"Total morning bars: {np.count_nonzero(m_morn)}")
print(f"Max |trend|: {np.nanmax(np.abs(tr[m_morn])):.3f}")
print(f"90th percentile: {np.nanpercentile(np.abs(tr[m_morn]), 90):.3f}")
print(f"95th percentile: {np.nanpercentile(np.abs(tr[m_morn]), 95):.3f}")
print(f"Bars with |trend| >= 0.75: {np.count_nonzero(np.abs(tr[m_morn]) >= 0.75)}")
print(f"Bars with |trend| >= 0.60: {np.count_nonzero(np.abs(tr[m_morn]) >= 0.60)}")
print(f"Bars with |trend| >= 0.50: {np.count_nonzero(np.abs(tr[m_morn]) >= 0.50)}")

m_aft = (dec >= 780) & (dec < 930) & weekdays
print("\n2026 Test Afternoon Window (13:00 - 15:30 ET):")
print(f"Total afternoon bars: {np.count_nonzero(m_aft)}")
print(f"Max |trend|: {np.nanmax(np.abs(tr[m_aft])):.3f}")
print(f"Bars with |trend| >= 0.75: {np.count_nonzero(np.abs(tr[m_aft]) >= 0.75)}")
print(f"Bars with |trend| >= 0.50: {np.count_nonzero(np.abs(tr[m_aft]) >= 0.50)}")
