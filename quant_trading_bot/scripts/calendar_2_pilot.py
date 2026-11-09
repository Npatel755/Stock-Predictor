"""calendar_2 (research/calendar_2/PROTOCOL.md): overnight calendar windows, training 2010-2023 only. Reuses overnight_3 nights()/pnl()/evaluate()."""
import json, sys
from pathlib import Path
import numpy as np, pandas as pd
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT / "scripts"))
src = open(ROOT / "scripts/overnight_3_pilot.py").read().split('\nout = {"train"')[0]
ns = {"__name__": "ov3", "__file__": str(ROOT / "scripts/overnight_3_pilot.py")}; exec(src, ns); nights, pnl, evaluate, SPEC, COMM, SLIP = ns["nights"], ns["pnl"], ns["evaluate"], ns["SPEC"], ns["COMM"], ns["SLIP"]
ns["rng"] = np.random.default_rng(20261109)
csrc = open(ROOT / "scripts/calendar_1_pilot.py").read(); dsrc = "def daysets" + csrc.split("def daysets")[1].split("\ndef run_dayset")[0]
cns = {"np": np, "pd": pd}; exec(dsrc, cns); daysets = cns["daysets"]

def pnl_short(n, prod, ent="e1805", ex="x0930"):
    s = SPEC[prod]; cost = (s["spread"] + 2 * SLIP) * s["tv"] + 2 * COMM
    return (-(n[ex] - n[ent]) / s["tick"] * s["tv"] - cost)

out = {}
N = {p: nights(p) for p in ("MNQ", "MES")}
for prod in ("MNQ", "MES"):
    n = N[prod]; td = sorted(set(d for d in n.index if pd.notna(n.at[d, "rth_open"])) | set(pd.Timestamp(d).date() + pd.Timedelta(days=1) for d in n.index if pd.Timestamp(d).dayofweek == 3 and pd.notna(n.at[d, "x0930"]))); D = daysets(td)
    tdi = np.array(td); pos = np.searchsorted(tdi, n.index.to_numpy(), side="right")
    exit_day = pd.Series([tdi[i] if i < len(tdi) else None for i in pos], index=n.index)
    def into(name): return exit_day.map(D[name]).fillna(False).astype(bool)
    def outof(name): return pd.Series(n.index, index=n.index).map(D[name]).fillna(False).astype(bool)
    d4 = (n.gap <= -0.5 * n.sd20).fillna(False)
    W = {"W1_into_tom": into("tom"), "W2_into_month_end": into("month_end"), "W3_into_opex": into("opex"), "W4_out_of_pre_holiday": outof("pre_holiday"), "W5_tom_and_dip": into("tom") & d4,
         "W0_all_nights": pd.Series(True, index=n.index), "W6_non_tom": ~into("tom")}
    for ex in ("x0930", "x0945"):
        full = pnl(n, prod, ex=ex); fulls = pnl_short(n, prod, ex=ex)
        for name, mask in W.items():
            r = evaluate(n, full, mask, None, pnl_full=full); out[f"{prod}_{name}_{ex}_long"] = r; print(prod, name, ex, "L", {k: v for k, v in r.items() if k != "by_year"}, flush=True)
            if name.startswith(("W1", "W2", "W3", "W4")) and ex == "x0930":
                r = evaluate(n, fulls, mask, None, pnl_full=fulls); out[f"{prod}_{name}_{ex}_short"] = r; print(prod, name, ex, "S", {k: v for k, v in r.items() if k != "by_year"}, flush=True)
json.dump(out, open(ROOT / "reports/CALENDAR_2_TRAINING.json", "w"), indent=1, default=str); print("DONE")
