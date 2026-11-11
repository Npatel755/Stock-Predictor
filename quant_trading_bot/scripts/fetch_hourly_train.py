"""Databento GLBX.MDP3 ohlcv-1h continuous bars, TRAINING YEARS ONLY (2010-06-06 .. 2024-01-01). Claude, 2026-11-10.
Approved by Nick 2026-11-10 ("go") for GC.v.0 + SI.v.0 + BTC.v.0, quoted $1.95 total; free credits left before this ~$15.18.

  python fetch_hourly_train.py GC.v.0 SI.v.0 BTC.v.0            quote (free) and buy the symbols not yet on disk
  python fetch_hourly_train.py --estimate GC.v.0 ...             quote only

Budget rules as fetch_cl_1m_train.py: ledger = onesec_nq/_spend_ledger.json + crossasset_train/_spend.json; HARD_CAP $45 total (real credits
left are lower, see memory; the cap keeps the card untouched); each request is quoted first and charged to the ledger BEFORE it is made.
"""
import json, sys, time
from pathlib import Path
import pandas as pd
import databento as db

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data/market/crossasset_train"
SPEND = OUT / "_spend.json"; ONESEC = ROOT / "data/market/onesec_nq/_spend_ledger.json"
HARD_CAP, LO, HI = 45.0, "2010-06-06", "2024-01-01"


def spent_total():
    s = json.loads(SPEND.read_text()) if SPEND.exists() else {}
    return float(json.loads(ONESEC.read_text())["spent_estimated"]) + sum(float(v) for v in s.values())


def charge(tag, usd):
    s = json.loads(SPEND.read_text()) if SPEND.exists() else {}
    s[tag] = round(float(s.get(tag, 0.0)) + usd, 6); SPEND.write_text(json.dumps(s, indent=1))


def main():
    args = sys.argv[1:]; estimate = "--estimate" in args; syms = [a for a in args if not a.startswith("--")]
    key = [l.split("=", 1)[1].strip() for l in (ROOT / ".env").read_text().splitlines() if l.startswith("DATABENTO_API_KEY=")][0]
    client = db.Historical(key)
    for sym in syms:
        kw = dict(dataset="GLBX.MDP3", symbols=[sym], stype_in="continuous", schema="ohlcv-1h", start=LO, end=HI)
        dest = OUT / f"{sym.replace('.', '_')}_ohlcv1h_2010_2023.parquet"; tag = dest.stem
        cost = None
        for _ in range(6):
            try: cost = float(client.metadata.get_cost(**kw)); break
            except Exception: time.sleep(5)
        if cost is None: sys.exit(f"quote failed for {sym}")
        print(f"{sym}: quote ${cost:.2f} | ledger ${spent_total():.2f} | on disk {dest.exists()}", flush=True)
        if estimate or dest.exists(): continue
        if spent_total() + cost > HARD_CAP: sys.exit(f"STOP: {sym} would take the ledger past ${HARD_CAP:.2f}")
        charge(tag, cost)
        df = client.timeseries.get_range(**kw).to_df()
        assert len(df) and df.index.max() < pd.Timestamp("2024-01-01", tz="UTC")
        df.to_parquet(dest)
        print(f"{sym}: {len(df):,} bars {df.index.min()} .. {df.index.max()}, contracts {df.instrument_id.nunique()}, ledger ${spent_total():.2f}", flush=True)


if __name__ == "__main__":
    main()
