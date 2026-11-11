"""xmkt_fx (Claude fork A, 2026-11-11): micro FX futures streams (M6E / M6A / M6B) as a NEW evaluation sleeve. TRAINING 2010-23 only.

DATA: free HistData 1-minute BID bars (scripts/xmkt_fetch_histdata.py -> data/external/xmkt_histdata/), wall clock = New York time with DST,
verified in scripts/xmkt_fx_clock_check.py (reports/xmkt_fx_clock_check.json). DROPPED (rule fixed before results): every year's spring-gap
and fall-gap weeks, plus summer/winter year-regimes failing the +-1 minute 08:30 check (AUD 2010 winter, 2020 winter; GBP 2012 winter, 2020
summer, 2020 winter). Spot is used as a proxy for the CME micro future (forward points move slowly intraday).
TOPSTEP: M6E permitted for the Combine; M6A / M6B on the Launchpad list (help.topstep.com, read 2026-11-11). Flat by 16:10 ET; entries
after the 18:00 ET reopen. All trades here exit by 16:00 ET.
UNIT = 10 micros (EUR: 10 x 12,500 = $12.50 per pip; AUD 10 x 10,000 = $10; GBP 10 x 6,250 = $6.25), so a unit's daily swing is comparable
with the book's. COSTS (directive): per micro per side 1 tick spread + 1 tick slippage + $1.00 commission -> per unit round trip
10 x (4 ticks + $2): EUR $70, AUD $60, GBP $45. (Bid data, so charging the spread on both sides is conservative.) Also REPORTED only: net at
full-size-future costs (1 pip spread + 0.5 pip slippage per side round trip 2 pips, $2.62/side) - not used by any gate.
Session date D = the ET date of 03:00..16:00; Asia range = 19:00 (D-1) .. 03:00.
CELLS (10 per pair, 30 total, fixed before any result):
  LDN_OPP_12 / LDN_OPP_16 / LDN_MID_12 / LDN_MID_16  London breakout of the Asia range: first 1-min close beyond it between 03:00 and 06:00 ->
        enter next open; stop = opposite side (OPP) or range midpoint (MID); exit 12:00 / 16:00; one trade per day.
  NY_1 / NY_2   range 08:00-09:00 / 08:00-10:00; first close beyond it until 12:00 -> next open; stop opposite side; exit 16:00.
  NOISE_03 / NOISE_08   Zarattini-style band from the 03:00 / 08:00 open (14-session mean |close/open - 1| per minute, around
        max/min(open, prior 16:00 close)); checks every 30 minutes; trailing stop = closer of band / running TWAP; exit 16:00.
  TSMOM_20 / TSMOM_60   sign of the last N daily (16:00-16:00) returns; hold 03:00 -> 16:00; stop 1.0 x ATR20 (03:00-16:00 range).
GATES as xmkt_zn: standalone net, PF per half, years positive, 200 random-side placebo (seed 7) REPORTED; eval_harness.screen decides;
screen passers -> Harness().pass_rate(extra, F1 / F2 units) 2-fold, adopt only if both out-of-fold halves >= 55.5 / 66.6.
Run from the scripts folder with `python -P`.
"""
import json, sys
import numpy as np, pandas as pd
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT / "scripts"))
import eval_harness as eh
from xmkt_fx_clock_check import regime_of

NY = "America/New_York"; H1_END = pd.Timestamp("2017-01-01").date()
SPEC = {"eurusd": dict(mult=125000.0, tick=1.25), "audusd": dict(mult=100000.0, tick=1.0), "gbpusd": dict(mult=62500.0, tick=0.625)}
BAD = {"audusd": {(2010, "winter"), (2020, "winter")}, "gbpusd": {(2012, "winter"), (2020, "summer"), (2020, "winter")}, "eurusd": set()}
T03, T08, T09, T10, T06, T12, T16, T19 = 600, 900, 960, 1020, 780, 1140, 1380, 120     # minutes since 17:00 of D-1


def panel(p):
    df = pd.read_parquet(ROOT / f"data/external/xmkt_histdata/{p}_1m_2010_2023.parquet")
    assert df.wall.max() < pd.Timestamp("2024-01-01")
    sh = df.wall + pd.Timedelta(hours=7); df["D"] = sh.dt.date; df["t"] = (sh.dt.hour * 60 + sh.dt.minute).to_numpy()
    REG = regime_of(df.D); out = []
    for D, g in df.groupby("D", sort=True):
        if pd.Timestamp(D).dayofweek >= 5: continue
        reg = REG[D]
        if reg in ("spring_gap", "fall_gap") or (D.year, reg) in BAD[p]: continue
        g = g.drop_duplicates("t").set_index("t").reindex(range(1440))
        if g.close.iloc[T03:T16].isna().sum() > 60 or g.close.iloc[T19:T03].isna().sum() > 120: continue
        c = g.close.ffill().bfill().to_numpy(float)
        o = g.open.fillna(pd.Series(c)).to_numpy(float); h = g.high.fillna(pd.Series(c)).to_numpy(float); l = g.low.fillna(pd.Series(c)).to_numpy(float)
        out.append(dict(D=D, o=o, h=h, l=l, c=c, t0=pd.Timestamp(D).tz_localize(NY) - pd.Timedelta(hours=7)))
    return out


