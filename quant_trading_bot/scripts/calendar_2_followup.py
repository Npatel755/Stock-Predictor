import json, sys
from pathlib import Path
import numpy as np, pandas as pd
ROOT = Path("/home/ubuntu/repos/csr-codex/quant_trading_bot"); sys.path.insert(0, str(ROOT / "scripts"))
src = open(ROOT / "scripts/overnight_3_pilot.py").read().split('\nout = {"train"')[0]
ns = {"__name__": "ov3", "__file__": str(ROOT / "scripts/overnight_3_pilot.py")}; exec(src, ns); nights, pnl = ns["nights"], ns["pnl"]
csrc = open(ROOT / "scripts/calendar_1_pilot.py").read(); dsrc = "def daysets" + csrc.split("def daysets")[1].split("\ndef run_dayset")[0]
cns = {"np": np, "pd": pd}; exec(dsrc, cns); daysets = cns["daysets"]; rng = np.random.default_rng(7)
out = {}
for prod in ("MNQ", "MES"):
    n = nights(prod); td = sorted(set(d for d in n.index if pd.notna(n.at[d, "rth_open"])) | set(pd.Timestamp(d).date() + pd.Timedelta(days=1) for d in n.index if pd.Timestamp(d).dayofweek == 3 and pd.notna(n.at[d, "x0930"]))); D = daysets(td)
    tdi = np.array(td); pos = np.searchsorted(tdi, n.index.to_numpy(), side="right"); exit_day = pd.Series([tdi[i] if i < len(tdi) else None for i in pos], index=n.index)
    print(prod, "opex days", int(D["opex"].sum()), "exit_day weekday counts", pd.Series([pd.Timestamp(x).dayofweek for x in exit_day.dropna()]).value_counts().to_dict(), "sample opex", list(D["opex"][D["opex"]].index[:3]), "sample exit", list(exit_day.iloc[:3]), flush=True)
    w3 = exit_day.map(D["opex"]).fillna(False).astype(bool); print(prod, "W3 nights", int(w3.sum()), flush=True)
    d4 = (n.gap <= -0.5 * n.sd20).fillna(False); tom = exit_day.map(D["tom"]).fillna(False).astype(bool); w5 = tom & d4
    for ex in ("x0930", "x0945"):
        p = pnl(n, prod, ex=ex); pd4 = p[d4 & p.notna()]; p5 = p[w5 & p.notna()]; yrs = n.year
        cnt = yrs.loc[p5.index].groupby(yrs.loc[p5.index]).size(); plc = []
        for _ in range(200):
            pick = np.concatenate([rng.choice(pd4.index[yrs.loc[pd4.index] == y], size=min(int(c), int((yrs.loc[pd4.index] == y).sum())), replace=False) for y, c in cnt.items()])
            plc.append(float(pd4.loc[pick].sum()))
        rest = pd4.drop(p5.index); r = dict(w5_net=round(float(p5.sum()), 2), w5_n=int(len(p5)), w5_per=round(float(p5.mean()), 2), d4_per=round(float(pd4.mean()), 2), d4_rest_per=round(float(rest.mean()), 2), beat_d4_subsets=int(sum(float(p5.sum()) > x for x in plc)), plc_mean=round(float(np.mean(plc)), 2))
        if w3.sum(): 
            p3 = p[w3 & p.notna()]; r.update(w3_net=round(float(p3.sum()), 2), w3_n=int(len(p3)), w3_per=round(float(p3.mean()), 2))
        out[f"{prod}_{ex}"] = r; print(prod, ex, r, flush=True)
json.dump(out, open(ROOT / "reports/CALENDAR_2_FOLLOWUP.json", "w"), indent=1, default=str); print("DONE")
