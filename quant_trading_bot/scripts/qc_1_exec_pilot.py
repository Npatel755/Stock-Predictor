"""qc_1 T1 (exec_1): passive-limit execution of short-horizon fades on MNQ, Apr-Dec 2023, per research/qc_1/PROTOCOL.md.
Quotes: bbo-1s (bid/ask per second, forward-filled on a regular RTH second grid); trades: 1-s hi/lo/last/vol/pxv.
Passive fill = a later second's trade range crosses strictly through the limit by >= THR ticks within W seconds, else cancel."""
import json, sys, time
from pathlib import Path
import numpy as np, pandas as pd
from numba import njit
ROOT = Path(__file__).resolve().parents[1]
TICK, TV, COMM, SLIP = 0.25, 0.5, 0.61, 1
OUT = ROOT / "reports" / "QC_1_EXEC_PILOT.json"

q = pd.read_parquet(ROOT / "data/market/orderflow/MNQ_c0_bbo-1s_2023.parquet", columns=["ts_recv", "bid_px_00", "ask_px_00"])
q["sec"] = pd.to_datetime(q.ts_recv, utc=True).dt.floor("1s"); q = q[q.sec >= pd.Timestamp("2023-04-01", tz="UTC")]
q = q[(q.bid_px_00 > 0) & (q.ask_px_00 > q.bid_px_00)].drop_duplicates("sec", keep="last")
tr = pd.read_parquet(ROOT / "data/market/orderflow/MNQ_c0_trades_2023-04_2023-12.sec.parquet"); tr["sec"] = tr.ts.dt.floor("1s")
et = q.sec.dt.tz_convert("America/New_York"); q["date"] = et.dt.date
days = sorted(set(q.date))
grid = []
for d in days:
    start = pd.Timestamp(f"{d} 09:30:00", tz="America/New_York").tz_convert("UTC")
    grid.append(pd.DataFrame({"sec": pd.date_range(start, periods=23400, freq="1s"), "date": d}))
grid = pd.concat(grid, ignore_index=True)
g = grid.merge(q[["sec", "bid_px_00", "ask_px_00"]], on="sec", how="left").merge(tr[["sec", "hi", "lo", "last_px", "vol", "pxv"]], on="sec", how="left")
g[["bid_px_00", "ask_px_00"]] = g.groupby("date")[["bid_px_00", "ask_px_00"]].ffill()
g = g[g.bid_px_00.notna()].reset_index(drop=True)
g["day_id"] = pd.factorize(g.date)[0]; g["sod"] = (g.sec.dt.tz_convert("America/New_York").dt.hour * 3600 + g.sec.dt.tz_convert("America/New_York").dt.minute * 60 + g.sec.dt.tz_convert("America/New_York").dt.second)
g["mid"] = (g.bid_px_00 + g.ask_px_00) / 2
g["hi"] = g.hi.fillna(-np.inf); g["lo"] = g.lo.fillna(np.inf)
# 1-min bars from the second grid (completed minutes), session VWAP from trades, ATR14 on 1-min mid bars
g["minute"] = g.sod // 60
m = g.groupby(["day_id", "minute"], sort=True).agg(c=("mid", "last"), h=("mid", "max"), l=("mid", "min"), vol=("vol", "sum"), pxv=("pxv", "sum")).reset_index()
gm = m.groupby("day_id", sort=False)
m["cum_v"] = gm.vol.cumsum(); m["cum_pxv"] = gm.pxv.cumsum(); m["vwap"] = m.cum_pxv / m.cum_v.where(m.cum_v > 0)
prev = gm.c.shift(1); trng = pd.concat([m.h - m.l, (m.h - prev).abs(), (m.l - prev).abs()], axis=1).max(axis=1)
m["atr"] = trng.groupby(m.day_id).transform(lambda s: s.rolling(14, min_periods=14).mean())
m["stretch"] = (m.c - m.vwap) / m.atr; m["mom5"] = (m.c - gm.c.shift(5)) / m.atr
m["sig_sec"] = (m.minute + 1) * 60  # act on the first second after the minute completes
# window: signals 09:45-15:30 ET
m = m[(m.sig_sec >= 9 * 3600 + 45 * 60) & (m.sig_sec <= 15 * 3600 + 30 * 60)]
sec_index = {(int(a), int(b)): i for i, (a, b) in enumerate(zip(g.day_id.to_numpy(), g.sod.to_numpy()))}
def signal_array(kind, thr):
    s = np.zeros(len(g), np.int8); v = m.stretch if kind == "stretch" else m.mom5
    prev_abs = v.abs().groupby(m.day_id).shift(1).fillna(0).to_numpy()   # fire once per threshold crossing, not every minute while stretched
    for d, ss, val, pv in zip(m.day_id.to_numpy(), m.sig_sec.to_numpy(), v.to_numpy(), prev_abs):
        if np.isfinite(val) and abs(val) >= thr and pv < thr:
            i = sec_index.get((int(d), int(ss)))
            if i is not None: s[i] = -1 if val > 0 else 1
    return s
