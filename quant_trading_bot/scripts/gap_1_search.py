"""gap_1 (protocol research/gap_1/PROTOCOL.md): overnight gap fade / gap-and-go / Globex-range break, 15-min bars incl. Globex,
fixed engine, train 2010-23 (ES/NQ -> MES/MNQ 2019+), placebo, gates, frozen passers validated once on 2024-25."""
import json, sys, itertools
from pathlib import Path
import numpy as np, pandas as pd
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts")); sys.path.insert(0, str(ROOT / "src"))
import mass_1m_search as m1
from quant_futures import ensemble_paper as ep
from quant_futures.session_calendar import apply_early_close
eng = ep.engine(); rng = np.random.default_rng(20261108); N_PLACEBO = 50

def prep(inst, split, lo, hi):
    b = m1.load_bars(inst, 15, lo, hi, split).reset_index(drop=True)
    assert b.timestamp_utc.max() < pd.Timestamp("2026-01-01", tz="UTC")
    loc = b.timestamp_utc.dt.tz_convert("America/New_York"); b["minute"] = (loc.dt.hour * 60 + loc.dt.minute).to_numpy()
    b["tdate"] = (loc + pd.Timedelta(hours=6)).dt.date
    rth = b[(b.minute >= 570) & (b.minute < 960)]
    g = rth.groupby("tdate"); day = pd.DataFrame(dict(rth_close=g.close.last(), rng=g.high.max() - g.low.min()))
    day["prior_close"] = day.rth_close.shift(1); day["datr"] = day.rng.rolling(14).mean().shift(1)
    gx = b[(b.minute >= 1080) | (b.minute < 570)].groupby("tdate"); day["ghigh"] = gx.high.max(); day["glow"] = gx.low.min()
    b = b.merge(day[["prior_close", "datr", "ghigh", "glow"]], left_on="tdate", right_index=True, how="left")
    f = eng["features"](b, 8); b["atr"] = f["atr"]
    o = b[b.minute == 570].set_index("tdate").open; b["open0930"] = b.tdate.map(o)
    b["gap"] = (b.open0930 - b.prior_close) / b.datr
    return b, f

def signals(b, fam, th, confirm=None, win=None):
    sig = np.zeros(len(b), np.int8); m = b.minute.to_numpy(); c = b.close.to_numpy(); o = b.open.to_numpy(); gap = b.gap.to_numpy(); pc = b.prior_close.to_numpy()
    if fam == "A":
        i = (m == 570) & (gap >= th) & (c > pc); sig[i] = -1; i = (m == 570) & (gap <= -th) & (c < pc); sig[i] = 1
    elif fam == "B":
        up = (m == 570) & (gap >= th); dn = (m == 570) & (gap <= -th)
        if confirm: up &= c > o; dn &= c < o
        sig[up] = 1; sig[dn] = -1
    else:
        gh, gl, atr = b.ghigh.to_numpy(), b.glow.to_numpy(), b.atr.to_numpy(); inwin = (m >= 570) & (m < win)
        brk = np.where(inwin & (c > gh + th * atr), 1, np.where(inwin & (c < gl - th * atr), -1, 0))
        first = pd.Series(brk != 0).groupby(b.tdate.to_numpy()).cumsum().to_numpy() == 1  # first break of the session only
        sig[(brk != 0) & first] = brk[(brk != 0) & first]
    return sig

def run_years(data, sig, atr, cfg, years):
    out = {}
    for y in years:
        idx = np.flatnonzero(data["year"] == y)
        if not len(idx): continue
        a, z = int(idx[0]), int(idx[-1]) + 1
        d = {k: np.ascontiguousarray(v[a:z]) for k, v in data.items()}
        d["session"] = pd.factorize(d["session"], sort=False)[0].astype(np.int64); d["contract"] = pd.factorize(d["contract"], sort=False)[0].astype(np.int64)
        r = eng["execute"](d, np.ascontiguousarray(sig[a:z]), np.ascontiguousarray(atr[a:z]), cfg)
        peaks = np.maximum.accumulate(np.r_[50000.0, r["equity"]])[1:]
        out[int(y)] = dict(net=round(float(r["cash"][-1] - 50000.0), 2), dd=round(float(np.max(peaks - r["worst"])), 2), trades=int(len(r["trade_net"])))
    return out

