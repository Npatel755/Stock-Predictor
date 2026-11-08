"""Re-score the paper candidates and the mass_v2 survivor at the LucidFlex fee schedule ($0.61/side micro all-in:
$0.25 commission + $0.35 exchange + $0.01 NFA) vs the engine default $0.50/side. MES/MNQ 2020-2023 (train) and
2024-2025 (validation) from the physical partitions; annual $50k accounts; 2026 never loaded."""
import json, sys
from pathlib import Path
import duckdb, numpy as np, pandas as pd
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src")); sys.path.insert(0, str(ROOT / "scripts"))
import unseen_years_replication as uy
from quant_futures import ensemble_paper as ep
from quant_futures.data import canonical
from quant_futures.session_calendar import apply_early_close
CAT = json.load(open(uy.CATALOG))["instruments"]
eng = ep.engine()
SURVIVOR = dict(instrument="MNQ", family="trend", lookback=8, threshold=1.0, stop_atr=2.0, target_r=2.0, hold_bars=12,
                session_start=600, session_end=720, max_contracts=1, trailing_atr=0.0)
CANDS = {k: [s for s in v["sleeves"]] for k, v in ep.CANDIDATES.items()}
CANDS["mass_v2_survivor"] = [dict(name="MNQ_TRD8_1c", **SURVIVOR)]

def load(inst, split, start, end):
    con = duckdb.connect(); f = con.execute(uy.STRICT, [str(CAT[inst]["splits"][split]["path"]), start, end]).fetch_df(); con.close()
    f = f[f.timestamp_utc.notna()].copy(); f["high"] = f[["open","high","low","close"]].max(axis=1); f["low"] = f[["open","high","low","close"]].min(axis=1)
    f["volume"] = f.volume.round(); b = canonical(f); assert b.timestamp_utc.max() < pd.Timestamp("2026-01-01", tz="UTC"); return b

BARS = {(i, s): load(i, s, a, e) for i in ("MES", "MNQ") for s, a, e in (("train", "2019-12-01", "2024-01-01"), ("validation", "2023-12-01", "2026-01-01"))}

def run(cfg, bars, year, fee):
    data = apply_early_close(eng["arrays"](bars), bars); f = eng["features"](bars, int(cfg["lookback"])); raw = eng["signal_for"](cfg, f).astype(np.int8)
    loc = bars.timestamp_utc.dt.tz_convert("America/New_York"); dec = (loc.dt.hour*60+loc.dt.minute+15).to_numpy()
    sig = np.where((dec >= cfg["session_start"]) & (dec < cfg["session_end"]) & (loc.dt.day_of_week.to_numpy() < 5), raw, 0).astype(np.int8)
    idx = np.flatnonzero(data["year"] == year); a, b = int(idx[0]), int(idx[-1]) + 1
    d = {k: np.ascontiguousarray(v[a:b]) for k, v in data.items()}
    d["session"] = pd.factorize(d["session"], sort=False)[0].astype(np.int64); d["contract"] = pd.factorize(d["contract"], sort=False)[0].astype(np.int64)
    ecfg = eng["execution_cfg"](cfg); ecfg["commission_per_side"] = fee
    r = eng["execute"](d, np.ascontiguousarray(sig[a:b]), np.ascontiguousarray(f["atr"][a:b]), ecfg)
    peaks = np.maximum.accumulate(np.r_[50000.0, r["equity"]])[1:]
    return float(r["cash"][-1] - 50000.0), float(np.max(peaks - r["worst"])), int(len(r["trade_net"])), pd.Series(r["cash"], index=d["timestamp"])

rows = []
for cand, sleeves in CANDS.items():
    for fee in (0.50, 0.61):
        for split, years in (("train", range(2020, 2024)), ("validation", (2024, 2025))):
            for y in years:
                net = dd = tr = 0.0; curves = []
                for s in sleeves:
                    n, _, t, c = run(s, BARS[(s["instrument"], split)], y, fee); net += n; tr += t; curves.append(c)
                comb = pd.concat(curves, axis=1).sort_index().ffill().fillna(50000.0).sum(axis=1) - 50000.0 * (len(curves) - 1)
                dd = float((comb.cummax() - comb).max())
                rows.append(dict(candidate=cand, fee=fee, split=split, year=y, net=round(net, 2), dd=round(dd, 2), trades=int(tr)))
df = pd.DataFrame(rows)
out = df.groupby(["candidate", "fee", "split"]).agg(net=("net", "sum"), worst_dd=("dd", "max"), trades=("trades", "sum"), years_pos=("net", lambda s: int((s > 0).sum()))).reset_index()
piv = out.pivot_table(index=["candidate", "split"], columns="fee", values=["net", "worst_dd", "trades"])
print(piv.round(0).to_string())
df.to_json(ROOT / "reports" / "FEE_SENSITIVITY_LUCIDFLEX.json", orient="records", indent=1)
lines = ["# Fee sensitivity: engine default $0.50/side vs LucidFlex micro all-in $0.61/side\n",
         "Closed-equity DD is the combined candidate curve (sleeves summed), annual $50k accounts, 2026 never loaded.\n",
         "| candidate | split | net @0.50 | net @0.61 | delta | worst DD @0.50 | worst DD @0.61 | trades |", "|---|---|---:|---:|---:|---:|---:|---:|"]
for (c, s), g in out.groupby(["candidate", "split"]):
    a, b = g[g.fee == 0.50].iloc[0], g[g.fee == 0.61].iloc[0]
    lines.append(f"| {c} | {s} | {a.net:,.0f} | {b.net:,.0f} | {b.net - a.net:,.0f} | {a.worst_dd:,.0f} | {b.worst_dd:,.0f} | {int(a.trades)} |")
(ROOT / "reports" / "FEE_SENSITIVITY_LUCIDFLEX.md").write_text("\n".join(lines) + "\n"); print("\n".join(lines))
