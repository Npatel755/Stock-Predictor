"""v4 runner checks (training 2010-23 only): (1) regression - existing ag_arch_d_plus_v2 still reproduces +17,576 / 1,398;
(2) live path - v4 on bars truncated mid-trade reports the open position (base + addon) and its closed trades are a prefix of the full run."""
import json
from pathlib import Path
import numpy as np, pandas as pd

ROOT = Path(__file__).resolve().parents[1]
P = (ROOT / "scripts/dplus_7e_pilot.py").read_text(encoding="utf-8").split("\nout = {}")[0].split("\ntr = route(")[0]
ns = {"__file__": str(ROOT / "scripts/dplus_7e_pilot.py")}
exec(P, ns)
ep, OVR = ns["ep"], ns["OVR"]; d7 = ns["ns"]; bars_for = d7["bars_for"]; START = d7["ns"]["START"]
OVR.clear()


def _cboe(n):
    d = pd.read_csv(ROOT / f"data/external/{n}_History.csv"); d.index = pd.to_datetime(d.DATE, format="%m/%d/%Y"); return d.CLOSE.astype(float)
_j = pd.concat([_cboe("VIX").rename("vix"), _cboe("VIX3M").rename("vix3m")], axis=1).dropna().sort_index()
ep._VIX_CACHE["series"] = (_j.vix > _j.vix3m)

out = {}
# (1) regression on an existing, untouched candidate
spec2 = ep.CANDIDATES["ag_arch_d_plus_v2"]
bars2 = {}
for sl in spec2["sleeves"]:
    bars2.setdefault(ep.bars_key(sl), bars_for(sl)[0])
r2 = ep.run_routed(spec2, bars2, START)
t2 = [t for r in r2.values() for t in r["trades"]]
out["regression_ag_arch_d_plus_v2"] = dict(trades=len(t2), net=round(sum(float(t["net"]) for t in t2), 2), expected="1,398 / +17,576.00")

# (2) live path: truncate every bar series inside a multi-bar v4 trade
spec = ep.CANDIDATES["ag_arch_d_plus_v2_gapsize_4c_v4"]
sleeves = [sl for k in ("ag_arch_d_plus_v2_3c_v4", "ag_arch_d_plus_v2_gap_addon_1of3_v4") for sl in ep.CANDIDATES[k]["sleeves"]]
bars = {}
for sl in sleeves:
    bars.setdefault(ep.bars_key(sl), bars_for(sl)[0])
full = ep.run_routed(spec, bars, START)
ft = sorted((t for r in full.values() for t in r["trades"]), key=lambda t: (t["entry_ts"], t["sleeve"]))
addon_trades = full["AG_CRABEL15_D_GAP1_v4"]["trades"]   # addon trades keep the base sleeve name inside the record; the run key is the addon's
pick = next(t for t in reversed(addon_trades) if pd.Timestamp(t["exit_ts"]) - pd.Timestamp(t["entry_ts"]) >= pd.Timedelta(minutes=30))
cut = pd.Timestamp(pick["entry_ts"]) + pd.Timedelta(minutes=15)
tb = {k: v[v.timestamp_utc <= cut].reset_index(drop=True) for k, v in bars.items()}
part = ep.run_routed(spec, tb, START)
pt = sorted((t for r in part.values() for t in r["trades"]), key=lambda t: (t["entry_ts"], t["sleeve"]))
closed_before = [t for t in ft if pd.Timestamp(t["exit_ts"]) <= cut - pd.Timedelta(minutes=15)]
key = lambda t: (t["sleeve"], t["entry_ts"], t["exit_ts"], t["net"])
out["live_path"] = dict(cut_utc=str(cut), picked_trade=dict(sleeve=pick["sleeve"], entry=pick["entry_ts"], exit=pick["exit_ts"]),
                        open_positions={n: r["position"] for n, r in part.items() if r["position"].get("quantity")},
                        partial_closed_trades=len(pt), full_trades_closed_before_cut=len(closed_before),
                        partial_is_prefix=bool({key(t) for t in closed_before} <= {key(t) for t in pt}),
                        extra_in_partial=[key(t) for t in pt if key(t) not in {key(x) for x in ft}][:5])
print(json.dumps(out, indent=1, default=str))
(ROOT / "reports/CHECK_DPLUS_V4_LIVE_PATH.json").write_text(json.dumps(out, indent=1, default=str))
