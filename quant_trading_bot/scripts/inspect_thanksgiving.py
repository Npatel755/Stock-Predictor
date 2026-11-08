import duckdb
import json
import pandas as pd

cat = json.load(open('quant_trading_bot/data/catalog.json'))
p = cat['instruments']['MES']['splits']['validation']['path']
con = duckdb.connect()
df = con.execute("SELECT timestamp_utc, open, high, low, close FROM read_parquet(?) WHERE timestamp_utc >= '2024-11-28' AND timestamp_utc <= '2024-12-02' ORDER BY 1", [str(p)]).fetch_df()
if df['timestamp_utc'].dt.tz is None:
    df['et'] = df['timestamp_utc'].dt.tz_localize('UTC').dt.tz_convert('America/New_York')
else:
    df['et'] = df['timestamp_utc'].dt.tz_convert('America/New_York')
print("Thanksgiving 2024 bars (last 30 bars of Friday Nov 29):")
print(df[df['et'].dt.date == pd.to_datetime('2024-11-29').date()][['et', 'open', 'high', 'low', 'close']].tail(20).to_string())

print("\nFirst 10 bars of Sunday/Monday Dec 1-2:")
print(df[df['et'].dt.date >= pd.to_datetime('2024-12-01').date()][['et', 'open', 'high', 'low', 'close']].head(10).to_string())
