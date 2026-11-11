"""Router / per-sleeve-floor fix for the deployed D+ ledgers (Claude, 2026-11-09). TRAINING 2010-23 only.

For every visible D+ candidate, replay 2010-23 through the runner under three settings of its base candidates:
  A current: router strict_1c, policy per-sleeve $2,000 funded floor on
  B router posthoc_1c (research route()), per-sleeve floor on
  C router posthoc_1c, per-sleeve floor off (funded_drawdown 1e9)
and compare with the research numbers in each candidate's provenance. Historical VIX/VIX3M is injected (the live filter fetches 1 year only).
"""
import copy, json
from pathlib import Path
import pandas as pd

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

BASES = ["ag_arch_d_plus", "ag_arch_d_plus_v2", "ag_arch_d_plus_v2_2c", "ag_arch_d_plus_v2_3c", "ag_arch_d_plus_v2_3c_v3"]
TARGETS = {  # research numbers from each candidate's provenance / report (net, trades as reported)
    "ag_arch_d_plus": ("+20,723 / 1,968 trades", 20723.0),
    "ag_arch_d_plus_v2": ("+17,576 / 1,398 trades", 17576.0),
    "ag_arch_d_plus_v2_2c": ("+27,327 / 1,281 trades", 27327.0),
    "ag_arch_d_plus_v2_gapsize": ("+23,142", 23142.0),
    "ag_arch_d_plus_v2_gapsize_3c": ("+49,999 (1,228 base trades)", 49999.0),
    "ag_arch_d_plus_v2_gapsize_3c_v3": ("+70,734 (1,456 base trades)", 70734.0),
}
ORIG = {k: copy.deepcopy(ep.CANDIDATES[k]) for k in BASES}
bars = {}
for k in BASES:
    for sl in ep.CANDIDATES[k]["sleeves"]:
        bars.setdefault(ep.bars_key(sl), bars_for(sl)[0])


def setting(router, floor_on):
    for k in BASES:
        spec = copy.deepcopy(ORIG[k]); spec["router"] = router
        if not floor_on:
            spec["sleeves"] = [dict(sl, funded_drawdown=1e9) for sl in spec["sleeves"]]
        ep.CANDIDATES[k] = spec


def measure(key):
    runs = ep.run_routed(ep.CANDIDATES[key], bars, START)
    tr = [t for r in runs.values() for t in r["trades"]]
    base_names = {sl["name"] for b in BASES for sl in ORIG[b]["sleeves"]}
    return dict(net=round(sum(float(t["net"]) for t in tr), 2), trades=len(tr),
                base_trades=sum(len(r["trades"]) for n, r in runs.items() if n in base_names),
                locks={n: r.get("lock") for n, r in runs.items() if r.get("lock")})


out = {}
for tag, router, floor in (("A_current_strict_floor_on", "strict_1c", True), ("B_posthoc_floor_on", "posthoc_1c", True), ("C_posthoc_floor_off", "posthoc_1c", False)):
    setting(router, floor)
    for key in TARGETS:
        out.setdefault(key, {"research": TARGETS[key][0]})[tag] = measure(key)
        print(tag, key, out[key][tag], flush=True)
for k in BASES:
    ep.CANDIDATES[k] = ORIG[k]
(ROOT / "reports/VERIFY_DPLUS_ROUTER_FIX.json").write_text(json.dumps(out, indent=1, default=str))
print("DONE", flush=True)
