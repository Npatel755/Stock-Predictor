"""v54 (Claude, 2026-11-10): two more improvement attempts on v5.3 (v5.2 minus TRD30PM). TRAINING 2010-23 only (2024-26 spent).

PRE-DECLARED (before results).
PART 1 - funded account rule refit for v5.3 (it has fewer near-misses than v5.2). Rule family as payout_24: 1x below T2, 2x from T2 ($700 stop,
$900 risk cap), overnight while balance >= $500, daily payouts above K ($250-$1,500), static -$2,000 until the first payout then $0.
Cells: T2 in {$3,000, $4,000} x K in {$5,000, $6,000, $7,000}; current = T2 $4,000 / K $6,000. 24-month windows, S0 / S3 / S4, both halves.
ELIGIBLE: closed S0 <= 3%, S3 <= 8%, S4 <= 15%; S0 near-miss <= current's; payouts >= 8 in year 1 and in year 2 (S0).
ADOPT the eligible cell with the most S0 dollars only if dollars >= current x 1.05 in BOTH halves.
PART 2 - Crabel exit (strongest sleeve; exit never tested): hold_bars in {8 (current, 2 h), 16 (4 h), 22 (~5.5 h)} x trailing stop in
{none (current), 2.0 ATR} = 5 new variants, everything else unchanged (engine re-run of the sleeve, gap-continuation doubling as before).
Scored on both tracks exactly as v53; ADOPT only if: funded dollars >= v5.3 x 1.05 in both halves, closure (S0, S3, S4) <= v5.3 + 0.005,
S0 near-miss <= v5.3's, evaluation pass >= v5.3 - 1 point overall and not > 2 points worse in either half.
Sanity check first: the re-run of the current Crabel settings must reproduce base Crabel trades.
"""
import json
import numpy as np, pandas as pd

from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
src = (ROOT / "scripts/v53_improve_train.py").read_text(encoding="utf-8").split("\nout = {}\n")[0]
V = {"__name__": "v53", "__file__": str(ROOT / "scripts/v53_improve_train.py")}; exec(src, V)
pl, base0, variant, eval_track, stressed, sc17, N0, fds, NIGHT_RISK, mae_pct = (V[k] for k in ("pl", "base0", "variant", "eval_track", "stressed", "sc17", "N0", "fds", "NIGHT_RISK", "mae_pct"))
P10 = V["P10"]; ep, bars_for, START, gs = P10["ep"], P10["bars_for"], P10["START"], P10["gs"]
H = (("2010-07-01", "2016-06-01"), ("2016-07-01", "2022-01-01"))


def funded(d, T2=4000.0, K=6000.0):
    SER = {}
    for kind in ("S0", "S3", "S4"):
        e = stressed(d, kind); _, n = sc17(kind, N0)
        for m in (1, 2):
            em = e[e.risk_today * e.n_contracts * m <= (900.0 if m > 1 else 1e9)]
            i = pl.route(em)[["tin", "tout", "net_today"]].assign(net_today=lambda x: x.net_today * m)
            nm = n.assign(net_today=n.net_today * m) if (m == 1 or NIGHT_RISK * (1.5 if kind == "S4" else 1) * m <= 900.0) else n.iloc[0:0]
            stop = 400.0 if m == 1 else 700.0
            SER[(kind, m, False)] = fds(i, stop).to_dict(); SER[(kind, m, True)] = fds(pd.concat([i, nm], ignore_index=True), stop).to_dict()
    def run(kind, a0="2010-07-01", a1="2022-01-01"):
        keys = [k for k in SER if k[0] == kind]
        days = sorted(set().union(*[set(SER[k]) for k in keys])); ix = pd.to_datetime(pd.Series(days).astype(str)).to_numpy(); rows = []
        for s0 in pd.date_range(a0, a1, freq="MS"):
            a = int(np.searchsorted(ix, np.datetime64(s0))); b = int(np.searchsorted(ix, np.datetime64(s0 + pd.DateOffset(months=24))))
            cut = np.datetime64(s0 + pd.DateOffset(months=12)); bal = 0.0; paid = False; since = 0.0; usd = 0.0; closed = False; low = 0.0; p1 = p2 = 0
            for x, t in zip(days[a:b], ix[a:b]):
                m = 2 if bal >= T2 else 1
                p = max(SER[(kind, m, bal >= 500.0)].get(x, 0.0), -1000.0); bal += p; since += p
                if not paid: low = min(low, bal)
                if bal <= (0.0 if paid else -2000.0): closed = True; break
                if (since > 0 or not paid) and bal - K >= 250.0:
                    w = min(1500.0, bal - K); bal -= w; usd += w; paid = True; since = 0.0
                    if t < cut: p1 += 1
                    else: p2 += 1
            rows.append((usd, closed, low <= -1500.0, p1, p2))
        r = pd.DataFrame(rows, columns=["usd", "closed", "near", "p1", "p2"])
        return dict(usd=round(float(r.usd.mean()), 0), closed=round(float(r.closed.mean()), 3), near=round(float(r.near.mean()), 3),
                    y1=round(float(r.p1.mean()), 2), y2=round(float(r.p2.mean()), 2))
    return dict(S0=run("S0"), S3=run("S3"), S4=run("S4"), half1=run("S0", *H[0]), half2=run("S0", *H[1]))


