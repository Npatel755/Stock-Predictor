"""Approved purchase (Nick, 2026-11-08, new account, cap $125): GLBX.MDP3 ohlcv-1m continuous front month ZN/6E/CL Jun 2010 - Dec 2025,
quoted $45.94 total. Re-checks the cost per symbol and aborts if the running total would exceed the quoted cap. Saves parquet."""
import os, sys, json, time
from pathlib import Path
import databento as db, pandas as pd
ROOT = Path(__file__).resolve().parents[1]; OUT = ROOT / "data/market/crossasset"; OUT.mkdir(parents=True, exist_ok=True)
CAP = 50.0
client = db.Historical(os.environ["DATABENTO_API_KEY"])
spent = 0.0; log = {}
for sym in ["ZN.c.0", "6E.c.0", "CL.c.0"]:
    dest = OUT / f"{sym.replace('.', '_')}_ohlcv1m_2010_2025.parquet"
    if dest.exists():
        print("exists", dest.name); continue
    kw = dict(dataset="GLBX.MDP3", symbols=[sym], stype_in="continuous", schema="ohlcv-1m", start="2010-06-06", end="2026-01-01")
    cost = float(client.metadata.get_cost(**kw))
    if spent + cost > CAP:
        print("ABORT: would exceed cap", spent + cost); break
    t0 = time.time(); data = client.timeseries.get_range(**kw); df = data.to_df()
    df.to_parquet(dest); spent += cost
    log[sym] = dict(usd=round(cost, 2), rows=len(df), first=str(df.index.min()), last=str(df.index.max()), seconds=round(time.time() - t0))
    print(sym, log[sym], "spent so far", round(spent, 2), flush=True)
json.dump(dict(spent_usd=round(spent, 2), files=log), open(OUT / "download_log.json", "w"), indent=1)
print("DONE spent", round(spent, 2))
