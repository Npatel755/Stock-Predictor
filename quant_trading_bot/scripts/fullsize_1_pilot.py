"""fullsize_1 (research/fullsize_1/PROTOCOL.md): re-score F2 (NQ/ES divergence two-sided), F3 (composite B, D) and F4 (AG morning trend lb16, fixed 15m
momentum lb24) at full-size NQ economics: tick $5, spread 1 tick, slippage 1 tick/side, commission $2.50/side, funded lock $2k / $400 day. Training 2010-23 only.
Reuses the signal construction of composite_1_pilot.py (S1 divergence, S2 Crabel, S3 VIX crush) by importing it with its run disabled."""
import json, sys, importlib.util
from pathlib import Path
import numpy as np, pandas as pd
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT / "scripts")); sys.path.insert(0, str(ROOT / "src"))
src = (ROOT / "scripts/composite_1_pilot.py").read_text().split("out = dict(train=evaluate(")[0]
ns = {"__file__": str(ROOT / "scripts/composite_1_pilot.py")}; exec(src, ns)
eng, m1, apply_early_close, signals, variants = ns["eng"], ns["m1"], ns["apply_early_close"], ns["signals"], ns["variants"]
NQ = dict(tick=0.25, multiplier=20.0, spread_ticks=1, slippage_ticks=1, commission_per_side=2.50)
def run_nq(bars, sig, atr, p, entry_start, entry_end, lo_year=2010):
    data = apply_early_close(eng["arrays"](bars), bars)
    cfg = eng["execution_cfg"](dict(p, instrument="MNQ", max_contracts=1, session_start=600, session_end=945, family="trend", lookback=8, threshold=0.0, trailing_atr=0.0))
    cfg.update(NQ); cfg.update(entry_start=entry_start, entry_end=entry_end, flat_minute=955, max_gap_minutes=20 if entry_start == 585 else 60)
    out = {}
    for y in sorted(set(data["year"])):
        if y < lo_year: continue
        idx = np.flatnonzero(data["year"] == y); a, b = int(idx[0]), int(idx[-1]) + 1
        d = {k: np.ascontiguousarray(v[a:b]) for k, v in data.items()}; d["session"] = pd.factorize(d["session"], sort=False)[0].astype(np.int64); d["contract"] = pd.factorize(d["contract"], sort=False)[0].astype(np.int64)
        r = eng["execute"](d, np.ascontiguousarray(sig[a:b]), np.ascontiguousarray(atr[a:b]), cfg)
        peaks = np.maximum.accumulate(np.r_[50000.0, r["equity"]])[1:]
        out[int(y)] = dict(net=round(float(r["cash"][-1] - 50000.0), 2), trades=int(len(r["trade_net"])), dd=round(float(np.max(peaks - r["worst"])), 2), breach=bool(np.any(r["funded_failed"])), lock=str(r["lock_reason"]) if r["lock_reason"] is not None else None)
    return out
def summ(o, label):
    t = sum(v["net"] for v in o.values()); tr = sum(v["trades"] for v in o.values())
    s = dict(label=label, total=round(t, 2), trades=tr, per_trade=round(t / tr, 2) if tr else None, pos_years=int(sum(v["net"] > 0 for v in o.values())), pre2020=round(sum(v["net"] for y, v in o.items() if y < 2020), 2),
             max_year_share=round(max(v["net"] for v in o.values()) / t, 3) if t > 0 else None, worst_year_dd=max(v["dd"] for v in o.values()), breach_years=int(sum(v["breach"] for v in o.values())), by_year={y: (v["net"], v["trades"], v["dd"]) for y, v in o.items()})
    print(label, {k: v for k, v in s.items() if k != "by_year"}, flush=True); return s
res = {}
nq, sod, day, ATR, S = signals("train", "2009-11-01", "2024-01-01"); at = sod == 585; V = variants(S)
res["F2_divergence_two_sided"] = summ(run_nq(nq, np.where(at, day.map(V["A_any_two_sided"] * 0 + pd.Series(S.s1, index=S.index)).fillna(0).to_numpy(), 0).astype(np.int8), ATR, dict(stop_atr=2.0, target_r=4.0, hold_bars=12), 585, 585), "F2 NQ/ES divergence two-sided @NQ")
for k in ("B_any_long_only", "D_two_agree_long_only"):
    res[f"F3_{k}"] = summ(run_nq(nq, np.where(at, day.map(V[k]).fillna(0).to_numpy(), 0).astype(np.int8), ATR, dict(stop_atr=1.5, target_r=4.0, hold_bars=20), 585, 585), f"F3 composite {k} @NQ")
# F4a fixed 15m momentum lb24 (anomaly_1 rule): sign of 24-bar return, entries 09:45-15:30, stop 2 ATR, 3R, hold 24
mom = np.sign(np.nan_to_num((nq.close / nq.close.shift(24) - 1).to_numpy())).astype(np.int8); win = (sod >= 585) & (sod < 930)
res["F4a_momentum15_lb24"] = summ(run_nq(nq, np.where(win, mom, 0).astype(np.int8), ATR, dict(stop_atr=2.0, target_r=3.0, hold_bars=24), 585, 915), "F4a 15m momentum lb24 @NQ")
# F4b AG morning EWMA trend lb16 th0.75 on 30m bars
b30 = m1.load_bars("MNQ", 30, "2009-11-01", "2024-01-01", "train").reset_index(drop=True)
c = b30.close.astype(float); h, l = b30.high.astype(float), b30.low.astype(float); prev = c.shift(1)
atr30 = pd.concat((h - l, (h - prev).abs(), (l - prev).abs()), axis=1).max(axis=1).rolling(14, min_periods=14).mean()
trend = (c.ewm(span=8, adjust=False, min_periods=8).mean() - c.ewm(span=16, adjust=False, min_periods=16).mean()) / atr30
sig30 = np.where(trend >= 0.75, 1, np.where(trend <= -0.75, -1, 0)).astype(np.int8)
res["F4b_ag_morning_trend_lb16"] = summ(run_nq(b30, sig30, np.nan_to_num(atr30.to_numpy()).astype(np.float32), dict(stop_atr=1.5, target_r=3.5, hold_bars=8), 570, 690), "F4b AG morning trend lb16 @NQ (30m)")
json.dump(res, open(ROOT / "reports/FULLSIZE_1_TRAINING.json", "w"), indent=1, default=str); print("DONE")