BID, ASK, HI, LO, DAY, SOD = (g[c].to_numpy(np.float64) for c in ("bid_px_00", "ask_px_00", "hi", "lo", "day_id", "sod"))
DAY = DAY.astype(np.int64); SOD = SOD.astype(np.int64)

@njit(cache=True)
def sim(sig, bid, ask, hi, lo, day, sod, W, T, H, thr, passive_entry, stop_ticks, flat_sod):
    n = len(sig); pnl = np.zeros(n); fills = 0; signals = 0; k = 0
    pos = 0; entry = 0.0; pend_dir = 0; pend_px = 0.0; pend_t = -1; ent_t = -1
    for i in range(n):
        if i > 0 and day[i] != day[i - 1]:
            pos = 0; pend_dir = 0   # defensive: positions are flattened before the close below
        if pos != 0:
            exit_px = 0.0; done = False
            if pos > 0:
                if hi[i] >= entry + T * TICK + thr * TICK: exit_px = entry + T * TICK; done = True
                elif (entry - 0.5 * (bid[i] + ask[i])) / TICK >= stop_ticks or i - ent_t >= H * 60 or sod[i] >= flat_sod: exit_px = bid[i] - SLIP * TICK; done = True
            else:
                if lo[i] <= entry - T * TICK - thr * TICK: exit_px = entry - T * TICK; done = True
                elif (0.5 * (bid[i] + ask[i]) - entry) / TICK >= stop_ticks or i - ent_t >= H * 60 or sod[i] >= flat_sod: exit_px = ask[i] + SLIP * TICK; done = True
            if done:
                pnl[k] = pos * (exit_px - entry) / TICK * TV - 2 * COMM; k += 1; pos = 0
            continue
        if pend_dir != 0:
            if i - pend_t > W or sod[i] >= flat_sod: pend_dir = 0
            elif pend_dir > 0 and lo[i] <= pend_px - thr * TICK: pos = 1; entry = pend_px; ent_t = i; fills += 1; pend_dir = 0; continue
            elif pend_dir < 0 and hi[i] >= pend_px + thr * TICK: pos = -1; entry = pend_px; ent_t = i; fills += 1; pend_dir = 0; continue
            else: continue
        if sig[i] != 0 and sod[i] < flat_sod - 300:
            signals += 1
            if passive_entry:
                pend_dir = sig[i]; pend_px = bid[i] if sig[i] > 0 else ask[i]; pend_t = i
            else:
                pos = sig[i]; entry = (ask[i] + SLIP * TICK) if sig[i] > 0 else (bid[i] - SLIP * TICK); ent_t = i; fills += 1
    return pnl[:k], fills, signals

