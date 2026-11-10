"""Export the D+ v2 per-trade log (TRAINING 2010-23 ONLY) for outside replication.

Trades come from the same engine run as dplus_4_pilot.py (ag_arch_d_plus_v2 sleeves: AG_CRABEL15_D_1c, AG_MES_TRD30_D_1c,
AG_TRD60_D_1c, routed one position at a time, prior-close VIX > VIX3M backwardation stand-aside on the gated sleeves), 1 contract.
No validation (2024-25) or test (2026) data is loaded.

Columns:
  entry_ts / exit_ts   UTC, open-stamped bar times from the engine (fill at the entry bar's open)
  side                 +1 long / -1 short
  entry_price, exit_price   engine fill prices (adverse slippage/spread already applied)
  stop_price           entry -/+ stop_atr x ATR(decision bar), recovered from the engine's stop_risk
  mae_pts / mfe_pts    worst / best move in points from entry_price, from 1-min bars between entry and exit
                       (NQ/ES before 2019, MNQ/MES from 2019); stop exits have MAE set to the stop distance
  net_usd, fees_usd    per contract, after costs ($0.61/side, 1.75-tick spread, 1-tick slippage)
  gap_continuation     Crabel trade in the direction of the opening RTH gap (used by the gap-sized variant)
"""
from pathlib import Path
import numpy as np, pandas as pd, pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parents[1]
src = (ROOT / "scripts/dplus_4_pilot.py").read_text(encoding="utf-8").split("\nout = {}")[0]
ns = {"__file__": str(ROOT / "scripts/dplus_4_pilot.py")}
exec(src, ns)
base = ns["base"]
MULT = ns["MULT"] if "MULT" in ns else ns["ns"]["MULT"]  # dplus_4 keeps dplus_1's namespace (where MULT lives) as `ns`
SPL = ROOT / "data/market/GLBX-20261106-FX6FM5XWUX-v3/splits"


def one_min(mini, micro):
    parts = []
    for sym, lo, hi in ((mini, "2010-01-01", "2019-01-01"), (micro, "2019-01-01", "2024-01-01")):
        t = pq.read_table(SPL / sym / "train.parquet", columns=["timestamp_utc", "high", "low"]).to_pandas()
        parts.append(t[(t.timestamp_utc >= pd.Timestamp(lo, tz="UTC")) & (t.timestamp_utc < pd.Timestamp(hi, tz="UTC"))])
    b = pd.concat(parts).drop_duplicates("timestamp_utc").sort_values("timestamp_utc").reset_index(drop=True)
    assert b.timestamp_utc.max() < pd.Timestamp("2024-01-01", tz="UTC")
    return b


bars = {"MNQ": one_min("NQ", "MNQ"), "MES": one_min("ES", "MES")}
rows = []
for t in base:
    inst = "MES" if "MES" in t["sleeve"] else "MNQ"
    mult = MULT[inst]
    side = int(t["side"])
    stop_pts = (float(t["stop_risk"]) - 1.0 - 0.75 * mult) / mult
    e, x = pd.Timestamp(t["entry_ts"]), pd.Timestamp(t["exit_ts"])
    b = bars[inst]
    w = b[(b.timestamp_utc >= e) & (b.timestamp_utc < x)]
    ep = float(t["entry_price"])
    if len(w):
        adverse = (ep - w.low.min()) if side > 0 else (w.high.max() - ep)
        favour = (w.high.max() - ep) if side > 0 else (ep - w.low.min())
    else:
        adverse = favour = 0.0
    move = side * (float(t["exit_price"]) - ep)
    if "stop" in str(t["reason"]):
        adverse = max(stop_pts, -move)
    favour = max(favour, move, 0.0)
    rows.append(dict(sleeve=t["sleeve"], instrument=inst, entry_ts=t["entry_ts"], exit_ts=t["exit_ts"], side=side, qty=int(t["qty"]),
                     entry_price=ep, stop_price=round(ep - side * stop_pts, 2), exit_price=float(t["exit_price"]),
                     mae_pts=round(max(adverse, 0.0), 2), mfe_pts=round(favour, 2), exit_reason=t["reason"],
                     net_usd=float(t["net"]), fees_usd=float(t["fees"]), gap_continuation=bool(t.get("cont", False))))
df = pd.DataFrame(rows).sort_values("entry_ts")
assert pd.to_datetime(df.exit_ts).max() < pd.Timestamp("2024-01-01", tz="UTC")
out = ROOT / "reports/DPLUS_V2_TRADE_LOG_TRAINING_2010_2023.csv"
df.to_csv(out, index=False)
print(f"wrote {out} trades={len(df)} net={df.net_usd.sum():.2f} per_trade={df.net_usd.mean():.2f} "
      f"{df.entry_ts.min()} .. {df.exit_ts.max()}")
print(df.groupby("sleeve").agg(trades=("net_usd", "size"), net=("net_usd", "sum"), mae_med=("mae_pts", "median"), mfe_med=("mfe_pts", "median")))
