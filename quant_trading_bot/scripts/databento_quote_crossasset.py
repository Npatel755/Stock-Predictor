"""Quote-only (no purchase): Databento GLBX.MDP3 ohlcv-1m for cross-asset continuous front-month symbols 2010-2025.
Reads the key from DATABENTO_API_KEY; prints cost per symbol/span and totals. Never calls timeseries.get_range."""
import os, sys, json
import databento as db
client = db.Historical(os.environ["DATABENTO_API_KEY"])
syms = sys.argv[1].split(",") if len(sys.argv) > 1 else ["ZN.c.0", "6E.c.0", "CL.c.0"]
spans = [("2010-06-06", "2026-01-01")]
out = {}
for s in syms:
    for lo, hi in spans:
        try:
            c = client.metadata.get_cost(dataset="GLBX.MDP3", symbols=[s], stype_in="continuous", schema="ohlcv-1m", start=lo, end=hi)
            sz = client.metadata.get_billable_size(dataset="GLBX.MDP3", symbols=[s], stype_in="continuous", schema="ohlcv-1m", start=lo, end=hi)
            out[f"{s} {lo}..{hi}"] = dict(usd=round(float(c), 2), mb=round(sz / 1e6, 1))
        except Exception as e:
            out[f"{s} {lo}..{hi}"] = dict(error=str(e)[:160])
        print(f"{s} {lo}..{hi}: {out[f'{s} {lo}..{hi}']}", flush=True)
print("TOTAL usd", round(sum(v.get("usd", 0) for v in out.values()), 2))
