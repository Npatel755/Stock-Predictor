"""eval_12 (Claude, 2026-11-11): published "noise area" intraday momentum as a NEW sleeve for the $50K Static Combine. TRAINING 2010-23 only.

SOURCE: Zarattini, Aziz & Barbon (2024), "Beat the Market: An Effective Intraday Momentum Strategy for S&P500 ETF (SPY)", SSRN 4824172.
Not tested before in this repo (grep of lessons/scripts/reports for noise area / Zarattini: no hits). Mechanism differs from the 15-min
price-rule universe: the breakout band is the AVERAGE absolute move from the open AT THAT TIME OF DAY over the last 14 sessions, so it is
calibrated to the intraday volatility smile, and it is checked only every 30 minutes.

PRE-DECLARED (written before any result). Published parameters, nothing tuned. RTH 09:30-16:00 ET, 1-minute bars (bar start stamps).
  O = 09:30 open, PC = prior full session's 16:00 close (PC = O when the contract changed).  m = minute index from 09:30 (bar m closes at 09:31+m).
  sigma(d, m) = mean over the previous 14 full sessions of |close(m) / O - 1|.
  UB = max(O, PC) x (1 + sigma);  LB = min(O, PC) x (1 - sigma).  VWAP from 09:30 on (H+L+C)/3 x volume.
  Checks at the closes of 10:00, 10:30, ..., 15:30 (p = that bar's close). Trailing stop = the closer of {band, VWAP} on the stop side
  (long: max(UB, VWAP) if VWAP < p else UB; short: min(LB, VWAP) if VWAP > p else LB).
  At a check: in a long and p <= stop -> exit; in a short and p >= stop -> exit; then if flat: p > UB -> long, p < LB -> short.
  Fills at the next bar's open; everything flat at the 16:00 close. 1 micro per trade. Full sessions only (>= 385 RTH bars, no
  contract change inside RTH).
  Costs/normalisation exactly as the book (payout_lib): per micro = ((side x (exit - entry) / entry) x TODAY - 2 x 0.5 pt) x MULT - $1.
  MAE per micro on 1-minute bars; risk_today = stop distance at entry (pct) x TODAY x MULT + 1 + 0.75 x MULT (engine formula).
CELLS (4): instrument {MNQ, MES} x stop mode {P = checked only at the 30-min marks, as published; R = resting stop walked on 1-min bars
  at the last check's level, gap-through fills at the bar open}.
GATE 1 (standalone, per cell): net per micro > 0 AND profit factor >= 1.10 in BOTH halves (2010-16, 2017-23), AND the 2010-23 total beats
  >= 190 of 200 random-side placebos (same entries/exits, side drawn at random, seed 12).
GATE 2 (evaluation): the gate-1 survivor with the highest min-half PF (one cell only) joins the eval_8 book as a 1-micro sleeve, priority 12
  in the 1-position router (after v5.3 and the two Codex sleeves), risk <= $300 filter like every other sleeve, sized by the incumbent rule
  (DEF + ENDGAME). ADOPT only if BOTH halves >= incumbent's same half + 1.0 point (54.5 / 65.6 -> 55.5 / 66.6).
"""
import json, sys
import numpy as np, pandas as pd
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT / "scripts")); sys.path.insert(0, str(ROOT / "src"))
import mass_1m_search as m1
import payout_lib as pl

NY = "America/New_York"; H1_END = pd.Timestamp("2017-01-01").date(); LOOK = 14
CHECKS = [29 + 30 * j for j in range(12)]          # bars closing 10:00 .. 15:30


def rth_panel(inst):
    b = m1.load_bars(inst, 1, "2009-11-01", "2024-01-01", "train").reset_index(drop=True)
    assert b.timestamp_utc.max() < pd.Timestamp("2024-01-01", tz="UTC")
    t = b.timestamp_utc.dt.tz_convert(NY); mi = (t.dt.hour * 60 + t.dt.minute - 570).to_numpy()
    b = b[(mi >= 0) & (mi < 390)].copy(); b["m"] = mi[(mi >= 0) & (mi < 390)]; b["d"] = t[b.index].dt.date
    days = []
    for d, g in b.groupby("d", sort=True):
        if len(g) < 385 or g.contract.nunique() != 1 or g.m.iloc[0] != 0: continue
        g = g.set_index("m").reindex(range(390))
        c = g.close.ffill().to_numpy(float); h = g.high.fillna(pd.Series(c, index=g.index)).to_numpy(float)
        l = g.low.fillna(pd.Series(c, index=g.index)).to_numpy(float); o = g.open.fillna(pd.Series(c, index=g.index)).to_numpy(float)
        v = g.volume.fillna(0).to_numpy(float); ts = g.timestamp_utc
        days.append(dict(d=d, o=o, h=h, l=l, c=c, v=v, con=g.contract.dropna().iloc[0], t0=ts.iloc[0].tz_convert(NY)))
    return days


