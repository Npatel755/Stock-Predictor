"""payout_4 (Claude, 2026-11-10): day-lock / partial banking on D+ v4 to turn give-back days into $150 days. TRAINING 2010-23 only.

PRE-DECLARED (written before any result):
  Mechanism: v4's winners are mostly time/session exits (Devin, payout_1); 22.5% of D+ winners give back >= half their peak. Locking the day
  once realised + open P&L first reaches L converts "was +$150, ended +$40 / -$100" days into qualifying days, at the cost of capping big
  winners that fund the losing days. Payouts need profit, so payouts/yr (not $150 days alone) is the target metric.
  Base: exact v4 trades (dplus_7e routed 3c v3 trades, 4 micros on gap-continuation Crabel, $600 account-level daily stop).
  Cells: B0 v4 as is | L160 / L200 / L300: close everything when the day reaches +$L net, no more entries that day |
         P160: bank half the position (k = n/2) once realised + k-contract open profit reaches +$160, move the rest to breakeven (entry, filled 2 ticks
         adverse), no new entries after the bank.
  Fills: lock exits at the trigger price minus 2 ticks adverse (engine convention); checks use 1-min bars from the entry minute up to (not
  including) the engine's exit bar (conservative: no lock inside the exit bar); same-minute BE stop after a bank uses the OHLC path rule.
  Payout policies: W0 withdraw all profit at each payout; W1 keep a $1,000 cushion (withdraw only above it). Static -$2,000 floor, account
  restarts after a breach (counted).
  Gate for adoption: payouts/yr (W1) > B0, 0 days <= -$1,000, blowups/yr <= B0, and the cell beats B0's $150 days in both 2010-19 and 2020-23.
"""
import json, math
from pathlib import Path
import numpy as np, pandas as pd, pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parents[1]
P = (ROOT / "scripts/dplus_7e_pilot.py").read_text(encoding="utf-8").split("\nout = {}")[0]
ns = {"__file__": str(ROOT / "scripts/dplus_7e_pilot.py")}
exec(P, ns)
tr, gs, NY = ns["tr"], ns["gs"], ns["NY"]
SPL = ROOT / "data/market/GLBX-20261106-FX6FM5XWUX-v3/splits"
MULT = {"MNQ": 2.0, "MES": 5.0}; ADV = 0.5; FEE = 1.0   # 2 ticks adverse per exit, $1 commission per contract round trip (engine)


def one_min(mini, micro):
    parts = []
    for sym, lo, hi in ((mini, "2010-01-01", "2019-01-01"), (micro, "2019-01-01", "2024-01-01")):
        t = pq.read_table(SPL / sym / "train.parquet", columns=["timestamp_utc", "open", "high", "low", "close"]).to_pandas()
        parts.append(t[(t.timestamp_utc >= pd.Timestamp(lo, tz="UTC")) & (t.timestamp_utc < pd.Timestamp(hi, tz="UTC"))])
    b = pd.concat(parts).drop_duplicates("timestamp_utc").sort_values("timestamp_utc")
    assert b.timestamp_utc.max() < pd.Timestamp("2024-01-01", tz="UTC")
    return dict(ts=b.timestamp_utc.astype("int64").to_numpy(), o=b.open.to_numpy(), h=b.high.to_numpy(), l=b.low.to_numpy(), c=b.close.to_numpy())


B = {"MNQ": one_min("NQ", "MNQ"), "MES": one_min("ES", "MES")}

# ---- v4 trade list (account stop applied exactly as in dplus_7e / the runner)
rows = []
for t in tr:
    tin = pd.Timestamp(t["entry_ts"]).tz_convert(NY); tout = pd.Timestamp(t["exit_ts"]).tz_convert(NY)
    inst = "MES" if "MES" in t["sleeve"] else "MNQ"
    cont = "CRABEL" in t["sleeve"] and int(t["side"]) * gs.get(tin.date(), 0) >= 0
    n = int(t["qty"]) * (4.0 / 3.0 if cont else 1.0)   # v4 = base qty x 4/3 on continuation (research + runner addon), fractional where qty < 3
    rows.append(dict(tin=tin, tout=tout, day=tout.date(), eday=tin.date(), inst=inst, side=int(t["side"]), n=n,
                     e=float(t["entry_price"]), x=float(t["exit_price"]), net=float(t["net"]) * (n / int(t["qty"]))))
rows.sort(key=lambda r: r["tin"])
v4 = []
for r in rows:
    if sum(q["net"] for q in v4 if q["day"] == r["eday"] and q["tout"] <= r["tin"]) <= -600.0:
        continue
    v4.append(r)
for r in v4:   # sanity: price formula reproduces the scaled engine net
    assert abs(r["side"] * (r["x"] - r["e"]) * MULT[r["inst"]] * r["n"] - FEE * r["n"] - r["net"]) < 0.02, r


def pnl(r, px, q):
    """Net of q contracts of trade r exited at raw level px (2 ticks adverse applied)."""
    return q * (r["side"] * (px - r["side"] * ADV - r["e"]) * MULT[r["inst"]] - FEE)