out = {"part1": {}, "part2": {}}
v53 = variant("A")
# ---------------- PART 1
for T2 in (3000.0, 4000.0):
    for K in (5000.0, 6000.0, 7000.0):
        name = f"2x from ${int(T2):,} | keep ${int(K):,}"; f = out["part1"][name] = funded(v53, T2, K)
        print(f"P1 {name:28s} $ {f['S0']['usd']:>7} y1 {f['S0']['y1']} y2 {f['S0']['y2']} closed {f['S0']['closed']} near {f['S0']['near']} | S3 cl {f['S3']['closed']} | S4 cl {f['S4']['closed']} "
              f"| halves $ {f['half1']['usd']} / {f['half2']['usd']}", flush=True)
cur = out["part1"]["2x from $4,000 | keep $6,000"]
for name, f in out["part1"].items():
    f["eligible"] = bool(f["S0"]["closed"] <= 0.03 and f["S3"]["closed"] <= 0.08 and f["S4"]["closed"] <= 0.15 and f["S0"]["near"] <= cur["S0"]["near"]
                         and f["S0"]["y1"] >= 8 and f["S0"]["y2"] >= 8)
el = {k: v for k, v in out["part1"].items() if v["eligible"] and k != "2x from $4,000 | keep $6,000"}
best = max(el, key=lambda k: el[k]["S0"]["usd"]) if el else None
out["part1_selected"] = best if (best and all(el[best][h]["usd"] >= 1.05 * cur[h]["usd"] for h in ("half1", "half2"))) else None
print("PART 1 selected:", out["part1_selected"], flush=True)

# ---------------- PART 2
def crabel(hold, trail):
    sl = dict(ep._AG_CRABEL15_D, name="AG_CRABEL15_D_1c", hold_bars=hold, trailing_atr=trail)
    c = pl.price_normalize(pl.sleeve_trades(ep, bars_for, START, sl, 0, True))
    cont = np.array([int(r.side) * gs.get(r.tin.date(), 0) >= 0 for r in c.itertuples()])
    c["n_contracts"] = np.where(cont, 2.0, 1.0); c["net_today"] = c.net_today * c.n_contracts
    c["mae_per_micro"] = [(mae_pct(r.inst, r.tin, r.tout, r.side, r.entry) * pl.TODAY[r.inst] - pl.ADV) * pl.MULT[r.inst] for r in c.itertuples()]
    return c[base0.columns]


cur_c = crabel(8, 0.0); ref = base0[base0.sleeve.str.contains("CRABEL")]
out["part2_sanity"] = dict(rerun_trades=len(cur_c), base_trades=len(ref), rerun_net=round(float(cur_c.net_today.sum()), 0), base_net=round(float(ref.net_today.sum()), 0))
print("sanity:", out["part2_sanity"], flush=True)
assert len(cur_c) == len(ref) and abs(cur_c.net_today.sum() - ref.net_today.sum()) < 1.0, "Crabel re-run does not reproduce base"
base_eval, base_f = eval_track(v53), cur
out["part2"]["v5.3 (hold 8, no trail)"] = dict(evaluation=base_eval, funded=base_f)
for hold, trail in ((16, 0.0), (22, 0.0), (8, 2.0), (16, 2.0), (22, 2.0)):
    d = pd.concat([v53[~v53.sleeve.str.contains("CRABEL")], crabel(hold, trail)], ignore_index=True)
    e, f = eval_track(d), funded(d); name = f"hold {hold} | trail {trail}"
    adopt = bool(all(f[h]["usd"] >= 1.05 * base_f[h]["usd"] for h in ("half1", "half2")) and all(f[k]["closed"] <= base_f[k]["closed"] + 0.005 for k in ("S0", "S3", "S4"))
                 and f["S0"]["near"] <= base_f["S0"]["near"] and e["all"] >= base_eval["all"] - 1 and e["half1"] >= base_eval["half1"] - 2 and e["half2"] >= base_eval["half2"] - 2)
    out["part2"][name] = dict(evaluation=e, funded=f, adopt=adopt)
    print(f"P2 {name:18s} EVAL {e['all']} (H1 {e['half1']} H2 {e['half2']}) | FUNDED $ {f['S0']['usd']} closed {f['S0']['closed']} near {f['S0']['near']} | S3 cl {f['S3']['closed']} "
          f"| S4 cl {f['S4']['closed']} | halves $ {f['half1']['usd']} / {f['half2']['usd']} | adopt {adopt}", flush=True)
print(f"P2 base (v5.3)       EVAL {base_eval['all']} (H1 {base_eval['half1']} H2 {base_eval['half2']}) | FUNDED $ {base_f['S0']['usd']} halves $ {base_f['half1']['usd']} / {base_f['half2']['usd']}")
(ROOT / "reports/V54_IMPROVE_TRAINING.json").write_text(json.dumps(out, indent=1, default=str))
