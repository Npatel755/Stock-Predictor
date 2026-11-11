"""payout_16 (Claude, 2026-11-10): equal-risk sizing for the payout book at today's prices. TRAINING 2010-23 only.

PRE-DECLARED (before results). Motivation (diagnostic run on the same training trades, no grid): v5.2 trades ~104 days/yr, only 31.7
reach >= $150 while 18.7 end between $0 and $150; the median stop risk per micro is $95 (MES 30m), $152 (60m trend), $169 (Crabel),
$205 (30m PM), so a 1R win on 1 micro often stays under $150.
Base R = v5.2 (1 micro; 2 micros on gap-continuation Crabel; skip trades with stop risk > $300 per micro; research routing; $400 account
stop) + overnight dip (0.55% stop, 1 micro) only when the balance is >= $500; $1,000 buffer at withdrawal; static -$2,000; $1k DLL.
Change tested: intraday micros = clip(floor(T / stop risk per micro), 1, K), times 2 for gap-continuation Crabel (v5.2 rule kept), so
each trade risks <= T (<= 2T for continuation). The $300 skip rule, routing, account stop and overnight leg are unchanged.
Grid: T in {$150, $200, $300} x K in {2, 3} x staging S_size in {$0, $500} (equal-risk sizing only while the balance at the prior close
is >= S_size, else v5.2 sizing) = 12 cells.
Metrics (151 monthly 12-month starts): payouts per 12 months mean / p10, 12-month breach, mean payout amount, days <= -$1,000, $150 days/yr.
SELECTION RULE (worst case first): eligible = S0 breach <= 2% AND S3 (costs +2 ticks/side + edge -25%) breach <= 5% AND S4 (volatility x1.5)
breach <= the base's S4 breach AND 0 days <= -$1,000 AND payouts up vs base in BOTH halves (starts 2010-07..2016-12 and 2017-01..2023-01).
Among eligible, the most S0 payouts. Adopt only if it beats base by >= 0.5 payouts per 12 months (multiplicity margin: 12 cells).
Stress definitions are payout_13's: S1 -1.0 pt x multiplier per contract; S2 each trade loses 25% of its sleeve's average net per micro;
S4 stop risk x1.5 and every intraday net x1.5, overnight non-stopped nights x1.5, stopped nights keep their stop loss.
"""
import json
import numpy as np, pandas as pd
import payout_lib as pl

src = (pl.ROOT / "scripts/payout_13_stress_train.py").read_text(encoding="utf-8").split("\nout = {}")[0]
ns = {"__name__": "p13"}; exec(src, ns)
base_intra, nights, stop_loss_level = ns["base_intra"], ns["nights"], ns["stop_loss_level"]
base_intra = base_intra.assign(base_n=base_intra.n_contracts, per_micro=base_intra.net_today / base_intra.n_contracts)
N0 = nights(0.0055)


def scenario(kind):
    d = base_intra.copy(); n = N0.copy()
    if kind in ("S1", "S3"):
        d["per_micro"] -= 1.0 * d.inst.map(pl.MULT); n["net_today"] -= 1.0 * pl.MULT["MNQ"]
    if kind in ("S2", "S3"):
        avg = d.groupby("sleeve").per_micro.transform("mean"); d["per_micro"] -= 0.25 * avg.clip(lower=0)
        n["net_today"] -= 0.25 * max(float(n.net_today.mean()), 0.0)
    if kind == "S4":
        d["risk_today"] *= 1.5; d["per_micro"] *= 1.5
        stopped = n.net_today <= stop_loss_level + 1e-6; n.loc[~stopped, "net_today"] *= 1.5
    return d, n[["tin", "tout", "net_today"]]


def intraday(d, T=None, K=1):
    e = d[d.risk_today <= 300.0].copy()
    q = np.ones(len(e)) if T is None else np.clip(np.floor(T / e.risk_today.to_numpy()), 1, K)
    e["net_today"] = e.per_micro * q * e.base_n
    return pl.route(e)[["tin", "tout", "net_today"]]


_CACHE = {}


