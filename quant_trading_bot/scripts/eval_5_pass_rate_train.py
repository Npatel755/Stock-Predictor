"""eval_5 (Claude, 2026-11-10): maximise P(pass the $50K Static Combine within 90 days). TRAINING 2010-23 only.

PRE-DECLARED (before results). Simulator = v53 eval_track rules (1-minute MAE floor check, DLL $1,000 flatten, 55% consistency, 90 calendar
days, overnight dip on, account stop $700, size per trade min(k x base, floor($900 / stop risk))); one attempt per session 2010-06..2023-09.
Base = v5.3 book at k = 3. A timeout is worth the same as a failure (the $149 attempt is lost), which is why the endgame family exists.
Families:
  B ENDGAME: k = 3, but from calendar day D of the attempt, while the balance is still more than G below the target, use k_end.
     D in {45, 60, 75} x G in {$1,000, $2,000} x k_end in {5, 6} = 12 cells.
  C EQUAL RISK: every trade (and the overnight leg) sized max(1, min(12, floor(R / stop risk per micro))), R in {$300, $450, $600} = 3 cells.
  D BOOK at k = 3: v5.2 (with TRD30PM) | v5.3 + TRD30_D | v5.3 + BRK30 | v5.3 + TRD30_D + BRK30 (replicated engine sleeves, ranked after
     v5.3's in the 1-position router) = 4 cells.
SELECTION per family on starts 2010-06..2016-12 (highest pass share). CONFIRMATION on 2017-01..2023-09: the family winner's pass share must
be >= base + 2 points there. Then ONE combination cell of the confirmed family winners (if two or more confirm), confirmed the same way.
Also reported for every cell: fail / timeout shares and median days to pass.
"""
import json
import numpy as np, pandas as pd
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
src = (ROOT / "scripts/v53_improve_train.py").read_text(encoding="utf-8").split("\nout = {}\n")[0]
V = {"__name__": "v53e", "__file__": str(ROOT / "scripts/v53_improve_train.py")}; exec(src, V)
pl, base0, variant, NIGHTS, SESS, mae_pct, NIGHT_RISK = (V[k] for k in ("pl", "base0", "variant", "NIGHTS", "SESS", "mae_pct", "NIGHT_RISK"))
P10 = V["P10"]; ep, bars_for, START = P10["ep"], P10["bars_for"], P10["START"]
H1_END = pd.Timestamp("2017-01-01").date()

EXTRA = {}
for key, (sl, prio) in {"TRD30_D": (dict(ep._AG_TRD30_D, name="AG_TRD30_D_1c"), 4), "BRK30": (dict(ep._AG_BRK30, name="AG_BRK30_1c"), 5)}.items():
    x = pl.price_normalize(pl.sleeve_trades(ep, bars_for, START, sl, prio, True)); x["n_contracts"] = 1.0
    x["mae_per_micro"] = [(mae_pct(r.inst, r.tin, r.tout, r.side, r.entry) * pl.TODAY[r.inst] - pl.ADV) * pl.MULT[r.inst] for r in x.itertuples()]
    EXTRA[key] = x[base0.columns]


def book(name):
    if name == "v5.2": return base0
    d = variant("A")
    for k in ("TRD30_D", "BRK30"):
        if k in name: d = pd.concat([d, EXTRA[k]], ignore_index=True)
    return d


def table(d):
    r = pl.route(d[d.risk_today <= 300.0]).copy(); r["per_micro"] = r.net_today / r.n_contracts
    t = pd.concat([r[["tin", "tout", "per_micro", "mae_per_micro", "n_contracts", "risk_today"]],
                   NIGHTS.assign(n_contracts=1.0, risk_today=NIGHT_RISK)[["tin", "tout", "per_micro", "mae_per_micro", "n_contracts", "risk_today"]]], ignore_index=True)
    t["day"] = t.tout.dt.date; t = t.sort_values("tin")
    by = {k: (g.per_micro.to_numpy(), g.mae_per_micro.to_numpy(), g.n_contracts.to_numpy(), g.risk_today.to_numpy()) for k, g in t.groupby("day")}
    td = sorted(by); return by, td, pd.to_datetime(pd.Series(td).astype(str)).to_numpy()


def size_k(k):
    return lambda n, risk: np.minimum(k * n, np.floor(900.0 / risk))


def size_r(R):
    return lambda n, risk: np.maximum(1.0, np.minimum(12.0, np.floor(R / risk)))


