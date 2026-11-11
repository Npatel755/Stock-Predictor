"""v55 (Claude, 2026-11-10): independent check of Antigravity's "Aegis Apex 4X" (research_supercharged_twostage_train.py). TRAINING only.

PRE-DECLARED (before results). Aegis = v5.3 book + overnight dip exited at 09:15 ET (instead of 09:45) + cap-aware ladder 1x <$2,500, 2x from
$2,500, 3x from $4,500, 4x from $6,500 (size per trade = min(m x base, floor($900 / stop risk)), overnight min(m, floor($900 / its risk))),
daily payouts above K = $7,500. Two separate questions:
PART A - overnight exit 09:15 vs 09:45 (0.55% stop, 1 micro, today's price): nights, net, PF and worst night per half (2010-16, 2017-23).
  09:15 is called better only if its net AND PF beat 09:45 in BOTH halves (it was picked from a grid on all 14 years).
PART B - sizing ladder on v5.3 with the CURRENT 09:45 exit (so the exit choice does not mix in): (1) current rule (2x from $4,000, skip a
  trade risking > $900, K $6,000); (2) Aegis ladder cap-aware, K $7,500; (3) Aegis ladder with the skip rule, K $7,500; (4) current ladder
  but cap-aware, K $6,000. 24-month windows, S0 / S3 / S4, both halves, near-miss, conservative closure (each day's largest position hits its
  full stop before any gain). The Aegis ladder (2) is confirmed only if 24-month dollars >= (1) x 1.10 in BOTH halves, closure (S0, S3, S4)
  <= (1) + 0.005, conservative closure (S0, S3, S4) <= (1) + 0.02, and S0 near-miss <= (1)'s.
"""
import json
import numpy as np, pandas as pd
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
src = (ROOT / "scripts/v53_improve_train.py").read_text(encoding="utf-8").split("\nout = {}\n")[0]
V = {"__name__": "v53", "__file__": str(ROOT / "scripts/v53_improve_train.py")}; exec(src, V)
pl, variant, stressed, sc17, N0, fds, NIGHT_RISK = (V[k] for k in ("pl", "variant", "stressed", "sc17", "N0", "fds", "NIGHT_RISK"))
P10 = V["P10"]; ov = P10["ov"]; m1 = P10["m1"]
TS = pd.to_datetime(m1.timestamp_utc, utc=True).dt.as_unit("ns").astype("int64").to_numpy(); O, L, C = m1.open.to_numpy(float), m1.low.to_numpy(float), m1.close.to_numpy(float)
H = (("2010-07-01", "2016-06-01"), ("2016-07-01", "2022-01-01"))


def nights(exit_hm):
    rows = []
    for t in ov:
        e_raw = float(t["entry_price"]) - pl.ADV; tin = pd.Timestamp(t["entry_ts"])
        tout = pd.Timestamp(t["exit_ts"]).tz_convert(pl.NY).replace(hour=exit_hm[0], minute=exit_hm[1]).tz_convert("UTC")
        i0, i1 = int(np.searchsorted(TS, tin.value)), int(np.searchsorted(TS, tout.value))
        if i1 <= i0: continue
        stop = e_raw * (1 - 0.0055); hit = np.nonzero(L[i0:i1] <= stop)[0]
        if len(hit): j = i0 + int(hit[0]); x_raw = min(stop, O[j]) if j > i0 else stop
        else: x_raw = O[i1] + pl.ADV if i1 < len(O) else C[i1 - 1] + pl.ADV     # exit at the open of the exit minute (engine-like), adverse tick
        x_raw -= pl.ADV if not len(hit) else 0.0
        net = (((x_raw - e_raw) / e_raw) * pl.TODAY["MNQ"] - 2 * pl.ADV) * pl.MULT["MNQ"] - pl.FEE
        rows.append(dict(tin=tin.tz_convert(pl.NY), tout=tout.tz_convert(pl.NY), net_today=net))
    return pd.DataFrame(rows)


def part_a():
    out = {}
    for name, hm in (("09:45", (9, 45)), ("09:15", (9, 15))):
        n = nights(hm); o = out[name] = {}
        for h, (a, b) in (("2010-16", ("2010-01-01", "2017-01-01")), ("2017-23", ("2017-01-01", "2024-01-01"))):
            x = n[(n.tin >= pd.Timestamp(a, tz=pl.NY)) & (n.tin < pd.Timestamp(b, tz=pl.NY))].net_today
            o[h] = dict(nights=int(len(x)), net=round(float(x.sum()), 0), pf=round(float(x[x > 0].sum() / -x[x < 0].sum()), 3), worst=round(float(x.min()), 0))
    out["check_0945_reproduces_payout_17"] = round(float(nights((9, 45)).net_today.sum() - N0.net_today.sum()), 2)
    out["0915_better_both_halves"] = bool(all(out["09:15"][h]["net"] > out["09:45"][h]["net"] and out["09:15"][h]["pf"] > out["09:45"][h]["pf"] for h in ("2010-16", "2017-23")))
    return out