def series(kind, T, K):
    if (kind, T, K) not in _CACHE:
        d, n = SC[kind]; i1 = intraday(d); iE = intraday(d, T, K) if T else i1
        _CACHE[(kind, T, K)] = {(sz, nt): pl.day_series(pd.concat([i] + ([n] if nt else []), ignore_index=True), stop=400.0).to_dict()
                                for sz, i in (("1", i1), ("E", iE)) for nt in (False, True)}
    return _CACHE[(kind, T, K)]


def evaluate(kind, T, K, S_size, S_night=500.0, C=1000.0, start_from=None, start_to=None):
    ser = series(kind, T, K)
    days = sorted(set().union(*[set(s) for s in ser.values()])); idx = pd.to_datetime(pd.Series(days).astype(str)).to_numpy()
    res = []
    for s0 in pd.date_range(start_from or "2010-07-01", start_to or "2023-01-01", freq="MS"):
        a = int(np.searchsorted(idx, np.datetime64(s0))); b = int(np.searchsorted(idx, np.datetime64(s0 + pd.DateOffset(months=12))))
        bal = 0.0; good = 0; pays = []; breach = False; dll = 0; q150 = 0
        for x in days[a:b]:
            p = ser[("E" if bal >= S_size else "1", bal >= S_night)].get(x, 0.0)
            dll += p <= -1000; bal += max(p, -1000.0)
            if bal <= -2000.0: breach = True; break
            good += p >= 150; q150 += p >= 150
            if good >= 5 and bal - C > 0: pays.append(bal - C); bal = C; good = 0
        res.append((len(pays), breach, float(np.mean(pays)) if pays else np.nan, dll, q150))
    r = pd.DataFrame(res, columns=["pays", "breach", "avg_pay", "dll", "q150"])
    return dict(payouts_12m_mean=round(float(r.pays.mean()), 2), payouts_12m_p10=float(r.pays.quantile(.1)), p_breach_12m=round(float(r.breach.mean()), 3),
                mean_payout=round(float(r.avg_pay.mean()), 0), dll_days=int(r.dll.sum()), days_ge150_12m=round(float(r.q150.mean()), 1))


SC = {k: scenario(k) for k in ("S0", "S3", "S4")}
H1, H2 = ("2010-07-01", "2016-12-01"), ("2017-01-01", "2023-01-01")


def cell(T, K, S):
    return dict(S0=evaluate("S0", T, K, S), S3=evaluate("S3", T, K, S), S4=evaluate("S4", T, K, S),
                H1=evaluate("S0", T, K, S, start_from=H1[0], start_to=H1[1]), H2=evaluate("S0", T, K, S, start_from=H2[0], start_to=H2[1]))


out = {"base R": cell(None, 1, 0.0)}
print("base R", out["base R"], flush=True)
b = out["base R"]
for T in (150.0, 200.0, 300.0):
    for K in (2, 3):
        for S in (0.0, 500.0):
            name = f"T${int(T)} K{K} S${int(S)}"; c = out[name] = cell(T, K, S)
            c["eligible"] = bool(c["S0"]["p_breach_12m"] <= 0.02 and c["S3"]["p_breach_12m"] <= 0.05 and c["S4"]["p_breach_12m"] <= b["S4"]["p_breach_12m"]
                                 and c["S0"]["dll_days"] == 0 and c["H1"]["payouts_12m_mean"] > b["H1"]["payouts_12m_mean"] and c["H2"]["payouts_12m_mean"] > b["H2"]["payouts_12m_mean"])
            print(f"{name:16s} S0 {c['S0']} | S3 br {c['S3']['p_breach_12m']} | S4 br {c['S4']['p_breach_12m']} | H1 {c['H1']['payouts_12m_mean']} H2 {c['H2']['payouts_12m_mean']} | eligible {c['eligible']}", flush=True)
ok = {k: v for k, v in out.items() if isinstance(v, dict) and v.get("eligible")}
best = max(ok, key=lambda k: ok[k]["S0"]["payouts_12m_mean"]) if ok else None
out["selected"] = best
out["adopt"] = bool(best and ok[best]["S0"]["payouts_12m_mean"] >= b["S0"]["payouts_12m_mean"] + 0.5)
print("selected:", best, "adopt:", out["adopt"])
(pl.ROOT / "reports/PAYOUT_16_EQUAL_RISK_TRAINING.json").write_text(json.dumps(out, indent=1, default=str))
