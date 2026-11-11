"""Databento GLBX.MDP3 ohlcv-1m CL.v.0 (crude oil, volume-front continuous), TRAINING YEARS ONLY (2010-06-06 .. 2024-01-01).
Approved by Nick 2026-11-10 ("go ahead and download it so it doesnt go over the amount of free credits i have"); free credits $50.

  python fetch_cl_1m_train.py --estimate     free: metadata.get_cost per yearly chunk, nothing downloaded
  python fetch_cl_1m_train.py --download     buys the chunks not yet on disk

Budget rules:
- Every Databento spend since Nick gave this key is in data/market/onesec_nq/_spend_ledger.json (1-second NQ) and
  data/market/crossasset_train/_spend.json. HARD_CAP = $45 total across both (a $5 margin under the $50 of credits).
- Each chunk is quoted (free) before it is requested and is requested only if ledger total + its quote <= HARD_CAP. Each attempt is charged
  to the ledger BEFORE the request, so a failed attempt counts as billed (the ledger can only overstate the spend).
- Yearly chunks, so a failed stream risks one chunk, not the whole file. A chunk already on disk is never requested again.
Holdout guard: the last chunk ends 2024-01-01 UTC and every saved bar is asserted to be before 2024-01-01.
"""
import json, sys, time
from pathlib import Path
import pandas as pd
import databento as db

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data/market/crossasset_train/CL_v_0_ohlcv1m"
SPEND = ROOT / "data/market/crossasset_train/_spend.json"
ONESEC = ROOT / "data/market/onesec_nq/_spend_ledger.json"
HARD_CAP = 45.0
SYM = "CL.v.0"
CHUNKS = [("2010-06-06", "2011-01-01")] + [(f"{y}-01-01", f"{y + 1}-01-01") for y in range(2011, 2024)]
assert max(hi for _, hi in CHUNKS) <= "2024-01-01"


def api_key():
    for line in (ROOT / ".env").read_text().splitlines():
        if line.startswith("DATABENTO_API_KEY="): return line.split("=", 1)[1].strip()
    sys.exit("DATABENTO_API_KEY missing from quant_trading_bot/.env")


def ledger():
    return json.loads(SPEND.read_text()) if SPEND.exists() else {}


def spent_total():
    return float(json.loads(ONESEC.read_text())["spent_estimated"]) + sum(float(v) for v in ledger().values())


def charge(tag, usd):
    s = ledger(); s[tag] = round(float(s.get(tag, 0.0)) + usd, 6); SPEND.write_text(json.dumps(s, indent=1))


def kw(lo, hi):
    return dict(dataset="GLBX.MDP3", symbols=[SYM], stype_in="continuous", schema="ohlcv-1m", start=lo, end=hi)


def quote(client, lo, hi):
    for _ in range(6):
        try: return float(client.metadata.get_cost(**kw(lo, hi)))
        except Exception as e: err = e; time.sleep(5)
    raise RuntimeError(f"get_cost failed {lo}: {str(err)[:120]}")


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "--estimate"
    client = db.Historical(api_key()); OUT.mkdir(parents=True, exist_ok=True)
    q = {lo: quote(client, lo, hi) for lo, hi in CHUNKS}
    todo = [(lo, hi) for lo, hi in CHUNKS if not (OUT / f"{lo[:4]}.parquet").exists()]
    print(f"spent so far (ledger) ${spent_total():.2f} | all chunks ${sum(q.values()):.2f} | still to buy ${sum(q[lo] for lo, _ in todo):.2f} "
          f"| cap ${HARD_CAP:.2f}", flush=True)
    if mode != "--download": return
    for lo, hi in todo:
        dest = OUT / f"{lo[:4]}.parquet"
        for attempt in range(2):
            if spent_total() + q[lo] > HARD_CAP:
                sys.exit(f"STOP: chunk {lo[:4]} (${q[lo]:.2f}) would take the ledger past ${HARD_CAP:.2f}")
            charge(f"CL_v_0_ohlcv1m_{lo[:4]}", q[lo])
            try:
                df = client.timeseries.get_range(**kw(lo, hi)).to_df()
                assert len(df) and df.index.max() < pd.Timestamp("2024-01-01", tz="UTC")
                df.to_parquet(dest); print(f"{lo[:4]}: {len(df):,} bars, ${q[lo]:.2f}, ledger ${spent_total():.2f}", flush=True); break
            except Exception as e:
                print(f"{lo[:4]} attempt {attempt + 1} failed ({str(e)[:120]}); counted as billed", flush=True); time.sleep(10)
    parts = sorted(OUT.glob("*.parquet"))
    if len(parts) == len(CHUNKS):
        df = pd.concat([pd.read_parquet(p) for p in parts]).sort_index()
        assert df.index.max() < pd.Timestamp("2024-01-01", tz="UTC")
        dup = int(df.reset_index().duplicated(["ts_event"]).sum())
        df.to_parquet(OUT.parent / "CL_v_0_ohlcv1m_2010_2023.parquet")
        print(f"combined: {len(df):,} bars {df.index.min()} .. {df.index.max()}, duplicate timestamps {dup}, "
              f"contracts {df.instrument_id.nunique()}, ledger ${spent_total():.2f}", flush=True)


if __name__ == "__main__":
    main()