def trades(days, inst, mode):
    rows = []
    mv = np.array([np.abs(x["c"] / x["o"][0] - 1.0) for x in days])
    for i in range(LOOK, len(days)):
        x = days[i]; prev = days[i - 1]; O = x["o"][0]
        PC = prev["c"][-1] if (prev["con"] == x["con"] and (x["d"] - prev["d"]).days <= 4) else O
        sig = mv[i - LOOK:i].mean(axis=0)
        typ = (x["h"] + x["l"] + x["c"]) / 3.0; cv = np.cumsum(x["v"]); vw = np.where(cv > 0, np.cumsum(typ * x["v"]) / np.maximum(cv, 1e-9), x["c"])
        UB = max(O, PC) * (1 + sig); LB = min(O, PC) * (1 - sig)
        pos = 0; e = None; ein = None; stop = None; risk = None; dec = None

        def close_at(j, px, why):
            nonlocal pos, e, ein, stop, risk, dec
            seg_l = np.append(x["l"][ein:min(j, 390)], px); seg_h = np.append(x["h"][ein:min(j, 390)], px)   # bars held fully + the exit fill
            worst = (seg_l.min() - e) / e if pos > 0 else (e - seg_h.max()) / e
            pct = pos * (px - e) / e
            pm = (pct * pl.TODAY[inst] - 2 * pl.ADV) * pl.MULT[inst] - pl.FEE
            mae = min(pm, (min(0.0, worst) * pl.TODAY[inst] - pl.ADV) * pl.MULT[inst])
            tin = x["t0"] + pd.Timedelta(minutes=ein); tout = x["t0"] + pd.Timedelta(minutes=min(j, 390))
            rows.append(dict(inst=inst, side=pos, entry=e, exit=px, tin=tin, tout=tout, dec=dec, stop_pct=risk, per_micro=pm, mae_per_micro=mae, why=why))
            pos = 0; e = None

        def stop_level(m, p):
            if pos > 0: return max(UB[m], vw[m]) if vw[m] < p else UB[m]
            return min(LB[m], vw[m]) if vw[m] > p else LB[m]

        for k, m in enumerate(CHECKS):
            if mode == "R" and pos != 0:          # walk the resting stop from the bar after the last check to this check bar
                lo_m = CHECKS[k - 1] + 1 if k > 0 else 0
                for j in range(max(lo_m, ein), m + 1):     # a stop already through the market fills at the bar open (never better)
                    if pos > 0 and x["l"][j] <= stop: close_at(j, min(stop, x["o"][j]), "stop"); break
                    if pos < 0 and x["h"][j] >= stop: close_at(j, max(stop, x["o"][j]), "stop"); break
            p = x["c"][m]
            if pos != 0:
                s = stop_level(m, p)
                if (pos > 0 and p <= s) or (pos < 0 and p >= s): close_at(m + 1, x["o"][m + 1], "check")
                else: stop = s
            if pos == 0 and m + 1 < 390:
                side = 1 if p > UB[m] else (-1 if p < LB[m] else 0)
                if side:
                    pos = side; ein = m + 1; e = x["o"][m + 1]; dec = x["t0"] + pd.Timedelta(minutes=m + 1)
                    stop = stop_level(m, p); risk = max(abs(e - stop) / e, 0.0005)
        if pos != 0:
            if mode == "R":
                lo_m = max(CHECKS[-1] + 1, ein)
                for j in range(lo_m, 390):
                    if pos > 0 and x["l"][j] <= stop: close_at(j, min(stop, x["o"][j]), "stop"); break
                    if pos < 0 and x["h"][j] >= stop: close_at(j, max(stop, x["o"][j]), "stop"); break
            if pos != 0: close_at(390, x["c"][389], "eod")
    t = pd.DataFrame(rows)
    t["risk_today"] = t.stop_pct * pl.TODAY[inst] * pl.MULT[inst] + 1.0 + 0.75 * pl.MULT[inst]
    return t