def build(d, cap_aware):
    SER, RISK = {}, {}
    for kind in ("S0", "S3", "S4"):
        e = stressed(d, kind); _, n = sc17(kind, N0); nr = NIGHT_RISK * (1.5 if kind == "S4" else 1.0)
        r = pl.route(e)                                                     # routing at 1x, as the paper book does
        for m in (1, 2, 3, 4):
            per = r.net_today / r.n_contracts; risk = r.risk_today
            if cap_aware: q = np.minimum(m * r.n_contracts, np.floor(900.0 / risk)) if m > 1 else r.n_contracts
            else: q = np.where(risk * r.n_contracts * m <= (900.0 if m > 1 else 1e9), m * r.n_contracts, 0.0)
            i = r.assign(net_today=per * q, q=q)[lambda x: x.q >= 1]
            qn = (min(m, int(900.0 // nr)) if cap_aware else (m if (m == 1 or nr * m <= 900.0) else 0)) if m > 1 else 1
            nm = n.assign(net_today=n.net_today * qn) if qn >= 1 else n.iloc[0:0]
            stop = 400.0 if m == 1 else 700.0
            SER[(kind, m, False)] = fds(i[["tin", "tout", "net_today"]], stop).to_dict()
            SER[(kind, m, True)] = fds(pd.concat([i[["tin", "tout", "net_today"]], nm], ignore_index=True), stop).to_dict()
            rk = (i.risk_today * i.q).groupby(i.tout.dt.date).max()
            if qn >= 1: rk = pd.concat([rk, pd.Series(nr * qn, index=pd.Index(n.tout.dt.date))]).groupby(level=0).max()
            RISK[(kind, m)] = rk.to_dict()
    return SER, RISK


def run(SER, RISK, kind, ladder, K, a0="2010-07-01", a1="2022-01-01"):
    keys = [k for k in SER if k[0] == kind]
    days = sorted(set().union(*[set(SER[k]) for k in keys])); ix = pd.to_datetime(pd.Series(days).astype(str)).to_numpy(); rows = []
    for s0 in pd.date_range(a0, a1, freq="MS"):
        a = int(np.searchsorted(ix, np.datetime64(s0))); b = int(np.searchsorted(ix, np.datetime64(s0 + pd.DateOffset(months=24))))
        bal = 0.0; paid = False; since = 0.0; usd = 0.0; closed = False; cons = False; low = 0.0
        for x in days[a:b]:
            m = max((mm for th, mm in ladder if bal >= th), default=ladder[0][1]); floor = 0.0 if paid else -2000.0   # 1x below $0 too
            if bal - RISK[(kind, m)].get(x, 0.0) <= floor: cons = True
            p = max(SER[(kind, m, bal >= 500.0)].get(x, 0.0), -1000.0); bal += p; since += p
            if not paid: low = min(low, bal)
            if bal <= floor: closed = True; break
            if (since > 0 or not paid) and bal - K >= 250.0:
                w = min(1500.0, bal - K); bal -= w; usd += w; paid = True; since = 0.0
        rows.append((usd, closed, cons, low <= -1500.0))
    r = pd.DataFrame(rows, columns=["usd", "closed", "cons", "near"])
    return dict(usd=round(float(r.usd.mean()), 0), closed=round(float(r.closed.mean()), 3), cons=round(float(r.cons.mean()), 3), near=round(float(r.near.mean()), 3))


def cell(SER, RISK, ladder, K):
    c = {k: run(SER, RISK, k, ladder, K) for k in ("S0", "S3", "S4")}
    c["half1"] = run(SER, RISK, "S0", ladder, K, *H[0]); c["half2"] = run(SER, RISK, "S0", ladder, K, *H[1]); return c


out = {"part_a": part_a()}; print("PART A:", json.dumps(out["part_a"]), flush=True)
d = variant("A")
SKIP, CAP = build(d, False), build(d, True)
CUR = [(0, 1), (4000, 2)]; AEG = [(0, 1), (2500, 2), (4500, 3), (6500, 4)]
cells = {"(1) current: 2x from $4k, skip rule, K $6k": (SKIP, CUR, 6000.0), "(2) Aegis ladder, cap-aware, K $7.5k": (CAP, AEG, 7500.0),
         "(3) Aegis ladder, skip rule, K $7.5k": (SKIP, AEG, 7500.0), "(4) current ladder, cap-aware, K $6k": (CAP, CUR, 6000.0),
         "(5) v54 winner: 2x from $3k, skip rule, K $6k (reported only)": (SKIP, [(0, 1), (3000, 2)], 6000.0)}
out["part_b"] = {}
for name, (S, lad, K) in cells.items():
    c = out["part_b"][name] = cell(*S, lad, K)
    print(f"{name:44s} S0 $ {c['S0']['usd']:>7} cl {c['S0']['closed']} cons {c['S0']['cons']} near {c['S0']['near']} | S3 $ {c['S3']['usd']} cl {c['S3']['closed']} cons {c['S3']['cons']} "
          f"| S4 $ {c['S4']['usd']} cl {c['S4']['closed']} cons {c['S4']['cons']} | halves $ {c['half1']['usd']} / {c['half2']['usd']}", flush=True)
b, g = out["part_b"]["(1) current: 2x from $4k, skip rule, K $6k"], out["part_b"]["(2) Aegis ladder, cap-aware, K $7.5k"]
out["aegis_ladder_confirmed"] = bool(all(g[h]["usd"] >= 1.10 * b[h]["usd"] for h in ("half1", "half2")) and all(g[k]["closed"] <= b[k]["closed"] + 0.005 for k in ("S0", "S3", "S4"))
                                     and all(g[k]["cons"] <= b[k]["cons"] + 0.02 for k in ("S0", "S3", "S4")) and g["S0"]["near"] <= b["S0"]["near"])
print("Aegis ladder confirmed:", out["aegis_ladder_confirmed"], "| 09:15 exit better in both halves:", out["part_a"]["0915_better_both_halves"])
(ROOT / "reports/V55_CHECK_AEGIS_TRAINING.json").write_text(json.dumps(out, indent=1, default=str))