class Book:
    def __init__(self, p):
        s = SPEC[p]; self.mult = s["mult"]; self.rt = 10 * (4 * s["tick"] + 2.0); self.rows = []

    def add(self, x, side, ein, e, stop, jx, px, why):
        seg = np.arange(ein, jx); lo = min(x["l"][seg].min() if len(seg) else px, px); hi = max(x["h"][seg].max() if len(seg) else px, px)
        worst = (lo - e) if side > 0 else (e - hi); pnl = side * (px - e) * self.mult - self.rt
        # NY tz arithmetic: t0 is 17:00 of D-1 local; minutes added in wall time via tz-naive then localise
        base = pd.Timestamp(x["D"]) - pd.Timedelta(hours=7)
        tin = (base + pd.Timedelta(minutes=int(ein))).tz_localize(NY, ambiguous="NaT", nonexistent="NaT")
        tout = (base + pd.Timedelta(minutes=int(jx))).tz_localize(NY, ambiguous="NaT", nonexistent="NaT")
        self.rows.append(dict(tin=tin, tout=tout, side=side, entry=e, exit=px, per_micro=pnl, mae_per_micro=min(pnl, worst * self.mult - self.rt / 2),
                              risk_today=abs(e - stop) * self.mult + self.rt, why=why))

    def walk(self, x, side, ein, stop, jend, why_end="time"):
        e = x["o"][ein]
        for j in range(ein, jend):
            if (side > 0 and x["l"][j] <= stop) or (side < 0 and x["h"][j] >= stop):
                self.add(x, side, ein, e, stop, j, min(stop, x["o"][j]) if side > 0 else max(stop, x["o"][j]), "stop"); return
        self.add(x, side, ein, e, stop, jend, x["c"][jend - 1], why_end)


def orb(S, b, r0, r1, s0, s1, stop_kind, exit_t):
    for x in S:
        H = x["h"][r0:r1].max(); L = x["l"][r0:r1].min()
        cross = np.nonzero((x["c"][s0:s1] > H) | (x["c"][s0:s1] < L))[0]
        if not len(cross): continue
        j = s0 + int(cross[0]); side = 1 if x["c"][j] > H else -1
        stop = (L if side > 0 else H) if stop_kind == "OPP" else (H + L) / 2
        if j + 1 < exit_t: b.walk(x, side, j + 1, stop, exit_t)


def noise(S, b, start):
    mv = []
    for i, x in enumerate(S):
        O = x["o"][start]; mv.append(np.abs(x["c"][start:T16] / O - 1))
        if i < 14: continue
        sig = np.mean(mv[i - 14:i], axis=0); prev = S[i - 1]
        PC = prev["c"][T16 - 1] if (x["D"] - prev["D"]).days <= 4 else O
        UB = max(O, PC) * (1 + sig); LB = min(O, PC) * (1 - sig)
        tp = (x["h"][start:T16] + x["l"][start:T16] + x["c"][start:T16]) / 3; tw = np.cumsum(tp) / np.arange(1, len(tp) + 1)
        pos = 0; ein = None; stop0 = None
        for m in range(29, T16 - start - 30, 30):
            p = x["c"][start + m]
            if pos:
                s = (max(UB[m], tw[m]) if tw[m] < p else UB[m]) if pos > 0 else (min(LB[m], tw[m]) if tw[m] > p else LB[m])
                if (pos > 0 and p <= s) or (pos < 0 and p >= s):
                    b.add(x, pos, ein, x["o"][ein], stop0, start + m + 1, x["o"][start + m + 1], "check"); pos = 0
            if not pos:
                side = 1 if p > UB[m] else (-1 if p < LB[m] else 0)
                if side:
                    pos = side; ein = start + m + 1
                    stop0 = (max(UB[m], tw[m]) if tw[m] < p else UB[m]) if side > 0 else (min(LB[m], tw[m]) if tw[m] > p else LB[m])
        if pos: b.add(x, pos, ein, x["o"][ein], stop0, T16, x["c"][T16 - 1], "eod")