def stats(t):
    w = t.per_micro[t.per_micro > 0].sum(); l = -t.per_micro[t.per_micro < 0].sum()
    yrs = t.groupby(t.tout.dt.year).per_micro.sum()
    return dict(n=len(t), net=round(float(t.per_micro.sum()), 0), mean=round(float(t.per_micro.mean()), 2), pf=round(float(w / l), 3) if l > 0 else None,
                years_pos=f"{int((yrs > 0).sum())}/{len(yrs)}", win=round(100 * float((t.per_micro > 0).mean()), 1))


def placebo(t, inst, n=200, seed=12):
    rng = np.random.default_rng(seed); e, x = t.entry.to_numpy(), t.exit.to_numpy(); act = t.per_micro.sum(); beat = 0
    for _ in range(n):
        s = rng.choice([-1, 1], size=len(t))
        tot = (((s * (x - e) / e) * pl.TODAY[inst] - 2 * pl.ADV) * pl.MULT[inst] - pl.FEE).sum(); beat += int(act > tot)
    return beat


out = {"cells": {}}; T = {}
for inst in ("MNQ", "MES"):
    days = rth_panel(inst); print(inst, "full sessions", len(days), days[0]["d"], days[-1]["d"], flush=True)
    for mode in ("P", "R"):
        t = trades(days, inst, mode); t = t[t.tout.dt.date >= pd.Timestamp("2010-06-07").date()].reset_index(drop=True)
        h1 = t.tout.dt.date < H1_END; c = dict(h1=stats(t[h1]), h2=stats(t[~h1]), all=stats(t), placebo_beaten=placebo(t, inst),
                                               exits=t.why.value_counts().to_dict(), med_risk_today=round(float(t.risk_today.median()), 0))
        c["gate1"] = bool(all(c[h]["net"] > 0 and (c[h]["pf"] or 0) >= 1.10 for h in ("h1", "h2")) and c["placebo_beaten"] >= 190)
        out["cells"][f"{inst}_{mode}"] = c; T[f"{inst}_{mode}"] = t; print(inst, mode, c, flush=True)

pas = [k for k, c in out["cells"].items() if c["gate1"]]
out["gate1_pass"] = pas
if not pas:
    print("no cell passed gate 1", flush=True)
else:
    best = max(pas, key=lambda k: min(out["cells"][k]["h1"]["pf"], out["cells"][k]["h2"]["pf"])); out["gate2_cell"] = best
    src = (ROOT / "scripts/eval_9_optimal_sizing_train.py").read_text(encoding="utf-8").split("\n# ---------------- DP")[0]
    E9 = {"__name__": "e12", "__file__": str(ROOT / "scripts/eval_9_optimal_sizing_train.py")}; exec(src, E9)
    evaluate2, DEF_END, table, variant, SLV, A, B = (E9[k] for k in ("evaluate2", "DEF_END", "table", "variant", "SLV", "A", "B"))
    inc = dict(h1=evaluate2(DEF_END, A), h2=evaluate2(DEF_END, B)); print("incumbent", inc, flush=True)
    assert abs(inc["h1"]["pass_"] - 54.5) <= 0.1 and abs(inc["h2"]["pass_"] - 65.6) <= 0.1, "does not reproduce the incumbent"
    cols = SLV[0].columns; t = T[best].copy()
    t["sleeve"] = f"NOISE_{best}"; t["prio"] = 12; t["n_contracts"] = 1.0; t["net_today"] = t.per_micro; t["net_then"] = np.nan
    t = t.reindex(columns=cols)
    E9["TAB"] = table(pd.concat([variant("A")] + SLV + [t], ignore_index=True))
    new = dict(h1=evaluate2(DEF_END, A), h2=evaluate2(DEF_END, B)); print("with", best, new, flush=True)
    out["gate2"] = dict(incumbent=inc, with_sleeve=new, adopt=bool(new["h1"]["pass_"] >= inc["h1"]["pass_"] + 1.0 and new["h2"]["pass_"] >= inc["h2"]["pass_"] + 1.0))
    print("gate2", out["gate2"]["adopt"], flush=True)
(ROOT / "reports/EVAL_12_NOISE_AREA_TRAINING.json").write_text(json.dumps(out, indent=1, default=str))
