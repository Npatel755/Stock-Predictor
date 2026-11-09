import json
from pathlib import Path
import duckdb
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
CATALOG = json.load(open(ROOT / 'data/catalog.json'))

p_mnq_train = CATALOG['instruments']['MNQ']['splits']['train']['path']
p_mes_train = CATALOG['instruments']['MES']['splits']['train']['path']

con = duckdb.connect()

for tf_name, tf_interval in [("15m", "15 minutes"), ("30m", "30 minutes"), ("60m", "60 minutes")]:
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
    df = con.execute(query, [str(p_mnq_train)]).fetch_df()
    df = df[df.timestamp_utc.notna()].copy()
    atr_pts = (df['high'] - df['low']).mean()
    print(f"MNQ Train ({tf_name}): {len(df):>6} bars | Average Bar Range: {atr_pts:.2f} pts (${atr_pts*2:.2f} / contract)")

for tf_name, tf_interval in [("15m", "15 minutes"), ("30m", "30 minutes"), ("60m", "60 minutes")]:
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
    df = con.execute(query, [str(p_mes_train)]).fetch_df()
    df = df[df.timestamp_utc.notna()].copy()
    atr_pts = (df['high'] - df['low']).mean()
    print(f"MES Train ({tf_name}): {len(df):>6} bars | Average Bar Range: {atr_pts:.2f} pts (${atr_pts*5:.2f} / contract)")
con.close()