def summarize(pnl_arr, fills, signals, sig_days):
    return dict(net=round(float(pnl_arr.sum()), 2), fills=int(fills), signals=int(signals), per_fill=round(float(pnl_arr.mean()), 3) if len(pnl_arr) else None)

def monthly_pos(sig, W, T, H, thr, passive):
    # recompute with trade exit indices for month attribution: approximate via day of entry -> rerun per month slice
    pos_months = 0; months = sorted(set(pd.to_datetime(g.date).dt.to_period("M")))
    dm = pd.to_datetime(g.date).dt.to_period("M").to_numpy()
    for mo in months:
        mask = dm == mo; idx = np.flatnonzero(mask)
        p, f, s = sim(sig[idx], BID[idx], ASK[idx], HI[idx], LO[idx], DAY[idx], SOD[idx], W, T, H, thr, passive, 12, 15 * 3600 + 55 * 60)
        pos_months += int(p.sum() > 0)
    return pos_months, len(months)

rng = np.random.default_rng(7); results = []; t0 = time.time()
FLAT = 15 * 3600 + 55 * 60
sigs = [("stretch", z) for z in (1.5, 2.0, 2.5)] + [("mom5", k) for k in (2.0, 3.0)]
for kind, th in sigs:
    sig = signal_array(kind, th); nsig = int((sig != 0).sum())
    # placebo signal sets: same count per day, random seconds within the window, random direction
    plc = []
    sig_days = pd.Series(sig != 0).groupby(DAY).sum()
    win = np.flatnonzero((SOD >= 9 * 3600 + 45 * 60) & (SOD <= 15 * 3600 + 30 * 60) & (SOD % 60 == 0))
    for r in range(20):
        s = np.zeros(len(g), np.int8)
        for d, cnt in sig_days.items():
            if cnt == 0: continue
            cand = win[DAY[win] == d]
            pick = rng.choice(cand, size=min(int(cnt), len(cand)), replace=False); s[pick] = rng.choice(np.array([-1, 1], np.int8), size=len(pick))
        plc.append(s)
    for W in (30, 60, 120):
        for T in (8, 16):
            for H in (5, 15):
                p, f, sg = sim(sig, BID, ASK, HI, LO, DAY, SOD, W, T, H, 1, True, 12, FLAT)
                pb, fb, _ = sim(sig, BID, ASK, HI, LO, DAY, SOD, W, T, H, 1, False, 12, FLAT)
                p2, f2, _ = sim(sig, BID, ASK, HI, LO, DAY, SOD, W, T, H, 2, True, 12, FLAT)
                pl = np.array([sim(s, BID, ASK, HI, LO, DAY, SOD, W, T, H, 1, True, 12, FLAT)[0].sum() for s in plc])
                pm, nm = monthly_pos(sig, W, T, H, 1, True)
                rec = dict(signal=kind, thr=th, W=W, T=T, H=H, n_signals=nsig, passive=summarize(p, f, sg, None), marketable=summarize(pb, fb, sg, None),
                           passive_thr2=summarize(p2, f2, sg, None), placebo_mean=round(float(pl.mean()), 2), placebo_sd=round(float(pl.std()), 2),
                           beat_placebo=int((p.sum() > pl).sum()), pos_months=pm, months=nm)
                rec["pass"] = bool(p.sum() > 0 and pm >= 7 and f >= 200 and rec["beat_placebo"] >= 19 and (p.sum() - pl.mean()) >= 2 * TV * max(f, 1))
                results.append(rec)
                print(kind, th, W, T, H, "passive", rec["passive"], "mkt", rec["marketable"]["net"], "thr2", rec["passive_thr2"]["net"], "plc", rec["placebo_mean"], rec["beat_placebo"], "mo", pm, "PASS" if rec["pass"] else "", flush=True)
OUT.write_text(json.dumps(dict(days=len(days), seconds=len(g), results=results), indent=1))
print("DONE", len(results), "configs", sum(r["pass"] for r in results), "pass", round(time.time() - t0), "s")
