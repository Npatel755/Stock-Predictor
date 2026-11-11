"""Fetch Databento GLBX.MDP3 ohlcv-1s NQ bars for the Crabel 16/28/120 trade days (free-roll sprint + Vol-Adaptive Fortress).
TRAINING 2010-23 ONLY. Budget-guarded: Nick has $50 of free credits and the spend MUST NOT exceed it.

Usage:
  python fetch_1s_crabel_train.py --estimate [--scope all|amb]      free: Databento metadata.get_cost only, nothing downloaded
  python fetch_1s_crabel_train.py --download --scope amb --cap 40   downloads, stops before the running cost would pass --cap

Each request = one day, the RTH contract the training bars used that day (by instrument_id), 09:45:00-15:56:00 ET (the trade
window of the strategy). Files are cached in data/market/onesec_nq/ (git-ignored) and never re-requested (Databento bills every
download). The key is read from quant_trading_bot/.env and is never printed.
"""
import argparse, json, os, sys, time
from pathlib import Path
import pandas as pd, pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
OUT = ROOT / "data/market/onesec_nq"; OUT.mkdir(parents=True, exist_ok=True)
LEDGER = OUT / "_spend_ledger.json"
DATASET, SCHEMA = "GLBX.MDP3", "ohlcv-1s"
HARD_CAP = 45.0                                    # absolute ceiling regardless of --cap (Nick's limit is $50)


def api_key():
    for line in (ROOT / ".env").read_text().splitlines():
        if line.startswith("DATABENTO_API_KEY="): return line.split("=", 1)[1].strip()
    raise SystemExit("no key in .env")


def request_days(scope):
    import audit_vol_adaptive_fortress_train as au
    dates, gap, G = au.load_train()
    days, amb = set(), set()
    for vixf in (au.same_day_vix, au.prior_day_vix):
        for pess in (False, True):
            r, _, _ = au.sim(dates, gap, G, vixf, pess=pess)
            for k, v in r.items():
                if v["traded"]: days.add(k)
                if v.get("amb"): amb.add(k)
    pick = sorted({k[:10] for k in (amb if scope == "amb" else days)})
    t = pq.read_table(ROOT / "data/market/GLBX-20261106-FX6FM5XWUX-v3/splits/NQ/train.parquet", columns=["timestamp_utc", "instrument_id"]).to_pandas()
    et = t.timestamp_utc.dt.tz_convert("America/New_York"); sod = et.dt.hour * 60 + et.dt.minute
    t = t[(sod >= 585) & (sod <= 955)]; t["date"] = et[t.index].dt.date.astype(str)
    iid = t.groupby("date").instrument_id.agg(lambda s: int(s.mode().iloc[0])).to_dict()
    reqs = []
    for d in pick:
        assert d < "2024-01-01", d                     # training split only
        s = pd.Timestamp(d + " 09:45", tz="America/New_York").tz_convert("UTC"); e = pd.Timestamp(d + " 15:56", tz="America/New_York").tz_convert("UTC")
        reqs.append(dict(date=d, instrument_id=iid[d], start=s.isoformat(), end=e.isoformat()))
    return reqs, len(days), len(amb)


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--estimate", action="store_true"); ap.add_argument("--download", action="store_true")
    ap.add_argument("--scope", default="amb", choices=["all", "amb"]); ap.add_argument("--cap", type=float, default=40.0); a = ap.parse_args()
    import databento as db
    client = db.Historical(api_key())
    reqs, n_all, n_amb = request_days(a.scope)
    print(f"trade days {n_all}, ambiguous days {n_amb}, requesting scope={a.scope}: {len(reqs)} days", flush=True)
    est_path = OUT / "_cost_estimate.json"          # shared cache: amb days are a subset of all days
    if est_path.exists():
        est = json.loads(est_path.read_text())
    else:
        est = {}
    for i, r in enumerate(reqs):
        if r["date"] in est: continue
        kw = dict(dataset=DATASET, symbols=[r["instrument_id"]], stype_in="instrument_id", schema=SCHEMA, start=r["start"], end=r["end"])
        for attempt in range(6):                        # get_cost is free; retry gateway timeouts
            try: est[r["date"]] = dict(cost=float(client.metadata.get_cost(**kw)), bytes=0); break
            except Exception as ex: print(f"  retry {r['date']} ({type(ex).__name__})", flush=True); time.sleep(5 * (attempt + 1))
        else: raise SystemExit("cost estimate kept failing")
        est_path.write_text(json.dumps(est))
        if i % 25 == 0: print(f"  estimated {i + 1}/{len(reqs)}  running ${sum(v['cost'] for v in est.values()):.4f}", flush=True)
    est_path.write_text(json.dumps(est))
    total = sum(est[r["date"]]["cost"] for r in reqs); size = sum(est[r["date"]]["bytes"] for r in reqs)
    print(f"ESTIMATE scope={a.scope}: {len(reqs)} days, {size / 1e6:.1f} MB, ${total:.4f}", flush=True)
    if not a.download: return
    cap = min(a.cap, HARD_CAP)
    ledger = json.loads(LEDGER.read_text()) if LEDGER.exists() else {"spent_estimated": 0.0, "days": {}}
    if ledger["spent_estimated"] + sum(est[r["date"]]["cost"] for r in reqs if r["date"] not in ledger["days"]) > cap:
        raise SystemExit(f"refusing: total would exceed cap ${cap:.2f}")
    for r in reqs:
        f = OUT / f"{r['date']}.parquet"
        if r["date"] in ledger["days"] and f.exists(): continue
        c = est[r["date"]]["cost"]
        if ledger["spent_estimated"] + c > cap: raise SystemExit(f"stopping: next request would pass cap ${cap:.2f}")
        for attempt in range(3):                        # every attempt is charged to the ledger, as if billed, to stay under the cap
            if ledger["spent_estimated"] + c > cap: raise SystemExit(f"stopping: next request would pass cap ${cap:.2f}")
            ledger["spent_estimated"] = round(ledger["spent_estimated"] + c, 6); LEDGER.write_text(json.dumps(ledger))
            try:
                data = client.timeseries.get_range(dataset=DATASET, symbols=[r["instrument_id"]], stype_in="instrument_id", schema=SCHEMA, start=r["start"], end=r["end"])
                df = data.to_df(price_type="float", pretty_ts=True).reset_index(); df.to_parquet(f, index=False); break
            except Exception as ex: print(f"  download retry {r['date']} ({type(ex).__name__})", flush=True); time.sleep(10 * (attempt + 1))
        else: raise SystemExit(f"download kept failing on {r['date']}")
        ledger["days"][r["date"]] = c; LEDGER.write_text(json.dumps(ledger))
    print(f"downloaded {len(ledger['days'])} days, estimated spend ${ledger['spent_estimated']:.4f}")


if __name__ == "__main__":
    main()