def tsmom(S, b, N):
    ret = []; rng = []
    for i, x in enumerate(S):
        atr = np.mean(rng[-20:]) if len(rng) >= 20 else None
        if len(ret) >= N and atr:
            sg = np.nansum(ret[-N:])
            if sg != 0:
                side = 1 if sg > 0 else -1; e = x["o"][T03]; b.walk(x, side, T03, e - side * atr, T16)
        prev = S[i - 1] if i else None
        ret.append(np.nan if prev is None or (x["D"] - prev["D"]).days > 4 else x["c"][T16 - 1] / prev["c"][T16 - 1] - 1)
        rng.append(x["h"][T03:T16].max() - x["l"][T03:T16].min())


def stats(t):
    w = t.per_micro[t.per_micro > 0].sum(); l = -t.per_micro[t.per_micro < 0].sum(); yrs = t.groupby(t.tout.dt.year).per_micro.sum()
    return dict(n=len(t), net=round(float(t.per_micro.sum())), pf=round(float(w / l), 3) if l > 0 else None, years_pos=f"{int((yrs > 0).sum())}/{len(yrs)}")


CELLS = {"LDN_OPP_12": lambda S, b: orb(S, b, T19, T03, T03, T06, "OPP", T12), "LDN_OPP_16": lambda S, b: orb(S, b, T19, T03, T03, T06, "OPP", T16),
         "LDN_MID_12": lambda S, b: orb(S, b, T19, T03, T03, T06, "MID", T12), "LDN_MID_16": lambda S, b: orb(S, b, T19, T03, T03, T06, "MID", T16),
         "NY_1": lambda S, b: orb(S, b, T08, T09, T09, T12, "OPP", T16), "NY_2": lambda S, b: orb(S, b, T08, T10, T10, T12, "OPP", T16),
         "NOISE_03": lambda S, b: noise(S, b, T03), "NOISE_08": lambda S, b: noise(S, b, T08),
         "TSMOM_20": lambda S, b: tsmom(S, b, 20), "TSMOM_60": lambda S, b: tsmom(S, b, 60)}

if __name__ == "__main__":
    pairs = sys.argv[1:] or ["eurusd", "audusd", "gbpusd"]
    f = ROOT / "reports/xmkt_fx_training.json"; out = json.loads(f.read_text()) if f.exists() else {"cells": {}}
    for p in pairs:
        S = panel(p); print(p, "sessions kept", len(S), S[0]["D"], S[-1]["D"], flush=True)
        for name, fn in CELLS.items():
            b = Book(p); fn(S, b); t = pd.DataFrame(b.rows).dropna(subset=["tin", "tout"])
            t = t[t.tout.dt.date >= pd.Timestamp("2010-06-07").date()].reset_index(drop=True)
            assert t.tout.max() < pd.Timestamp("2024-01-01", tz=NY)
            h1 = t.tout.dt.date < H1_END; rng = np.random.default_rng(7); e, x_ = t.entry.to_numpy(), t.exit.to_numpy(); act = t.per_micro.sum()
            plc = sum(int(act > (rng.choice([-1, 1], size=len(t)) * (x_ - e) * b.mult - b.rt).sum()) for _ in range(200))
            gross_pips = float((t.side * (t.exit - t.entry)).mean() * 1e4)
            pipval = b.mult / 1e4; full_cost_pips = 2.0 + 2 * 2.62 / pipval        # report-only: one full-size future = one unit
            c = dict(h1=stats(t[h1]), h2=stats(t[~h1]), placebo_beaten=plc, gross_pips_per_trade=round(gross_pips, 2),
                     cost_pips_rt=round(b.rt / pipval, 2), fullsize_cost_pips_rt=round(full_cost_pips, 2),
                     fullsize_net_per_trade=round((gross_pips - full_cost_pips) * pipval, 2),
                     med_risk=round(float(t.risk_today.median())), exits=t.why.value_counts().to_dict(),
                     screen=eh.screen(t.groupby(t.tout.dt.date).per_micro.sum(), f"{p}_{name}"))
            out["cells"][f"{p}_{name}"] = c; s = c["screen"]
            print(f"{p} {name:11s} n {len(t):5d} gross {gross_pips:5.2f}p cost {c['cost_pips_rt']}p net {c['h1']['net']:>8} / {c['h2']['net']:>8} "
                  f"PF {c['h1']['pf']} / {c['h2']['pf']} yrs {c['h1']['years_pos']} {c['h2']['years_pos']} plc {plc} | sr {s['sr']} rho {s['rho']} "
                  f"w {s['best_w']} lift {s['lift']} h1 {s['halves']['h1']['lift_at_best_w']} h2 {s['halves']['h2']['lift_at_best_w']} pass {s['screen_pass']}", flush=True)
            t.to_csv(ROOT / f"reports/xmkt_fx_{p}_{name}_trades_training.csv", index=False)
        f.write_text(json.dumps(out, indent=1, default=str))
