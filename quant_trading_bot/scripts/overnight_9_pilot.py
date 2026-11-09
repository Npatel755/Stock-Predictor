"""overnight_9: intrabar protective stops / late gap-fill exit for overnight_dip_v2 on the 1-min path; training 2010-23 only."""
import json, sys
from pathlib import Path
import numpy as np, pandas as pd
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT / "scripts")); sys.path.insert(0, str(ROOT / "src"))
src = (ROOT / "scripts/overnight_3_pilot.py").read_text().split("\nif __name__")[0].split("\nN = ")[0]
ns = {"__name__": "ov3", "__file__": str(ROOT / "scripts/overnight_3_pilot.py")}; exec(src, ns)
m1 = ns["m1"]; SPEC, SLIP, COMM = ns["SPEC"], ns["SLIP"], ns["COMM"]
mn, me = ns["nights"]("MNQ"), ns["nights"]("MES")
dip = ((mn.gap <= -0.5 * mn.sd20) & (me.gap.reindex(mn.index) <= -0.5 * me.sd20.reindex(mn.index))).fillna(False)
nights = mn[dip & mn.e1805.notna() & mn.x0945.notna()]
print("dip nights", len(nights), flush=True)
b = m1.load_bars("MNQ", 1, "2010-01-01", "2024-01-01", "train")[["timestamp_utc", "open", "high", "low", "close"]]
assert b.timestamp_utc.max() < pd.Timestamp("2024-01-01", tz="UTC")
et = pd.to_datetime(b.timestamp_utc, utc=True).dt.tz_convert("America/New_York"); b["sod"] = (et.dt.hour * 60 + et.dt.minute).to_numpy(); b["date"] = et.dt.date.to_numpy()
dates = sorted(set(b.date)); prev = {d: p for p, d in zip(dates[:-1], dates[1:])}
b["nk"] = np.where(b.sod >= 1080, b.date, np.where(b.sod <= 600, pd.Series(b.date).map(prev).to_numpy(), None))
path = {k: g for k, g in b[b.nk.notna() & ((b.sod >= 1085) | (b.sod < 585))].groupby("nk") if k in nights.index}
s = SPEC["MNQ"]; tv, tick, half = s["tv"], s["tick"], (s["spread"] / 2 + SLIP) * s["tick"]
def simulate(rule, k=None):
    out = {}; hits = 0
    for key, row in nights.iterrows():
        g = path.get(key)
        if g is None: continue
        entry = row.e1805 + half; exit_px = row.x0945 - half; reason = "0945"
        if rule == "stop":
            stop = row.e1805 * (1 - k * row.sd20); lows = g.low.to_numpy(); sods = g.sod.to_numpy()
            m = (lows <= stop) & ((sods >= 1086) | (sods < 585))
            if m.any(): exit_px = stop - half; reason = "stop"; hits += 1
        elif rule == "fill0830":
            sub = g[(g.sod >= 510) & (g.sod < 585)]
            if (sub.high.to_numpy() >= row.ref_close).any(): exit_px = row.ref_close - half; reason = "fill"; hits += 1
        out[key] = (exit_px - entry) / tick * tv - 2 * COMM
    return pd.Series(out), hits
def marked_dd(p):
    """closed equity with each night marked at its session low (low_night) before the close, as in book_1."""
    eq = p.cumsum(); low_mark = eq - p + ((nights.low_night.reindex(p.index) - half - (nights.e1805.reindex(p.index) + half)) / tick * tv - 2 * COMM)
    return float((eq.cummax() - np.minimum(eq, low_mark)).max())
def stats(p, hits):
    yrs = nights.year.reindex(p.index); yr = p.groupby(yrs).sum(); eq = p.cumsum()
    return dict(net=round(float(p.sum()), 2), nights=int(len(p)), per=round(float(p.mean()), 2), pos_years=int((yr > 0).sum()), max_year_share=round(float(yr.max() / p.sum()), 3) if p.sum() > 0 else None,
                closed_dd=round(float((eq.cummax() - eq).max()), 2), marked_dd=round(marked_dd(p), 2), worst=round(float(p.min()), 2), hits=hits, pre2020=round(float(yr[yr.index < 2020].sum()), 2))
res = {}
base, _ = simulate("base"); res["v2_base"] = stats(base, 0); print("v2_base", res["v2_base"], flush=True)
for k in (1.0, 1.5, 2.0):
    p, h = simulate("stop", k); res[f"S_stop_{k}sd"] = stats(p, h); print(f"S_stop_{k}sd", res[f"S_stop_{k}sd"], flush=True)
p, h = simulate("fill0830"); res["F1_fill_after_0830"] = stats(p, h); print("F1_fill_after_0830", res["F1_fill_after_0830"], flush=True)
b0 = res["v2_base"]
for kk, r in res.items():
    if kk != "v2_base": r["pass"] = bool(r["net"] >= 0.9 * b0["net"] and r["marked_dd"] <= 0.9 * b0["marked_dd"] and r["pos_years"] >= 12 and (r["max_year_share"] or 1) <= 0.4)
Path(ROOT / "reports/OVERNIGHT_9_TRAINING.json").write_text(json.dumps(res, indent=1, default=str)); print({k: v.get("pass") for k, v in res.items()})