def ecfg(inst, stop, tgt, hold):
    c = eng["execution_cfg"](dict(instrument=inst, max_contracts=1, stop_atr=stop, target_r=tgt, hold_bars=hold, session_start=585, session_end=955, trailing_atr=0.0))
    c.update(commission_per_side=0.61, spread_ticks=1.75 if inst == "MNQ" else 1.0, entry_start=570, entry_end=690, flat_minute=955); return c

GRID = [dict(fam="A", th=th, stop=s, tgt=t, hold=h) for th in (0.5, 1.0, 1.5) for s in (1.0, 1.5) for t in (1, 2) for h in (4, 8)]
GRID += [dict(fam="B", th=th, confirm=cf, stop=1.5, tgt=t, hold=h) for th in (0.5, 1.0, 1.5) for cf in (False, True) for t in (2, 3) for h in (4, 8, 12)]
GRID += [dict(fam="C", th=th, win=w, stop=1.5, tgt=t, hold=h) for th in (0.0, 0.25) for w in (630, 690) for t in (2, 3) for h in (8, 12)]

def placebo(b, sig, fam, win):
    m = b.minute.to_numpy(); elig = np.flatnonzero(m == 570) if fam in "AB" else np.flatnonzero((m >= 570) & (m < win))
    n = int((sig != 0).sum()); p = np.zeros_like(sig)
    if fam == "C":  # one entry per session at most: pick sessions, then a random eligible bar in each
        days = pd.Series(elig).groupby(b.tdate.to_numpy()[elig]).apply(lambda s: s.sample(1, random_state=int(rng.integers(1 << 31))).iloc[0]).to_numpy(); elig = days
    pick = rng.choice(elig, size=min(n, len(elig)), replace=False); p[pick] = rng.choice([-1, 1], size=len(pick)); return p

def gate(years, plac_nets):
    nets = np.array([v["net"] for v in years.values()]); tot = nets.sum(); pos = nets > 0
    share = nets.max() / tot if tot > 0 else 9; tr = sum(v["trades"] for v in years.values()); dd = max(v["dd"] for v in years.values())
    pct = float((np.array(plac_nets) < tot).mean()) if plac_nets else None
    ok = tot > 0 and pos.sum() >= 10 and share <= 0.4 and dd < 2000 and tr >= 150 and (pct is None or pct >= 0.95)
    return dict(total=round(float(tot), 2), years_pos=int(pos.sum()), n_years=len(nets), max_year_share=round(float(share), 2), trades=tr, worst_dd=dd, placebo_pct=pct, passes=bool(ok))

results = []; frozen = []
for inst in ("MNQ", "MES"):
    b, f = prep(inst, "train", "2009-12-01", "2024-01-01"); data = apply_early_close(eng["arrays"](b), b); atr = np.ascontiguousarray(f["atr"]); years = range(2010, 2024)
    for g in GRID:
        sig = signals(b, g["fam"], g["th"], g.get("confirm"), g.get("win")); cfg = ecfg(inst, g["stop"], g["tgt"], g["hold"])
        yr = run_years(data, sig, atr, cfg, years); gt = gate(yr, [])
        if gt["total"] > 0 and gt["years_pos"] >= 9:  # placebo only where it can matter
            pl = [sum(v["net"] for v in run_years(data, placebo(b, sig, g["fam"], g.get("win")), atr, cfg, years).values()) for _ in range(N_PLACEBO)]; gt = gate(yr, pl)
        rec = dict(instrument=inst, **g, by_year=yr, **gt); results.append(rec)
        print(inst, g, gt, flush=True)
        if gt["passes"]: frozen.append(rec)
json.dump(results, open(ROOT / "reports" / "GAP_1_TRAINING.json", "w"), indent=1)
json.dump(frozen, open(ROOT / "reports" / "GAP_1_FROZEN.json", "w"), indent=1)
print("FROZEN", len(frozen), flush=True)
if frozen:
    val = []
    for rec in frozen:
        inst = rec["instrument"]; b, f = prep(inst, "validation", "2023-12-01", "2026-01-01"); data = apply_early_close(eng["arrays"](b), b)
        sig = signals(b, rec["fam"], rec["th"], rec.get("confirm"), rec.get("win"))
        val.append(dict(rec=rec, validation=run_years(data, sig, np.ascontiguousarray(f["atr"]), ecfg(inst, rec["stop"], rec["tgt"], rec["hold"]), (2024, 2025))))
        print("VAL", inst, rec["fam"], rec["th"], val[-1]["validation"], flush=True)
    json.dump(val, open(ROOT / "reports" / "GAP_1_VALIDATION.json", "w"), indent=1)