def evaluate(tab, sizer):
    """sizer(bal, day_index_calendar) -> function(n_contracts, risk) -> micros."""
    by, td, tix = tab; res = []
    for s in SESS:
        end = (pd.Timestamp(s) + pd.Timedelta(days=90)).date(); i = int(np.searchsorted(tix, np.datetime64(pd.Timestamp(s))))
        bal = 0.0; best = 0.0; out = "timeout"; when = None
        for d in td[i:]:
            if d >= end: break
            f = sizer(bal, (d - s).days, max(4000.0, best / 0.55)); per, mae, n, risk = by[d]; q = f(n, risk)
            stop = 400.0 if np.all(q <= n) else 700.0; day = 0.0
            for j in range(len(per)):
                if q[j] < 1: continue
                if day <= -stop or day <= -1000.0: break
                if bal + day + mae[j] * q[j] <= -2000.0: out = "fail"; break
                if day + mae[j] * q[j] <= -1000.0: day = -1000.0; break
                day += per[j] * q[j]
            if out == "fail": when = d; break
            bal += max(day, -1000.0); best = max(best, day)
            if bal <= -2000.0: out = "fail"; when = d; break
            if bal >= max(4000.0, best / 0.55): out = "pass"; when = d; break
        res.append((s, out, (when - s).days if (when and out == "pass") else None))
    r = pd.DataFrame(res, columns=["s", "o", "days"]); h1 = (r.s < H1_END).to_numpy()
    def sh(m): return round(100 * float((r.o[m] == "pass").mean()), 1)
    return dict(all=sh(np.ones(len(r), bool)), h1=sh(h1), h2=sh(~h1), fail=round(100 * float((r.o == "fail").mean()), 1),
                timeout=round(100 * float((r.o == "timeout").mean()), 1), median_days=float(r.days.dropna().median()))


TAB = {n: table(book(n)) for n in ("v5.3", "v5.2", "v5.3+TRD30_D", "v5.3+BRK30", "v5.3+TRD30_D+BRK30")}
fixed3 = lambda bal, day, tgt: size_k(3)
out = {"base v5.3 k3": evaluate(TAB["v5.3"], fixed3)}; base = out["base v5.3 k3"]; print("base", base, flush=True)
fam = {"B": {}, "C": {}, "D": {}}
for D in (45, 60, 75):
    for G in (1000.0, 2000.0):
        for ke in (5, 6):
            name = f"B endgame day {D}, gap > ${int(G)}, k{ke}"
            rule = (lambda D, G, ke: (lambda bal, day, tgt: size_k(ke) if (day >= D and bal < tgt - G) else size_k(3)))(D, G, ke)
            fam["B"][name] = out[name] = evaluate(TAB["v5.3"], rule); print(name, out[name], flush=True)
for R in (300.0, 450.0, 600.0):
    name = f"C equal risk ${int(R)}"; fam["C"][name] = out[name] = evaluate(TAB["v5.3"], (lambda R: lambda bal, day, tgt: size_r(R))(R)); print(name, out[name], flush=True)
for b in ("v5.2", "v5.3+TRD30_D", "v5.3+BRK30", "v5.3+TRD30_D+BRK30"):
    name = f"D book {b} k3"; fam["D"][name] = out[name] = evaluate(TAB[b], fixed3); print(name, out[name], flush=True)
conf = {}
for f, cells in fam.items():
    w = max(cells, key=lambda k: cells[k]["h1"]); ok = cells[w]["h2"] >= base["h2"] + 2.0
    conf[f] = dict(winner=w, h1=cells[w]["h1"], h2=cells[w]["h2"], base_h2=base["h2"], confirmed=bool(ok))
out["family_winners"] = conf; print("family winners:", conf, flush=True)
won = [f for f, c in conf.items() if c["confirmed"]]
if len(won) >= 2:
    wB = conf["B"]["winner"] if "B" in won else None; wC = conf["C"]["winner"] if "C" in won else None; wD = conf["D"]["winner"] if "D" in won else None
    bk = wD.split("book ")[1].split(" k3")[0] if wD else "v5.3"
    if wC:
        R = float(wC.split("$")[1]); basef = lambda bal, day, tgt, R=R: size_r(R)
    else: basef = fixed3
    if wB:
        D = int(wB.split("day ")[1].split(",")[0]); G = float(wB.split("$")[1].split(",")[0]); ke = int(wB.split(" k")[-1])
        rule = lambda bal, day, tgt, D=D, G=G, ke=ke: size_k(ke) if (day >= D and bal < tgt - G) else basef(bal, day, tgt)
    else: rule = basef
    c = out["COMBINATION"] = evaluate(TAB[bk], rule); c["confirmed"] = bool(c["h2"] >= base["h2"] + 2.0); c["parts"] = won
    print("COMBINATION", c, flush=True)
(ROOT / "reports/EVAL_5_PASS_RATE_TRAINING.json").write_text(json.dumps(out, indent=1, default=str))
