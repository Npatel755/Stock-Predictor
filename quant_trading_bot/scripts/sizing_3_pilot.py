"""sizing_3: 2 contracts when prior-close SKEW < its 20d mean, else 1; overnight dip v2 / All-Weather 1c / book; training 2010-23 only."""
import json, os, sys
from pathlib import Path
import numpy as np, pandas as pd
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts")); sys.path.insert(0, str(ROOT / "src"))
sk = pd.read_csv(ROOT / "data/external/SKEW_History.csv"); sk["DATE"] = pd.to_datetime(sk.DATE); sk = sk.set_index("DATE").SKEW.sort_index(); sk = sk[sk.index < "2024-01-01"]
below = (sk - sk.rolling(20).mean()) < 0
def state_before(dates):
    d = pd.to_datetime(pd.Series(list(dates))).dt.tz_localize(None).dt.normalize()
    pos = np.searchsorted(below.index.to_numpy(), d.to_numpy(), side="left") - 1
    v = below.to_numpy()[np.clip(pos, 0, len(below) - 1)]; v[pos < 0] = False
    return pd.Series(v, index=list(dates))
src = (ROOT / "scripts/overnight_3_pilot.py").read_text().split("\nif __name__")[0].split("\nN = ")[0]
ns = {"__name__": "ov3", "__file__": str(ROOT / "scripts/overnight_3_pilot.py")}; exec(src, ns)
mn, me = ns["nights"]("MNQ"), ns["nights"]("MES")
p_all = ns["pnl"](mn, "MNQ", ex="x0945"); p_all = p_all[p_all.notna()]
dip = ((mn.gap <= -0.5 * mn.sd20) & (me.gap.reindex(mn.index) <= -0.5 * me.sd20.reindex(mn.index))).fillna(False).reindex(p_all.index).fillna(False)
L1 = p_all[dip]; L1.index = pd.to_datetime(pd.Series(list(L1.index))).dt.tz_localize(None).dt.normalize().to_numpy() if getattr(pd.Index(L1.index), "tz", None) else pd.to_datetime(L1.index)
os.environ["SIZING_BUDGET"] = "1e9"
srcs = (ROOT / "scripts/sizing_1_pilot.py").read_text().split("\nfor key in (")[0]
ns1 = {"__file__": str(ROOT / "scripts/sizing_1_pilot.py")}; exec(srcs, ns1)
L2 = ns1["daily"](ns1["run_candidate"]("ag_all_weather_v2", True)); L2.index = pd.to_datetime(L2.index)
assert L1.index.max() < pd.Timestamp("2024-01-01") and L2.index.max() < pd.Timestamp("2024-01-01")
def stats(d, label):
    yr = d.groupby(d.index.year).sum(); eq = d.cumsum(); dd = float((eq.cummax() - eq).max())
    br = ns1["breach"](d) if "breach" in ns1 else None
    r = dict(net=round(float(d.sum()), 2), dd=round(dd, 2), pos_years=int((yr > 0).sum()), max_year_share=round(float(yr.max() / d.sum()), 3) if d.sum() > 0 else None, net_per_dd=round(float(d.sum() / dd), 2), breach=br)
    print(label, r, flush=True); return r
out = {}
for leg, d in (("L1_overnight_v2", L1), ("L2_allweather_1c", L2), ("L3_book", L1.add(L2, fill_value=0.0))):
    s = state_before(d.index).to_numpy()
    out[leg] = dict(base_1c=stats(d, f"{leg} 1c"),
                    skew_below_2c=stats(d * np.where(s, 2.0, 1.0), f"{leg} 2c when SKEW<20d"),
                    control_above_2c=stats(d * np.where(~s, 2.0, 1.0), f"{leg} CONTROL 2c when SKEW>=20d"),
                    share_below=round(float(s.mean()), 3))
Path(ROOT / "reports/SIZING_3_TRAINING.json").write_text(json.dumps(out, indent=1, default=str))