def simulate(mode, L):
    """mode: 'none' | 'full' | 'partial'. Returns day P&L series (by ET exit date) over the v4 trade list."""
    day_pnl, locked = {}, set()
    for r in v4:
        d = r["eday"]
        if mode != "none" and d in locked:
            continue
        realised = day_pnl.get(d, 0.0)
        if mode == "none":
            day_pnl[r["day"]] = day_pnl.get(r["day"], 0.0) + r["net"]; continue
        b = B[r["inst"]]; i0 = int(np.searchsorted(b["ts"], r["tin"].value)); i1 = int(np.searchsorted(b["ts"], r["tout"].value))
        n, s, m = r["n"], r["side"], MULT[r["inst"]]
        k = n if mode == "full" else n / 2.0
        # price at which realised + k contracts' net reaches L
        need = (L - realised) / k + FEE
        p_star = r["e"] + s * (need / m + ADV)
        out = None
        for i in range(i0, i1):
            fav = b["h"][i] if s > 0 else b["l"][i]
            if (fav >= p_star) if s > 0 else (fav <= p_star):
                out = i; break
        if out is None:
            day_pnl[r["day"]] = day_pnl.get(r["day"], 0.0) + r["net"]; continue
        banked = pnl(r, p_star, k)
        rest = n - k; rest_pnl = 0.0
        if rest:
            be = r["e"]; hit = False
            o, h, l, c = b["o"][out], b["h"][out], b["l"][out], b["c"][out]
            # same minute: up bar O-L-H-C (low before high), down bar O-H-L-C (high before low)
            if s > 0 and c < o and l <= be: hit = True
            if s < 0 and c > o and h >= be: hit = True
            j = out + 1
            while not hit and j < i1:
                if (b["l"][j] <= be) if s > 0 else (b["h"][j] >= be): hit = True; break
                j += 1
            rest_pnl = pnl(r, be, rest) if hit else (r["side"] * (r["x"] - r["e"]) * m - FEE) * rest
        total = banked + rest_pnl
        day_pnl[d] = day_pnl.get(d, 0.0) + total
        locked.add(d)
    s = pd.Series(day_pnl).sort_index()
    return s


def account(day, cushion):
    bal = 0.0; good = 0; pays = []; blow = 0
    for p in day.to_numpy():
        bal += p
        if bal <= -2000.0: blow += 1; bal = 0.0; good = 0; continue
        good += p >= 150
        if good >= 5:
            w = bal - cushion
            if w > 0: pays.append(w); bal -= w; good = 0
    return round(len(pays) / 14.0, 2), round(float(np.median(pays)), 0) if pays else 0, round(blow / 14.0, 2), round(float(sum(pays)), 0)


def summ(day):
    yrs = pd.DatetimeIndex(pd.to_datetime(pd.Series(day.index).astype(str))).year
    q = pd.Series((day >= 150).to_numpy(), index=yrs).groupby(level=0).sum().reindex(range(2010, 2024), fill_value=0)
    early = yrs < 2020; yr_net = pd.Series(day.to_numpy(), index=yrs).groupby(level=0).sum()
    w0 = account(day, 0.0); w1 = account(day, 1000.0)
    return dict(net=round(float(day.sum()), 2), days150_per_year=round(float(q.mean()), 1),
                days150_2010_19=round(float(q[q.index < 2020].mean()), 1), days150_2020_23=round(float(q[q.index >= 2020].mean()), 1),
                net_2010_19=round(float(day[early].sum()), 0), net_2020_23=round(float(day[~early].sum()), 0), pos_years=f"{int((yr_net > 0).sum())}/14",
                worst_day=round(float(day.min()), 2), days_le_minus_1000=int((day <= -1000).sum()),
                W0_payouts_per_year=w0[0], W0_median_payout=w0[1], W0_blowups_per_year=w0[2], W0_total_withdrawn=w0[3],
                W1_payouts_per_year=w1[0], W1_median_payout=w1[1], W1_blowups_per_year=w1[2], W1_total_withdrawn=w1[3])


cells = {"B0 v4 as is": ("none", 0), "L160 full day-lock": ("full", 160.0), "L200 full day-lock": ("full", 200.0),
         "L300 full day-lock": ("full", 300.0), "P160 bank half, rest to breakeven": ("partial", 160.0)}
out = {}
for name, (mode, L) in cells.items():
    out[name] = summ(simulate(mode, L))
    r = out[name]
    print(f"{name:36s} net {r['net']:>10,.0f} | $150d/yr {r['days150_per_year']:>5} ({r['days150_2010_19']}/{r['days150_2020_23']}) | "
          f"W0 {r['W0_payouts_per_year']}/yr med {r['W0_median_payout']} blow {r['W0_blowups_per_year']} | "
          f"W1 {r['W1_payouts_per_year']}/yr med {r['W1_median_payout']} blow {r['W1_blowups_per_year']} tot {r['W1_total_withdrawn']:,.0f} | "
          f"worst {r['worst_day']} | <=-1k {r['days_le_minus_1000']} | yrs+ {r['pos_years']}", flush=True)
b0 = out["B0 v4 as is"]
for name, r in out.items():
    r["gate"] = bool(name != "B0 v4 as is" and r["W1_payouts_per_year"] > b0["W1_payouts_per_year"] and r["days_le_minus_1000"] == 0
                     and r["W1_blowups_per_year"] <= b0["W1_blowups_per_year"] and r["days150_2010_19"] > b0["days150_2010_19"]
                     and r["days150_2020_23"] > b0["days150_2020_23"])
(ROOT / "reports/PAYOUT_4_DAYLOCK_TRAINING.json").write_text(json.dumps(out, indent=1))
print("gates:", {k: v["gate"] for k, v in out.items()})
